"""Live ticker engine — polls yfinance on a fast interval and broadcasts
price deltas to subscribers (SSE clients).

Universe: every IDX-listed ticker in ``data/idx_universe.txt`` (≈951
emiten). Yahoo Finance doesn't expose a streaming API, so we poll on our
own cadence. To stay within yfinance's rate limits:

* **Hot lane** — a small set of the most-tracked symbols (BBCA, BBRI,
  IHSG, etc.) is polled every cycle, so the cards users see on the
  first screen feel "live".
* **Cold lane** — the rest of the universe is polled round-robin in
  batches. One full sweep takes roughly 60–90 s.
* **Stalled tickers** — yfinance returns nothing for suspended / delisted
  / pre-IPO stocks. After a few consecutive misses we move them to a
  "slow" bucket polled once a minute. The moment they respond again, they
  bounce back into the active set automatically. No manual filter list.
* **IHSG (^JKSE)** is polled on its own tight interval for the hero card.

The in-memory state is the source of truth for the REST snapshot and the
SSE delta stream. Symbols that have never produced a quote are still
exposed (with ``price=null``) so the UI can render skeletons.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Set

import yfinance as yf

logger = logging.getLogger('saham-api')

# ── Tunables (env-overridable) ──────────────────────────────────────
# Polling cadence was reduced from 4s/40 batch to 8s/30 batch to keep us
# under Yahoo Finance's unofficial rate limit (~200 req/min/IP). Combined
# with a 0-1.5s jitter, we now sit around ~120 req/min — well within the
# safe zone even with hot+cold+slow lanes combined.
POLL_IHSG_SECS = float(os.environ.get('TICKER_POLL_IHSG', '2.0'))
POLL_STOCKS_SECS = float(os.environ.get('TICKER_POLL_STOCKS', '8.0'))
BATCH_SIZE = int(os.environ.get('TICKER_BATCH', '30'))
POLL_JITTER_SECS = float(os.environ.get('TICKER_JITTER', '1.5'))
SUBSCRIBER_QUEUE_MAX = 8
SLOW_LANE_STRIKES = 4           # consecutive failures before demotion
SLOW_LANE_RESCAN = 15           # every N cycles, retry stalled tickers
SLOW_LANE_PROBE_SIZE = 12       # how many stalled to re-check per rescan
STALE_AFTER_SECS = 15 * 60      # after 15min, mark as "stale"
# Backoff state — incremented on yfinance errors, reset on a clean cycle.
_BACKOFF_INITIAL = 5.0          # first back-off sleep in seconds
_BACKOFF_MAX = 60.0             # cap on exponential back-off
_BACKOFF_FACTOR = 2.0           # multiplier per consecutive failure

# IHSG sanity bounds — reject obviously bad quotes
_IHSG_LOW = 4500.0
_IHSG_HIGH = 12000.0

# Per-stock sanity bounds (very wide — penny stocks to blue chips).
# 1 < price < 10M IDR covers the entire IDX range.
_STOCK_LOW = 1.0
_STOCK_HIGH = 10_000_000.0

# Hot lane — most-watched symbols get polled every cycle. Tickers NOT in
# this list still get polled via the round-robin sweep, just less often.
HOT_SYMBOLS: List[str] = [
    'BBCA', 'BBRI', 'BMRI', 'BBNI', 'TLKM', 'ASII', 'INDF', 'UNVR',
    'ICBP', 'KLBF', 'GOTO', 'ADRO', 'PTBA', 'ANTM', 'INCO', 'PGAS',
    'JSMR', 'SMGR', 'INTP', 'BREN', 'AMMN', 'MBMA', 'CUAN', 'CDIA',
    'PTRO', 'PANI', 'DSSA',
]

# Fallback when the data file is missing — enough to render the app.
_FALLBACK_UNIVERSE = [
    'BBCA', 'BBRI', 'BMRI', 'BBNI', 'TLKM', 'ASII', 'INDF', 'UNVR',
    'ICBP', 'KLBF', 'GOTO', 'ADRO', 'PTBA', 'ANTM', 'INCO', 'PGAS',
    'JSMR', 'SMGR', 'INTP', 'BREN', 'AMMN', 'MBMA', 'CUAN', 'CDIA',
]

_UNIVERSE_FILE = Path(__file__).resolve().parent.parent / 'data' / 'idx_universe.txt'


def _valid_price(v, lo=_STOCK_LOW, hi=_STOCK_HIGH) -> bool:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return False
    return lo <= v <= hi and v == v  # NaN check


@dataclass
class Tick:
    symbol: str
    price: Optional[float] = None
    prev_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    ts: float = 0.0  # unix seconds
    stalled: bool = False  # true when yfinance has stopped returning data

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get('price') is not None:
            d['price'] = round(float(d['price']), 2)
        if d.get('change') is not None:
            d['change'] = round(float(d['change']), 2)
        if d.get('change_pct') is not None:
            d['change_pct'] = round(float(d['change_pct']), 2)
        return d


class TickerEngine:
    """In-memory price cache + SSE broadcaster for the full IDX universe."""

    _instance: Optional['TickerEngine'] = None

    def __init__(self):
        self._state: Dict[str, Tick] = {}
        self._subscribers: List[asyncio.Queue] = []
        self._tasks: List[asyncio.Task] = []
        self._running = False

        # Full IDX universe (no .JK suffix). Loaded once at start().
        self._universe: List[str] = []

        # Round-robin cursor into the universe
        self._cursor: int = 0

        # Track how many consecutive polls returned nothing for a symbol.
        # When this hits SLOW_LANE_STRIKES, the symbol is demoted to the
        # slow lane and the regular round-robin skips it.
        self._failures: Dict[str, int] = {}

        # Slow lane — symbols that repeatedly fail (likely suspended)
        self._stalled: List[str] = []
        self._stalled_set: Set[str] = set()
        # Cycle counter for slow-lane rescans
        self._cycle_n: int = 0

    # ── Singleton ──

    @classmethod
    def instance(cls) -> 'TickerEngine':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Lifecycle ──

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._load_universe()
        self._tasks = [
            asyncio.create_task(self._ihsg_loop(), name='ticker-ihsg'),
            asyncio.create_task(self._stocks_loop(), name='ticker-stocks'),
            asyncio.create_task(self._slow_lane_loop(), name='ticker-slow'),
        ]
        logger.info(
            'TickerEngine: started (ihsg=%.1fs stocks=%.1fs universe=%d hot=%d)',
            POLL_IHSG_SECS, POLL_STOCKS_SECS,
            len(self._universe), len(HOT_SYMBOLS),
        )

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()
        for q in self._subscribers:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
        self._subscribers.clear()

    # ── Universe loading ──

    def _load_universe(self) -> None:
        """Load every IDX-listed ticker from data/idx_universe.txt.

        The file is curated and contains the official listing. Yahoo
        Finance's own universe can drift (new IPOs, delistings), so we
        trust our local file and let yfinance be the live-data oracle.
        Symbols that don't return data are NOT removed from the universe
        — they're just demoted to the slow lane.
        """
        symbols: List[str] = []
        try:
            if _UNIVERSE_FILE.exists():
                with _UNIVERSE_FILE.open() as f:
                    symbols = [
                        line.strip().replace('.JK', '').upper()
                        for line in f
                        if line.strip()
                    ]
        except Exception as exc:
            logger.warning('universe file read failed: %s', exc)

        if not symbols:
            symbols = list(_FALLBACK_UNIVERSE)
            logger.warning('universe file empty — using %d-ticker fallback',
                          len(symbols))

        # Dedup, preserve order
        seen: Set[str] = set()
        universe: List[str] = []
        for s in symbols:
            if s and s not in seen:
                seen.add(s)
                universe.append(s)

        self._universe = universe

        # Seed state rows so the SSE snapshot is complete on first connect
        now = time.time()
        for sym in universe:
            if sym not in self._state:
                self._state[sym] = Tick(symbol=sym, ts=now)
        # ^JKSE row
        if '^JKSE' not in self._state:
            self._state['^JKSE'] = Tick(symbol='^JKSE', ts=now)

        # Reset round-robin cursor
        self._cursor = 0
        self._cycle_n = 0
        self._failures.clear()
        self._stalled.clear()
        self._stalled_set.clear()

    # ── Subscribe / publish ──

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_MAX)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def _publish(self, event: Dict[str, Any]) -> None:
        """Fan out a tick event to all subscribers. Drops oldest on backpressure."""
        dead: List[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow client — drop oldest, push the new one
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    # ── Snapshot (REST) ──

    def snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """Return the current in-memory state for the requested symbols.

        Symbols with no data yet are still included (with ``price=null``)
        so clients can render skeletons without losing the row.
        """
        if not symbols:
            ticks = list(self._state.values())
        else:
            ticks = [self._state[s] for s in symbols if s in self._state]
            present = {t.symbol for t in ticks}
            for s in symbols:
                if s not in present:
                    ticks.append(Tick(symbol=s, ts=0.0))
        ihsg = self._state.get('^JKSE')
        return {
            'ihsg': ihsg.to_dict() if ihsg else None,
            'ticks': [t.to_dict() for t in ticks],
            'ts': time.time(),
            'universe_size': len(self._universe),
            'stalled_size': len(self._stalled),
        }

    def universe_size(self) -> int:
        return len(self._universe)

    # ── Polling loops ──

    async def _ihsg_loop(self) -> None:
        await asyncio.sleep(0.3)
        while self._running:
            try:
                tick = await self._fetch_ihsg()
                if tick is not None:
                    prev = self._state.get('^JKSE')
                    self._state['^JKSE'] = tick
                    if (not prev
                            or prev.price != tick.price
                            or prev.change != tick.change):
                        self._publish({'type': 'ihsg', 'data': tick.to_dict()})
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug('TickerEngine: ihsg loop error: %s', exc)
            await asyncio.sleep(POLL_IHSG_SECS)

    async def _stocks_loop(self) -> None:
        """Hot lane + round-robin sweep through the active universe.

        Each cycle:
          * Poll all HOT_SYMBOLS (so the most-watched cards stay "live")
          * Poll a BATCH_SIZE slice of the universe via the round-robin
            cursor (skipping anything in the slow lane)

        Cadence is ``POLL_STOCKS_SECS`` with ``POLL_JITTER_SECS`` random jitter
        to avoid the synchronous "thundering herd" pattern. If yfinance
        raises, we apply exponential back-off and only reset the counter
        after a clean cycle.
        """
        import random
        await asyncio.sleep(0.5)
        backoff = 0.0
        while self._running:
            cycle_ok = True
            try:
                self._cycle_n += 1
                # Hot lane: every cycle
                hot = [s for s in HOT_SYMBOLS if s in self._state]
                if hot:
                    changed_hot = await self._fetch_batch(hot)
                    if changed_hot:
                        self._publish({
                            'type': 'ticks',
                            'data': [t.to_dict() for t in changed_hot],
                        })
                # Cold lane: round-robin batch
                batch = self._next_batch()
                if batch:
                    changed_cold = await self._fetch_batch(batch)
                    if changed_cold:
                        self._publish({
                            'type': 'ticks',
                            'data': [t.to_dict() for t in changed_cold],
                        })
            except asyncio.CancelledError:
                break
            except Exception as exc:
                cycle_ok = False
                logger.warning('TickerEngine: stocks loop error: %s', exc)
            # Apply backoff if cycle failed, otherwise reset.
            if cycle_ok:
                backoff = 0.0
                jitter = random.uniform(0, POLL_JITTER_SECS)
                await asyncio.sleep(POLL_STOCKS_SECS + jitter)
            else:
                backoff = min(_BACKOFF_MAX, max(_BACKOFF_INITIAL, backoff * _BACKOFF_FACTOR or _BACKOFF_INITIAL))
                logger.info('TickerEngine: backing off %.1fs after yfinance error', backoff)
                await asyncio.sleep(backoff)

    async def _slow_lane_loop(self) -> None:
        """Re-check a few stalled tickers every cycle.

        When a suspended stock resumes trading, this loop is what puts
        it back into the active universe. Picks `SLOW_LANE_PROBE_SIZE`
        random stalled symbols each cycle — keeps the slow lane fresh
        without hammering it.
        """
        await asyncio.sleep(1.0)
        while self._running:
            try:
                # Wait a few cycles between rescans
                if self._cycle_n % SLOW_LANE_RESCAN != 0:
                    await asyncio.sleep(POLL_STOCKS_SECS)
                    continue
                if not self._stalled:
                    await asyncio.sleep(POLL_STOCKS_SECS)
                    continue
                # Probe a sample of stalled tickers
                import random
                sample = random.sample(
                    self._stalled,
                    min(SLOW_LANE_PROBE_SIZE, len(self._stalled)),
                )
                changed = await self._fetch_batch(sample)
                if changed:
                    # Any symbol that responded gets promoted back
                    for t in changed:
                        self._rejoin_universe(t.symbol)
                    self._publish({
                        'type': 'ticks',
                        'data': [t.to_dict() for t in changed],
                    })
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug('TickerEngine: slow lane error: %s', exc)
            await asyncio.sleep(POLL_STOCKS_SECS)

    def _next_batch(self) -> List[str]:
        """Take the next slice of the universe, skipping the slow lane."""
        if not self._universe:
            return []
        # Build a fresh active set each call so demotions take effect
        active = [s for s in self._universe if s not in self._stalled_set]
        if not active:
            return []
        n = len(active)
        # Take a BATCH_SIZE window starting at the cursor, wrapping around
        start = self._cursor % n
        end = start + BATCH_SIZE
        if end <= n:
            batch = active[start:end]
            self._cursor = (end) % n
        else:
            # Wrap
            batch = active[start:] + active[:end - n]
            self._cursor = (end - n) % n
        return batch

    def _demote_to_slow_lane(self, symbol: str) -> None:
        if symbol in self._stalled_set:
            return
        self._stalled.append(symbol)
        self._stalled_set.add(symbol)
        # Mark the existing row as stalled so the UI can show the right hint
        tick = self._state.get(symbol)
        if tick is not None:
            tick.stalled = True
        logger.debug('TickerEngine: demoted %s to slow lane', symbol)

    def _rejoin_universe(self, symbol: str) -> None:
        if symbol not in self._stalled_set:
            return
        self._stalled_set.discard(symbol)
        try:
            self._stalled.remove(symbol)
        except ValueError:
            pass
        tick = self._state.get(symbol)
        if tick is not None:
            tick.stalled = False
        self._failures.pop(symbol, None)
        logger.info('TickerEngine: %s re-joined active universe', symbol)

    # ── Fetches (run in executor — yfinance is sync) ──

    async def _fetch_ihsg(self) -> Optional[Tick]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_ihsg_sync)

    def _fetch_ihsg_sync(self) -> Optional[Tick]:
        try:
            t = yf.Ticker('^JKSE')
            current = None
            prev_close = None
            intraday = t.history(period='1d', interval='1m', timeout=3)
            if not intraday.empty:
                closes = intraday['Close'].dropna()
                opens = intraday['Open'].dropna()
                if len(closes):
                    current = float(closes.iloc[-1])
                if len(opens):
                    prev_close = float(opens.iloc[0])
            if not _valid_price(current, _IHSG_LOW, _IHSG_HIGH):
                info = t.fast_info or {}
                current = info.get('last_price') or info.get('regular_market_price')
            if not _valid_price(current, _IHSG_LOW, _IHSG_HIGH):
                hist5 = t.history(period='5d', timeout=3)
                if not hist5.empty:
                    current = float(hist5['Close'].dropna().iloc[-1])
            if not _valid_price(prev_close, _IHSG_LOW, _IHSG_HIGH):
                info = t.fast_info or {}
                prev_close = info.get('previous_close')
            if not _valid_price(prev_close, _IHSG_LOW, _IHSG_HIGH):
                hist5 = t.history(period='5d', timeout=3)
                if len(hist5) >= 2:
                    prev_close = float(hist5['Close'].dropna().iloc[-2])
            if not _valid_price(current, _IHSG_LOW, _IHSG_HIGH):
                return None
            change = round(current - prev_close, 2) if prev_close else 0.0
            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
            return Tick(
                symbol='^JKSE',
                price=round(current, 2),
                prev_close=round(prev_close, 2) if prev_close else None,
                change=change,
                change_pct=change_pct,
                ts=time.time(),
            )
        except Exception as exc:
            logger.debug('ihsg fetch failed: %s', exc)
            return None

    async def _fetch_batch(self, symbols: List[str]) -> List[Tick]:
        loop = asyncio.get_event_loop()
        all_changed: List[Tick] = []
        # Process in chunks of BATCH_SIZE — yfinance handles it well, but
        # smaller chunks keep individual HTTP responses bounded.
        for i in range(0, len(symbols), BATCH_SIZE):
            if not self._running:
                break
            chunk = symbols[i:i + BATCH_SIZE]
            try:
                results = await loop.run_in_executor(
                    None, self._fetch_batch_sync, chunk,
                )
            except Exception as exc:
                logger.debug('batch fetch failed: %s', exc)
                results = []
            responded = {tick.symbol for tick in results}
            for tick in results:
                prev = self._state.get(tick.symbol)
                if (prev
                        and prev.price == tick.price
                        and prev.change == tick.change):
                    # No actual change — don't bother publishing
                    self._failures.pop(tick.symbol, None)
                    continue
                self._state[tick.symbol] = tick
                self._failures.pop(tick.symbol, None)
                all_changed.append(tick)
            # Mark symbols in this chunk that DIDN'T respond
            for sym in chunk:
                if sym in responded:
                    continue
                self._failures[sym] = self._failures.get(sym, 0) + 1
                if self._failures[sym] >= SLOW_LANE_STRIKES:
                    self._demote_to_slow_lane(sym)
            await asyncio.sleep(0)
        return all_changed

    def _fetch_batch_sync(self, symbols: List[str]) -> List[Tick]:
        """Fetch prices for a batch using ``yf.Tickers`` (concurrent)."""
        if not symbols:
            return []
        results: List[Tick] = []
        yf_symbols = [s if s.endswith('.JK') else f'{s}.JK' for s in symbols]
        try:
            tickers = yf.Tickers(' '.join(yf_symbols))
        except Exception as exc:
            logger.debug('Tickers() init failed: %s', exc)
            return results
        for clean_sym, yf_sym in zip(symbols, yf_symbols):
            try:
                t = tickers.tickers.get(yf_sym)
                if t is None:
                    continue
                info = {}
                try:
                    info = t.fast_info or {}
                except Exception:
                    pass
                price = info.get('last_price') or info.get('regular_market_price')
                prev_close = info.get('previous_close')
                if not _valid_price(price):
                    hist = t.history(period='1d', interval='1m', timeout=3)
                    if not hist.empty:
                        price = float(hist['Close'].dropna().iloc[-1])
                        if not _valid_price(prev_close) and len(hist) >= 1:
                            prev_close = float(hist['Open'].dropna().iloc[0])
                if not _valid_price(price):
                    continue
                change = round(price - prev_close, 2) if prev_close else 0.0
                change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
                results.append(Tick(
                    symbol=clean_sym,
                    price=round(float(price), 2),
                    prev_close=round(float(prev_close), 2) if prev_close else None,
                    change=change,
                    change_pct=change_pct,
                    ts=time.time(),
                ))
            except Exception as exc:
                logger.debug('batch row %s failed: %s', yf_sym, exc)
                continue
        return results


# ── SSE serialization helpers ──

def sse_format(event: str, data: Any) -> bytes:
    """Format one Server-Sent-Events message.

    Format reference: https://html.spec.whatwg.org/multipage/server-sent-events.html
    """
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False, default=str)
    return f'event: {event}\ndata: {data}\n\n'.encode('utf-8')


# ── Generator for FastAPI StreamingResponse ──

async def stream_ticks(engine: TickerEngine) -> AsyncIterator[bytes]:
    """Yield SSE events to a single client until they disconnect.

    Sends a heartbeat comment every 15s so intermediate proxies don't kill
    the connection. Yields a snapshot first so the client gets a baseline
    immediately, then waits for new tick events.
    """
    queue = engine.subscribe()
    try:
        # Initial snapshot
        snap = engine.snapshot()
        yield sse_format('snapshot', snap)
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield b': heartbeat\n\n'
                continue
            if event is None:
                yield sse_format('end', {'reason': 'server-stopped'})
                return
            yield sse_format('tick', event)
    finally:
        engine.unsubscribe(queue)
