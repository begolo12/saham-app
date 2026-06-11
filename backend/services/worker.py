"""Background worker for auto-refreshing stock data into Redis."""

import asyncio
import logging
import time
from typing import List, Optional

from services.cache import RedisClient
from stock_data import get_top_stocks

logger = logging.getLogger('saham-api')

# ── Refresh intervals (seconds) ──
INTERVAL_TOP_STOCKS = 300      # 5 min
INTERVAL_ALL_STOCKS = 900      # 15 min
INTERVAL_MARKET_SUMMARY = 60   # 1 min
INTERVAL_BACKTEST_TUNE = 6 * 60 * 60   # 6 hours — periodic weight tuning


class BackgroundWorker:
    """Periodic stock data refresher.

    Runs as long-lived asyncio tasks. Start via ``start()``, stop via ``stop()``.
    Each refresh writes results into Redis with appropriate TTL, so API endpoints
    read from cache instead of calling yfinance.
    """

    def __init__(self):
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._redis = RedisClient()

    # ── Lifecycle ──

    async def start(self):
        """Launch background refresh tasks."""
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._run_loop('top-stocks',    INTERVAL_TOP_STOCKS,      self.refresh_top_stocks),      name='worker-top-stocks'),
            asyncio.create_task(self._run_loop('all-stocks',    INTERVAL_ALL_STOCKS,      self.refresh_all_stocks),      name='worker-all-stocks'),
            asyncio.create_task(self._run_loop('market-summary', INTERVAL_MARKET_SUMMARY, self.refresh_market_summary),  name='worker-market-summary'),
            asyncio.create_task(self._run_loop('backtest-tune', INTERVAL_BACKTEST_TUNE,  self.refresh_backtest_tune),   name='worker-backtest-tune'),
        ]
        logger.info('BackgroundWorker: started %d tasks', len(self._tasks))

    async def stop(self):
        """Cancel all background tasks."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()
        logger.info('BackgroundWorker: stopped')

    async def _run_loop(self, name: str, interval: int, refresh_fn):
        """Periodically call *refresh_fn*, then sleep *interval* seconds."""
        # Initial run after short stagger to let app start
        stagger = sum(hash(c) for c in name) % 5
        await asyncio.sleep(stagger)
        while self._running:
            try:
                logger.debug('Worker[%s]: refreshing …', name)
                t0 = time.time()
                await refresh_fn()
                elapsed = time.time() - t0
                logger.info('Worker[%s]: done in %.1fs', name, elapsed)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error('Worker[%s]: error: %s', name, exc, exc_info=True)
            await asyncio.sleep(interval)

    # ── Refresh methods ──

    async def refresh_top_stocks(self):
        """Fetch top 30 stocks, cache in Redis with 5 min TTL."""
        loop = asyncio.get_event_loop()
        stocks = await loop.run_in_executor(None, lambda: get_top_stocks()[:30])
        if stocks:
            self._redis.set_stock_list('stocks:top', stocks, ttl=INTERVAL_TOP_STOCKS)
            logger.info('Cached %d top stocks', len(stocks))

    async def refresh_all_stocks(self):
        """Fetch all tracked stocks, cache with 15 min TTL."""
        loop = asyncio.get_event_loop()
        # Limit to MAX_UNIVERSE (140) which is existing stock_data behaviour
        stocks = await loop.run_in_executor(None, lambda: get_top_stocks())
        if stocks:
            self._redis.set_stock_list('stocks:all', stocks, ttl=INTERVAL_ALL_STOCKS)
            logger.info('Cached %d stocks in universe', len(stocks))

    async def refresh_market_summary(self):
        """Fetch IHSG market summary, cache with 1 min TTL."""
        import yfinance as yf
        import pandas as pd
        from services.db import _now_iso

        now = time.time()
        fallback_data = {
            'name': 'IHSG — Indeks Harga Saham Gabungan',
            'symbol': '^JKSE',
            'price': None, 'change': 0, 'change_percent': 0,
            'high_52w': 9174.474, 'low_52w': 4500.0,
            'volume': 0, 'updated_at': _now_iso(), 'stale': True,
        }
        try:
            ihsg = yf.Ticker('^JKSE')
            info_data = {}
            try:
                info_data = ihsg.fast_info or {}
            except Exception:
                pass
            intraday = ihsg.history(period='1d', interval='1m', timeout=3)
            history = pd.DataFrame()
            if intraday.empty:
                history = ihsg.history(period='5d', timeout=3)

            current_price = None
            prev_close = None
            if not intraday.empty:
                closes = intraday['Close'].dropna()
                opens = intraday['Open'].dropna()
                if len(closes) and len(opens):
                    current_price = float(closes.iloc[-1])
                    prev_close = float(opens.iloc[0])
            def _valid(v):
                try:
                    return 4500 <= float(v) <= 9500
                except Exception:
                    return False
            if not _valid(current_price):
                current_price = info_data.get('last_price') or info_data.get('regular_market_price')
            if not _valid(current_price) and not history.empty:
                current_price = float(history['Close'].dropna().iloc[-1])
            if not _valid(prev_close):
                prev_close = info_data.get('previous_close')
            if not _valid(prev_close) and len(history) >= 2:
                prev_close = float(history['Close'].dropna().iloc[-2])
            if not _valid(current_price):
                current_price = None

            change_val = 0.0
            change_pct = 0.0
            if prev_close and current_price:
                change_val = round(current_price - prev_close, 2)
                change_pct = round((change_val / prev_close) * 100, 2)

            result = {
                'name': 'IHSG — Indeks Harga Saham Gabungan',
                'symbol': '^JKSE',
                'price': current_price,
                'change': change_val,
                'change_percent': change_pct,
                'high_52w': (info_data.get('year_high') or info_data.get('fiftyTwoWeekHigh') or fallback_data['high_52w']),
                'low_52w': (info_data.get('year_low') or info_data.get('fiftyTwoWeekLow') or fallback_data['low_52w']),
                'volume': (info_data.get('last_volume') or info_data.get('volume') or 0),
                'updated_at': _now_iso(),
            }
            self._redis.set_json('market:summary', result, ttl=INTERVAL_MARKET_SUMMARY)
        except Exception as exc:
            logger.warning('Worker[market-summary] fetch failed: %s', exc)
            self._redis.set_json('market:summary', fallback_data, ttl=INTERVAL_MARKET_SUMMARY)

    async def refresh_backtest_tune(self):
        """Run periodic weight-tuning backtest (S2b).

        Picks symbols that have at least one entry in ``signal_recommendations``
        and runs the grid-search weight tuner. Updates ``signal_weights`` for
        each picked symbol based on recent performance and logs a summary.
        Designed to be safe on empty data (no-op when no symbols found).
        """
        loop = asyncio.get_event_loop()
        try:
            symbols = await loop.run_in_executor(None, _pick_symbols_with_recommendations)
        except Exception as exc:
            logger.warning('Worker[backtest-tune] symbol lookup failed: %s', exc)
            return

        if not symbols:
            logger.info('Worker[backtest-tune]: no symbols with signal_recommendations; skipping')
            return

        try:
            from scripts.tune_weights import run_tune
        except ImportError as exc:
            logger.warning('Worker[backtest-tune] could not import tune_weights: %s', exc)
            return

        try:
            summary = await loop.run_in_executor(
                None,
                lambda: run_tune(days=180, symbols=symbols, top_n=len(symbols)),
            )
        except Exception as exc:
            logger.error('Worker[backtest-tune] tune failed: %s', exc, exc_info=True)
            return

        # Console summary
        if isinstance(summary, dict):
            best_w = summary.get('best_weights') or {}
            best_m = summary.get('best_metrics') or {}
            logger.info(
                'Worker[backtest-tune] complete: symbols=%d windows=%d win_rate=%.2f%% '
                'avg_return=%.2f%% sharpe=%.4f weights=TA=%.2f Fund=%.2f Sent=%.2f '
                'Vol=%.2f Regime=%.2f',
                summary.get('symbols_tuned', 0),
                summary.get('windows_evaluated', 0),
                float(best_m.get('win_rate', 0)),
                float(best_m.get('avg_return', 0)),
                float(best_m.get('sharpe_ratio', 0)),
                float(best_w.get('ta_weight', 0)),
                float(best_w.get('fund_weight', 0)),
                float(best_w.get('sent_weight', 0)),
                float(best_w.get('vol_weight', 0)),
                float(best_w.get('regime_weight', 0)),
            )


# ── Module helpers ──

def _pick_symbols_with_recommendations(limit: int = 50) -> List[str]:
    """Return distinct symbols that have at least one signal_recommendation.

    Used by the periodic backtest/tune task. Safe on empty tables.
    """
    try:
        from services.db import _db_conn
        with _db_conn() as conn:
            rows = conn.execute(
                '''SELECT symbol, COUNT(*) as cnt FROM signal_recommendations
                   GROUP BY symbol
                   ORDER BY cnt DESC
                   LIMIT ?''',
                (limit,),
            ).fetchall()
        return [r['symbol'] for r in rows if r['symbol']]
    except Exception as exc:
        logger.debug('_pick_symbols_with_recommendations failed: %s', exc)
        return []


# Module-level singleton
_worker: Optional[BackgroundWorker] = None


def get_worker() -> BackgroundWorker:
    global _worker
    if _worker is None:
        _worker = BackgroundWorker()
    return _worker
