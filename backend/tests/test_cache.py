"""Tests for RedisClient — get/set/delete, fakeredis fallback, JSON serialization."""

import json
import os
import time
from unittest.mock import patch

import pytest


@pytest.fixture
def fresh_redis(monkeypatch):
    """Return a fresh RedisClient singleton instance (resets class state)."""
    monkeypatch.delenv('REDIS_URL', raising=False)
    from services import cache as cache_mod
    cache_mod.RedisClient._instance = None
    cache_mod.RedisClient._client = None
    cache_mod.RedisClient._upstash = False
    rc = cache_mod.RedisClient()
    yield rc
    cache_mod.RedisClient._instance = None


class TestRedisClientBasic:
    def test_available_uses_fakeredis_by_default(self, fresh_redis):
        # No REDIS_URL env → fakeredis fallback
        assert fresh_redis.available is True
        assert fresh_redis.is_upstash is False

    def test_set_and_get_string(self, fresh_redis):
        assert fresh_redis.set('foo', 'bar') is True
        assert fresh_redis.get('foo') == 'bar'

    def test_set_with_ttl(self, fresh_redis):
        fresh_redis.set('ttl_key', 'value', ttl=1)
        assert fresh_redis.get('ttl_key') == 'value'

    def test_delete_existing_key(self, fresh_redis):
        fresh_redis.set('k', 'v')
        assert fresh_redis.delete('k') is True
        assert fresh_redis.get('k') is None

    def test_delete_missing_key(self, fresh_redis):
        assert fresh_redis.delete('never-existed') is False

    def test_exists(self, fresh_redis):
        fresh_redis.set('present', '1')
        assert fresh_redis.exists('present') is True
        assert fresh_redis.exists('absent') is False

    def test_get_missing_key_returns_none(self, fresh_redis):
        assert fresh_redis.get('nope') is None


class TestRedisClientJson:
    def test_set_json_and_get_json_roundtrip(self, fresh_redis):
        payload = {'a': 1, 'b': [2, 3], 'c': 'unicode-emoji-🇮🇩'}
        assert fresh_redis.set_json('obj', payload) is True
        out = fresh_redis.get_json('obj')
        assert out == payload

    def test_get_json_handles_unicode(self, fresh_redis):
        # ensure_ascii=False path
        fresh_redis.set_json('uni', {'name': 'IHSG — Indeks'})
        assert fresh_redis.get_json('uni')['name'] == 'IHSG — Indeks'

    def test_get_json_returns_none_for_garbage(self, fresh_redis):
        fresh_redis.set('bad', '{not json}')
        assert fresh_redis.get_json('bad') is None

    def test_set_json_serializes_pandas_timestamp(self, fresh_redis):
        # ensure_ascii=False + default=str path (Timestamps / datetimes)
        import datetime as dt
        payload = {'ts': dt.datetime(2026, 6, 11, 12, 0, 0), 'n': 1}
        fresh_redis.set_json('ts', payload)
        out = fresh_redis.get_json('ts')
        assert out['n'] == 1
        assert '2026' in out['ts']

    def test_get_or_set_miss_then_hit(self, fresh_redis):
        calls = []

        def factory():
            calls.append(1)
            return {'value': 42}
        # First call → miss, factory invoked
        assert fresh_redis.get_or_set('k', factory) == {'value': 42}
        assert len(calls) == 1
        # Second call → hit, factory not invoked
        assert fresh_redis.get_or_set('k', factory) == {'value': 42}
        assert len(calls) == 1

    def test_get_or_set_skips_caching_none(self, fresh_redis):
        calls = []

        def factory_none():
            calls.append(1)
            return None
        assert fresh_redis.get_or_set('k', factory_none) is None
        # Should call factory again on next miss (None not cached)
        assert fresh_redis.get_or_set('k', factory_none) is None
        assert len(calls) == 2


class TestRedisClientStockHelpers:
    def test_set_stock_data_injects_cached_at(self, fresh_redis):
        fresh_redis.set_stock_data('BBCA.JK', {'price': 10250})
        raw = fresh_redis.get('BBCA.JK')
        data = json.loads(raw)
        assert '_cached_at' in data
        assert data['stale'] is False

    def test_get_stock_data_returns_dict(self, fresh_redis):
        fresh_redis.set_stock_data('BBCA.JK', {'price': 10250, 'name': 'BCA'})
        out = fresh_redis.get_stock_data('BBCA.JK')
        assert out['price'] == 10250
        assert out['name'] == 'BCA'
        assert out['stale'] is False

    def test_get_stock_data_marks_stale_after_threshold(self, fresh_redis, monkeypatch):
        # Set with old timestamp
        import time as time_mod
        old_ts = time_mod.time() - 7200  # 2 hours ago
        fresh_redis._client.set('STALE.JK', json.dumps({'_cached_at': old_ts, 'stale': False, 'price': 1}))
        out = fresh_redis.get_stock_data('STALE.JK')
        assert out['stale'] is True

    def test_set_stock_list_and_get_stock_list(self, fresh_redis):
        items = [{'symbol': 'BBCA.JK', 'price': 1}, {'symbol': 'BBRI.JK', 'price': 2}]
        fresh_redis.set_stock_list('top', items, ttl=300)
        out = fresh_redis.get_stock_list('top')
        assert out == items
        assert all('stale' not in item for item in out)


class TestRedisClientFailurePaths:
    def test_set_returns_false_when_client_none(self, fresh_redis, monkeypatch):
        # Simulate no client available
        fresh_redis._client = None
        assert fresh_redis.set('k', 'v') is False
        assert fresh_redis.get('k') is None
        assert fresh_redis.delete('k') is False
        assert fresh_redis.exists('k') is False

    def test_upstash_branch_is_taken_when_redis_url_set(self, monkeypatch):
        """When REDIS_URL is set and a real connection is mocked, is_upstash=True."""
        from services import cache as cache_mod
        cache_mod.RedisClient._instance = None

        class _FakeRedis:
            def __init__(self, *a, **kw):
                self._calls = 0

            def ping(self):
                self._calls += 1
                return True

        monkeypatch.setenv('REDIS_URL', 'redis://example:6379/0')
        with patch('redis.from_url', return_value=_FakeRedis()) as _:
            rc = cache_mod.RedisClient()
            assert rc.is_upstash is True
            assert rc.available is True


class TestCachedDecorator:
    def test_decorator_caches_result(self, fresh_redis, monkeypatch):
        from services.cache import cached

        call_count = {'n': 0}

        @cached(prefix='decorator-test', ttl=60)
        def expensive(x):
            call_count['n'] += 1
            return {'x': x}
        # Force module-level helper to return our client
        monkeypatch.setattr('services.cache._get_client', lambda: fresh_redis)
        a = expensive(1)
        b = expensive(1)
        assert a == b == {'x': 1}
        assert call_count['n'] == 1

    def test_decorator_skips_cache_when_unavailable(self, monkeypatch):
        from services import cache as cache_mod

        class _Unavail:
            available = False
            def get_json(self, k): return None
            def set_json(self, k, v, ttl): return True

        call_count = {'n': 0}

        @cache_mod.cached(prefix='offline', ttl=60)
        def f(x):
            call_count['n'] += 1
            return x * 2
        monkeypatch.setattr('services.cache._get_client', lambda: _Unavail())
        assert f(3) == 6
        assert f(3) == 6
        # Without cache, every call invokes f
        assert call_count['n'] == 2
