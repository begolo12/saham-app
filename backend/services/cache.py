"""Redis cache client — Upstash with fakeredis fallback."""

import asyncio
import json
import logging
import os
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger('saham-api')


class RedisClient:
    """Singleton Redis client.

    Tries Upstash (REDIS_URL env var) first, falls back to fakeredis in-memory
    if REDIS_URL is not set or connection fails.
    """

    _instance = None
    _client = None
    _upstash = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._client = None
        self._upstash = False
        self._init_client()

    def _init_client(self):
        redis_url = os.environ.get('REDIS_URL', '').strip()
        if redis_url:
            try:
                import redis as _redis
                kwargs = {'decode_responses': True}
                if redis_url.startswith('rediss://'):
                    kwargs['ssl'] = True
                self._client = _redis.from_url(redis_url, **kwargs)
                self._client.ping()
                self._upstash = True
                logger.info('RedisClient: connected to Upstash Redis')
                return
            except Exception as exc:
                logger.warning('RedisClient: Upstash connection failed (%s), falling back to fakeredis', exc)
        # Fallback to fakeredis
        try:
            import fakeredis as _fake
            self._client = _fake.FakeRedis(decode_responses=True)
            logger.info('RedisClient: using fakeredis (in-memory)')
        except Exception as exc:
            logger.warning('RedisClient: fakeredis unavailable (%s), running without cache', exc)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def is_upstash(self) -> bool:
        return self._upstash

    # ── Basic operations ──

    def get(self, key: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            return self._client.get(key)
        except Exception as exc:
            logger.debug('Redis get(%s) failed: %s', key, exc)
            return None

    def set(self, key: str, value: str, ttl: int = 300) -> bool:
        if not self._client:
            return False
        try:
            # Use SET with EX (replaces deprecated setex). Works on both
            # the real redis client and fakeredis.
            self._client.set(key, value, ex=ttl)
            return True
        except Exception as exc:
            logger.debug('Redis set(%s) failed: %s', key, exc)
            return False

    def delete(self, key: str) -> bool:
        if not self._client:
            return False
        try:
            return bool(self._client.delete(key))
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        if not self._client:
            return False
        try:
            return bool(self._client.exists(key))
        except Exception:
            return False

    # ── Typed helpers ──

    def get_json(self, key: str) -> Optional[Any]:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_json(self, key: str, value: Any, ttl: int = 300) -> bool:
        return self.set(key, _json_dumps(value), ttl)

    def get_or_set(self, key: str, fn: Callable[[], Any], ttl: int = 300) -> Any:
        """Return cached value if exists, otherwise call fn, cache result, return it."""
        cached = self.get_json(key)
        if cached is not None:
            return cached
        result = fn()
        if result is not None:
            self.set_json(key, result, ttl)
        return result

    # ── Stock data helpers (used by stock_service/worker) ──

    STALE_THRESHOLD = 3600  # 1 hour

    @staticmethod
    def _now_ts() -> float:
        import time
        return time.time()

    def get_stock_data(self, key: str) -> Optional[dict]:
        """Get cached stock data. Returns None if missing or stale beyond threshold."""
        raw = self.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        # Add stale flag if data is old
        ts = data.get('_cached_at', 0)
        if ts and (self._now_ts() - ts) > self.STALE_THRESHOLD:
            data['stale'] = True
        return data

    def set_stock_data(self, key: str, data: dict, ttl: int = 300) -> bool:
        """Cache stock data with timestamp for staleness tracking."""
        data['_cached_at'] = self._now_ts()
        data.setdefault('stale', False)
        return self.set_json(key, data, ttl)

    def set_stock_list(self, key: str, items: list, ttl: int = 300) -> bool:
        """Cache a list of stock dicts with timestamp."""
        payload = {'_cached_at': self._now_ts(), 'stale': False, 'items': items}
        return self.set_json(key, payload, ttl)

    def get_stock_list(self, key: str) -> Optional[list]:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        ts = payload.get('_cached_at', 0)
        if ts and (self._now_ts() - ts) > self.STALE_THRESHOLD:
            payload['stale'] = True
        items = payload.get('items', [])
        # Propagate stale to each item
        if payload.get('stale'):
            for item in items:
                if isinstance(item, dict):
                    item['stale'] = True
        return items


def _json_dumps(obj: Any) -> str:
    """JSON dumps with default str for non-serialisable types (Timestamps, etc)."""
    return json.dumps(obj, default=str, ensure_ascii=False)


# ── Decorator ──

def cached(prefix: str, ttl: int = 300):
    """Decorator: cache function result in Redis.

    Key format: ``prefix:arg1:arg2:kwarg1=val1``

    Works for both sync and async functions. Skips caching if Redis unavailable.
    """
    def decorator(fn):
        _is_async = asyncio.iscoroutinefunction(fn)

        def _make_key(args, kwargs) -> str:
            parts = [prefix]
            parts.extend(str(a) for a in args)
            parts.extend(f'{k}={v}' for k, v in sorted(kwargs.items()))
            return ':'.join(parts)

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            client = _get_client()
            if not client.available:
                return await fn(*args, **kwargs)
            key = _make_key(args, kwargs)
            cached_val = client.get_json(key)
            if cached_val is not None:
                return cached_val
            result = await fn(*args, **kwargs)
            if result is not None:
                client.set_json(key, result, ttl)
            return result

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            client = _get_client()
            if not client.available:
                return fn(*args, **kwargs)
            key = _make_key(args, kwargs)
            cached_val = client.get_json(key)
            if cached_val is not None:
                return cached_val
            result = fn(*args, **kwargs)
            if result is not None:
                client.set_json(key, result, ttl)
            return result

        return async_wrapper if _is_async else sync_wrapper
    return decorator


def _get_client() -> RedisClient:
    return RedisClient()
