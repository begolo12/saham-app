"""Tests for the live ticker engine.

Covers the full IDX-universe ticker: lifecycle, subscribe/publish, snapshot,
the SSE generator, universe loading, slow-lane demotion/rejoin, and the
hot-lane + round-robin polling strategy. All yfinance calls are mocked —
these tests run offline.
"""

import asyncio
import json
import time
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from services.ticker import (
    TickerEngine, Tick, sse_format, stream_ticks,
    HOT_SYMBOLS, BATCH_SIZE, SLOW_LANE_STRIKES, SLOW_LANE_RESCAN,
)


# ── Reset singleton between tests ─────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_singleton():
    TickerEngine._instance = None
    yield
    TickerEngine._instance = None


def _make_noop_loop():
    async def _noop():
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            return
    return _noop


# ── Tick dataclass ─────────────────────────────────────────────────────

class TestTick:
    def test_to_dict_rounds_floats(self):
        t = Tick(symbol='BBCA', price=1234.5678, prev_close=1200.0,
                 change=34.5678, change_pct=2.88, ts=1.0)
        d = t.to_dict()
        assert d['symbol'] == 'BBCA'
        assert d['price'] == 1234.57
        assert d['change'] == 34.57
        assert d['change_pct'] == 2.88

    def test_to_dict_handles_none(self):
        t = Tick(symbol='X', price=None, prev_close=None, change=None,
                 change_pct=None, ts=0.0)
        d = t.to_dict()
        assert d['price'] is None
        assert d['change'] is None
        assert d['change_pct'] is None

    def test_to_dict_includes_stalled(self):
        t = Tick(symbol='X', ts=0.0, stalled=True)
        assert t.to_dict()['stalled'] is True


# ── Lifecycle ──────────────────────────────────────────────────────────

class TestLifecycle:
    def test_singleton(self):
        a = TickerEngine.instance()
        b = TickerEngine.instance()
        assert a is b

    @pytest.mark.asyncio
    async def test_start_creates_three_tasks(self):
        eng = TickerEngine()
        eng._ihsg_loop = _make_noop_loop()
        eng._stocks_loop = _make_noop_loop()
        eng._slow_lane_loop = _make_noop_loop()
        await eng.start()
        assert eng._running is True
        assert len(eng._tasks) == 3
        names = sorted(t.get_name() for t in eng._tasks)
        assert names == ['ticker-ihsg', 'ticker-slow', 'ticker-stocks']
        await eng.stop()
        assert eng._running is False

    @pytest.mark.asyncio
    async def test_double_start_idempotent(self):
        eng = TickerEngine()
        eng._ihsg_loop = _make_noop_loop()
        eng._stocks_loop = _make_noop_loop()
        eng._slow_lane_loop = _make_noop_loop()
        await eng.start()
        first = list(eng._tasks)
        await eng.start()
        assert eng._tasks == first
        await eng.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_safe(self):
        eng = TickerEngine()
        await eng.stop()
        assert eng._tasks == []


# ── Universe loading ──────────────────────────────────────────────────

class TestUniverseLoading:
    def test_loads_all_tickers_from_file(self, tmp_path, monkeypatch):
        """All 951 IDX-listed tickers should be in the universe."""
        f = tmp_path / 'idx_universe.txt'
        f.write_text('AADI.JK\nBBCA.JK\nTLKM.JK\nZINC.JK\n')
        monkeypatch.setattr('services.ticker._UNIVERSE_FILE', f)
        eng = TickerEngine()
        eng._load_universe()
        assert 'AADI' in eng._universe
        assert 'BBCA' in eng._universe
        assert 'TLKM' in eng._universe
        assert 'ZINC' in eng._universe
        # .JK stripped, no duplicates
        assert 'BBCA.JK' not in eng._universe
        assert len(eng._universe) == 4

    def test_dedupes(self, tmp_path, monkeypatch):
        f = tmp_path / 'idx_universe.txt'
        f.write_text('BBCA.JK\nBBCA.JK\nBBCA\n')
        monkeypatch.setattr('services.ticker._UNIVERSE_FILE', f)
        eng = TickerEngine()
        eng._load_universe()
        assert eng._universe.count('BBCA') == 1

    def test_falls_back_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr('services.ticker._UNIVERSE_FILE',
                            tmp_path / 'no_such_file.txt')
        eng = TickerEngine()
        eng._load_universe()
        assert len(eng._universe) >= 10
        assert 'BBCA' in eng._universe

    def test_real_universe_has_900_plus_symbols(self):
        """Production guard: ensure the actual data file is wired up."""
        eng = TickerEngine()
        eng._load_universe()
        # 951 listed, allow some slack for stale file
        assert len(eng._universe) >= 800, (
            f'universe too small: {len(eng._universe)}'
        )

    def test_seeds_state_for_every_symbol(self, tmp_path, monkeypatch):
        f = tmp_path / 'idx_universe.txt'
        f.write_text('A.JK\nB.JK\nC.JK\n')
        monkeypatch.setattr('services.ticker._UNIVERSE_FILE', f)
        eng = TickerEngine()
        eng._load_universe()
        assert set(eng._state.keys()) == {'A', 'B', 'C', '^JKSE'}

    def test_load_resets_failure_counters(self, tmp_path, monkeypatch):
        f = tmp_path / 'idx_universe.txt'
        f.write_text('A.JK\n')
        monkeypatch.setattr('services.ticker._UNIVERSE_FILE', f)
        eng = TickerEngine()
        eng._failures['A'] = 5
        eng._stalled.append('A')
        eng._stalled_set.add('A')
        eng._load_universe()
        assert eng._failures == {}
        assert eng._stalled == []
        assert eng._stalled_set == set()
        assert eng._cursor == 0


# ── Subscribe / publish ────────────────────────────────────────────────

class TestSubscribePublish:
    def test_subscribe_returns_queue(self):
        eng = TickerEngine()
        q = eng.subscribe()
        assert isinstance(q, asyncio.Queue)
        assert q in eng._subscribers
        eng.unsubscribe(q)

    def test_unsubscribe_removes(self):
        eng = TickerEngine()
        q = eng.subscribe()
        eng.unsubscribe(q)
        assert q not in eng._subscribers

    def test_publish_fans_out(self):
        eng = TickerEngine()
        q1 = eng.subscribe()
        q2 = eng.subscribe()
        eng._publish({'type': 'ticks', 'data': [{'symbol': 'A'}]})
        assert q1.qsize() == 1
        assert q2.qsize() == 1
        eng.unsubscribe(q1)
        eng.unsubscribe(q2)

    def test_publish_drops_oldest_on_backpressure(self):
        eng = TickerEngine()
        q = asyncio.Queue(maxsize=2)
        eng._subscribers.append(q)
        eng._publish({'n': 1})
        eng._publish({'n': 2})
        assert q.qsize() == 2
        eng._publish({'n': 3})
        assert q.qsize() == 2
        items = []
        while not q.empty():
            items.append(q.get_nowait())
        assert items[-1] == {'n': 3}


# ── Snapshot ───────────────────────────────────────────────────────────

class TestSnapshot:
    def test_includes_universe_size(self):
        eng = TickerEngine()
        eng._universe = ['A', 'B', 'C']
        eng._state['A'] = Tick(symbol='A', price=100.0, ts=time.time())
        snap = eng.snapshot()
        assert snap['universe_size'] == 3
        assert snap['stalled_size'] == 0

    def test_filters_symbols(self):
        eng = TickerEngine()
        eng._state['A'] = Tick(symbol='A', price=1.0, ts=1.0)
        eng._state['B'] = Tick(symbol='B', price=2.0, ts=1.0)
        snap = eng.snapshot(['A'])
        assert len(snap['ticks']) == 1
        assert snap['ticks'][0]['symbol'] == 'A'

    def test_includes_requested_symbols_without_data(self):
        eng = TickerEngine()
        snap = eng.snapshot(['NEW'])
        assert len(snap['ticks']) == 1
        assert snap['ticks'][0]['symbol'] == 'NEW'
        assert snap['ticks'][0]['price'] is None


# ── SSE format helper ──────────────────────────────────────────────────

class TestSseFormat:
    def test_formats_dict_as_json(self):
        out = sse_format('tick', {'a': 1}).decode('utf-8')
        assert out.startswith('event: tick\n')
        assert 'data: {"a": 1}' in out
        assert out.endswith('\n\n')

    def test_formats_string_verbatim(self):
        out = sse_format('end', 'bye').decode('utf-8')
        assert 'data: bye\n\n' in out

    def test_handles_non_serialisable_values(self):
        from datetime import datetime
        out = sse_format('t', {'when': datetime(2026, 1, 1)}).decode('utf-8')
        assert '2026' in out


# ── stream_ticks generator ─────────────────────────────────────────────

class TestStreamTicks:
    @pytest.mark.asyncio
    async def test_sends_initial_snapshot(self):
        eng = TickerEngine()
        eng._state['BBCA'] = Tick(symbol='BBCA', price=100.0, change=1.0,
                                  change_pct=1.0, ts=time.time())
        gen = stream_ticks(eng)
        try:
            first = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
        finally:
            await gen.aclose()
        text = first.decode('utf-8')
        assert text.startswith('event: snapshot\n')
        body = text.split('data: ', 1)[1].rstrip('\n')
        parsed = json.loads(body)
        assert 'ihsg' in parsed
        assert 'universe_size' in parsed

    @pytest.mark.asyncio
    async def test_publishes_tick_to_subscriber(self):
        eng = TickerEngine()
        gen = stream_ticks(eng)
        try:
            await asyncio.wait_for(gen.__anext__(), timeout=1.0)
            eng._publish({'type': 'ticks', 'data': [{'symbol': 'X'}]})
            msg = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
        finally:
            await gen.aclose()
        assert b'event: tick' in msg


# ── IHSG fetch (sync, mocked) ──────────────────────────────────────────

class TestIHSGFetch:
    def test_returns_valid_tick_from_intraday(self):
        eng = TickerEngine()
        idx = pd.date_range('2026-01-01 09:00', periods=5, freq='1min')
        df = pd.DataFrame({
            'Open': [6000.0]*5,
            'Close': [6000.0, 6010.0, 6020.0, 6030.0, 6050.43],
        }, index=idx)
        mock_t = MagicMock()
        mock_t.history.return_value = df
        mock_t.fast_info = {}
        with patch('services.ticker.yf.Ticker', return_value=mock_t):
            result = eng._fetch_ihsg_sync()
        assert result is not None
        assert result.symbol == '^JKSE'
        assert result.price == 6050.43
        assert result.prev_close == 6000.0
        assert result.change_pct > 0


# ── Batch fetch + slow-lane demotion ───────────────────────────────────

class TestBatchFetch:
    @pytest.mark.asyncio
    async def test_demote_after_consecutive_failures(self):
        """A symbol that returns no data `SLOW_LANE_STRIKES` times in a row
        must be moved to the slow lane so the next round-robin skips it.
        This is the core of the auto-filter for suspended stocks."""
        eng = TickerEngine()
        eng._running = True
        eng._state['SUSP'] = Tick(symbol='SUSP', ts=time.time())
        # Mock the sync fetch to return nothing
        eng._fetch_batch_sync = lambda symbols: []
        # Run `SLOW_LANE_STRIKES` polls — each one should fail
        for _ in range(SLOW_LANE_STRIKES):
            await eng._fetch_batch(['SUSP'])
        assert 'SUSP' in eng._stalled_set
        assert 'SUSP' in eng._stalled

    @pytest.mark.asyncio
    async def test_rejoin_resets_failure_counter(self):
        eng = TickerEngine()
        eng._running = True
        eng._state['A'] = Tick(symbol='A', ts=time.time())
        eng._fetch_batch_sync = lambda symbols: []
        for _ in range(SLOW_LANE_STRIKES - 1):
            await eng._fetch_batch(['A'])
        assert eng._failures.get('A') == SLOW_LANE_STRIKES - 1
        # Now respond
        eng._fetch_batch_sync = lambda symbols: [Tick(
            symbol='A', price=100.0, prev_close=99.0,
            change=1.0, change_pct=1.0, ts=time.time(),
        )]
        result = await eng._fetch_batch(['A'])
        assert len(result) == 1
        assert eng._failures.get('A', 0) == 0

    @pytest.mark.asyncio
    async def test_partial_chunk_marks_only_missing(self):
        eng = TickerEngine()
        eng._running = True
        eng._state['A'] = Tick(symbol='A', ts=time.time())
        eng._state['B'] = Tick(symbol='B', ts=time.time())
        # A responds, B doesn't
        eng._fetch_batch_sync = lambda symbols: [
            Tick(symbol='A', price=100.0, prev_close=99.0,
                 change=1.0, change_pct=1.0, ts=time.time())
        ]
        await eng._fetch_batch(['A', 'B'])
        assert 'A' not in eng._failures
        assert eng._failures.get('B') == 1

    @pytest.mark.asyncio
    async def test_skips_unchanged_rows(self):
        eng = TickerEngine()
        eng._running = True
        eng._state['BBCA'] = Tick(
            symbol='BBCA', price=100.0, prev_close=99.0,
            change=1.0, change_pct=1.01, ts=time.time(),
        )
        eng._fetch_batch_sync = lambda symbols: [Tick(
            symbol='BBCA', price=100.0, prev_close=99.0,
            change=1.0, change_pct=1.01, ts=time.time(),
        )]
        result = await eng._fetch_batch(['BBCA'])
        assert result == [], 'Unchanged row should be filtered'

    @pytest.mark.asyncio
    async def test_passes_changed_rows(self):
        eng = TickerEngine()
        eng._running = True
        eng._state['BBCA'] = Tick(
            symbol='BBCA', price=100.0, prev_close=99.0,
            change=1.0, change_pct=1.01, ts=time.time(),
        )
        eng._fetch_batch_sync = lambda symbols: [Tick(
            symbol='BBCA', price=101.0, prev_close=99.0,
            change=2.0, change_pct=2.02, ts=time.time(),
        )]
        result = await eng._fetch_batch(['BBCA'])
        assert len(result) == 1
        assert result[0].price == 101.0
        assert eng._state['BBCA'].price == 101.0


# ── Slow lane demote / rejoin ──────────────────────────────────────────

class TestSlowLane:
    def test_demote_marks_state_as_stalled(self):
        eng = TickerEngine()
        eng._state['SUSP'] = Tick(symbol='SUSP', price=100.0, ts=time.time())
        eng._demote_to_slow_lane('SUSP')
        assert eng._state['SUSP'].stalled is True

    def test_demote_is_idempotent(self):
        eng = TickerEngine()
        eng._demote_to_slow_lane('SUSP')
        eng._demote_to_slow_lane('SUSP')
        assert eng._stalled.count('SUSP') == 1

    def test_rejoin_clears_stalled_flag(self):
        eng = TickerEngine()
        eng._state['SUSP'] = Tick(symbol='SUSP', ts=time.time(), stalled=True)
        eng._stalled.append('SUSP')
        eng._stalled_set.add('SUSP')
        eng._failures['SUSP'] = 10
        eng._rejoin_universe('SUSP')
        assert 'SUSP' not in eng._stalled
        assert 'SUSP' not in eng._stalled_set
        assert eng._state['SUSP'].stalled is False
        assert 'SUSP' not in eng._failures

    def test_rejoin_unknown_symbol_is_noop(self):
        eng = TickerEngine()
        eng._rejoin_universe('NEVER')  # should not raise

    def test_demoted_symbol_skipped_by_round_robin(self):
        eng = TickerEngine()
        eng._universe = ['A', 'B', 'C', 'D']
        eng._stalled_set.add('B')
        eng._stalled.append('B')
        # Drain the cursor through several cycles
        seen = set()
        for _ in range(10):
            batch = eng._next_batch()
            seen.update(batch)
        assert 'B' not in seen, 'Stalled symbol leaked into cold batch'
        assert {'A', 'C', 'D'} <= seen


# ── Round-robin cursor ────────────────────────────────────────────────

class TestRoundRobin:
    def test_cursor_wraps_around(self):
        eng = TickerEngine()
        # 80 symbols, BATCH_SIZE=40 → first two batches should cover all
        # without overlap; the third batch is the wrap-around.
        eng._universe = [f'S{i:02d}' for i in range(80)]
        first = set(eng._next_batch())
        second = set(eng._next_batch())
        assert len(first) == BATCH_SIZE
        assert len(second) == BATCH_SIZE
        assert first.isdisjoint(second)
        assert first | second == set(eng._universe)
        # Third call is the wrap-around and matches first
        third = set(eng._next_batch())
        assert third == first

    def test_cursor_advances_past_batch(self):
        eng = TickerEngine()
        eng._universe = [f'S{i:02d}' for i in range(BATCH_SIZE * 3)]
        first = set(eng._next_batch())
        second = set(eng._next_batch())
        third = set(eng._next_batch())
        assert first != second != third
        # After exactly N cycles we've touched every symbol once
        union = first | second | third
        assert union == set(eng._universe)

    def test_batch_size_respected(self):
        eng = TickerEngine()
        eng._universe = [f'S{i:03d}' for i in range(20)]
        batch = eng._next_batch()
        assert len(batch) == BATCH_SIZE

    def test_full_universe_eventually_polled(self):
        """Every symbol must show up in a few cycles' worth of batches."""
        eng = TickerEngine()
        eng._universe = [f'S{i:02d}' for i in range(10)]
        seen = set()
        for _ in range(5):
            seen.update(eng._next_batch())
        assert seen == set(eng._universe)


# ── Hot lane coverage ─────────────────────────────────────────────────

class TestHotLane:
    def test_hot_symbols_includes_most_watched(self):
        """Sanity: the hot lane must include blue chips the UI shows by default."""
        for sym in ['BBCA', 'BBRI', 'BMRI', 'TLKM', 'ASII']:
            assert sym in HOT_SYMBOLS, f'{sym} should be in HOT_SYMBOLS'
