"""Tests for BackgroundWorker — start/stop lifecycle + periodic task invocation."""

import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest

from services.worker import BackgroundWorker, get_worker, INTERVAL_TOP_STOCKS, INTERVAL_MARKET_SUMMARY


class TestWorkerLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_expected_tasks(self):
        w = BackgroundWorker()
        assert w._running is False
        assert w._tasks == []
        await w.start()
        assert w._running is True
        # Should spawn 4 periodic tasks
        assert len(w._tasks) == 4
        names = sorted(t.get_name() for t in w._tasks)
        assert names == sorted([
            'worker-top-stocks', 'worker-all-stocks',
            'worker-market-summary', 'worker-backtest-tune',
        ])
        # Tasks are scheduled but may not have started — cancel cleanly
        await w.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        w = BackgroundWorker()
        await w.start()
        await asyncio.sleep(0.1)  # let them spin
        await w.stop()
        assert w._running is False
        assert w._tasks == []

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self):
        w = BackgroundWorker()
        await w.start()
        first = list(w._tasks)
        await w.start()  # should be no-op
        assert w._tasks == first
        await w.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_safe(self):
        w = BackgroundWorker()
        await w.stop()  # should not raise
        assert w._tasks == []


class TestWorkerRefreshes:
    @pytest.mark.asyncio
    async def test_refresh_top_stocks_writes_to_redis(self):
        w = BackgroundWorker()
        with patch.object(w, '_redis') as mock_redis, \
             patch('services.worker.get_top_stocks', return_value=[{'symbol': 'BBCA.JK', 'price': 1}] * 5):
            await w.refresh_top_stocks()
            mock_redis.set_stock_list.assert_called_once()
            args, kwargs = mock_redis.set_stock_list.call_args
            assert args[0] == 'stocks:top'
            assert len(args[1]) == 5

    @pytest.mark.asyncio
    async def test_refresh_top_stocks_handles_empty(self):
        w = BackgroundWorker()
        with patch.object(w, '_redis') as mock_redis, \
             patch('services.worker.get_top_stocks', return_value=[]):
            await w.refresh_top_stocks()
            mock_redis.set_stock_list.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_top_stocks_handles_exception(self):
        w = BackgroundWorker()
        with patch('services.worker.get_top_stocks', side_effect=RuntimeError('network')):
            # Should not raise — error logged by the run_loop, but direct call lets it bubble
            with pytest.raises(RuntimeError):
                await w.refresh_top_stocks()

    @pytest.mark.asyncio
    async def test_run_loop_invokes_refresh_and_sleeps(self, monkeypatch):
        """Direct test of _run_loop: should call refresh once then exit when cancelled.

        Note: _run_loop does an initial stagger sleep, so total sleep_calls = 2
        (1 stagger + 1 interval after first refresh).
        """
        w = BackgroundWorker()
        w._running = True
        call_count = {'n': 0}

        async def fake_refresh():
            call_count['n'] += 1

        # Patch asyncio.sleep to cancel after the post-refresh interval sleep
        sleep_calls = {'n': 0}
        real_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            sleep_calls['n'] += 1
            # Stop the loop only on the second sleep (the one after first refresh)
            if sleep_calls['n'] >= 2:
                w._running = False
            return await real_sleep(0)

        monkeypatch.setattr('services.worker.asyncio.sleep', fake_sleep)
        await w._run_loop('test', 0.01, fake_refresh)
        assert call_count['n'] == 1
        # 1 stagger sleep + 1 interval sleep = 2
        assert sleep_calls['n'] == 2

    @pytest.mark.asyncio
    async def test_run_loop_continues_after_refresh_error(self, monkeypatch):
        w = BackgroundWorker()
        w._running = True
        call_count = {'n': 0}

        async def flaky():
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise RuntimeError('boom')

        sleep_calls = {'n': 0}

        async def fake_sleep(_):
            sleep_calls['n'] += 1
            # Stop only after the second post-refresh interval (3rd sleep total:
            # 1 stagger + 2 intervals)
            if sleep_calls['n'] >= 3:
                w._running = False

        monkeypatch.setattr('services.worker.asyncio.sleep', fake_sleep)
        await w._run_loop('flaky', 0.001, flaky)
        # Should be called twice — once errored, once succeeded
        assert call_count['n'] == 2
        assert sleep_calls['n'] == 3


class TestWorkerSingleton:
    def test_get_worker_returns_singleton(self):
        # Reset module singleton for test isolation
        import services.worker as wmod
        wmod._worker = None
        a = get_worker()
        b = get_worker()
        assert a is b
        # Cleanup
        wmod._worker = None

    def test_intervals_are_positive(self):
        assert INTERVAL_TOP_STOCKS > 0
        assert INTERVAL_MARKET_SUMMARY > 0


class TestWorkerPeriodicInterval:
    @pytest.mark.asyncio
    async def test_short_interval_triggers_multiple_refreshes(self, monkeypatch):
        """With a 0.01s interval and 0.05s budget, expect multiple refresh calls."""
        w = BackgroundWorker()
        w._running = True
        call_count = {'n': 0}

        async def tick():
            call_count['n'] += 1

        real_sleep = asyncio.sleep

        async def fast_sleep(_):
            await real_sleep(0.001)
            # Stop after ~5 calls
            if call_count['n'] >= 5:
                w._running = False

        monkeypatch.setattr('services.worker.asyncio.sleep', fast_sleep)
        await w._run_loop('rapid', 0.001, tick)
        assert call_count['n'] >= 5
