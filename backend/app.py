"""FastAPI application entry — middleware, lifespan, error handlers."""

import html
import json
import logging
import math
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger('saham-api')


# ── S17: NaN/Inf-safe JSON encoder ──
# Last-resort defence: any float that slipped through as NaN / +Inf / -Inf
# becomes ``None`` so the response is always JSON-compliant. Used by the
# custom JSONResponse class below.
def _scrub_nan_inf(value):
    """Recursively replace NaN / +Inf / -Inf floats with ``None``.

    Walks dicts, lists, and tuples. Non-finite floats must be stripped
    BEFORE handing the payload to ``json.dumps`` — the C encoder raises
    ``ValueError: Out of range float values are not JSON compliant`` before
    ever consulting ``JSONEncoder.default()``, so a ``default()`` override
    alone is not enough.
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _scrub_nan_inf(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_nan_inf(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_scrub_nan_inf(v) for v in value)
    return value


def _dumps_safe(payload) -> bytes:
    return json.dumps(
        _scrub_nan_inf(payload),
        ensure_ascii=False,
        allow_nan=False,  # defence-in-depth: should be clean already
    ).encode('utf-8')


class SafeJSONResponse(JSONResponse):
    """JSONResponse subclass that tolerates NaN/Inf in the payload.

    A regular ``JSONResponse`` raises ``ValueError: Out of range float values
    are not JSON compliant`` when the payload contains a NaN. This subclass
    strips them out as ``None`` so endpoints always render a 200.
    """

    def render(self, content) -> bytes:
        try:
            return super().render(content)
        except ValueError:
            logger.warning('NaN/Inf detected in response payload — sanitizing')
            return _dumps_safe(content)

# ── Sentry (optional) ──
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    _sentry_dsn = os.environ.get('SENTRY_DSN', '').strip()
    if _sentry_dsn:
        sentry_sdk.init(
            dsn=_sentry_dsn,
            integrations=[FastApiIntegration()],
            traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
            environment=os.environ.get('SENTRY_ENV', os.environ.get('ENV', 'development')),
            send_default_pii=False,
        )
        logger.info('Sentry initialised (env=%s)', os.environ.get('SENTRY_ENV', 'development'))
except Exception as _sentry_exc:  # never let Sentry init break startup
    logger.debug('Sentry not initialised: %s', _sentry_exc)


def sanitize_message(text: str) -> str:
    """HTML-escape user-supplied text before reflecting it in error messages.

    Prevents stored/reflected XSS via error detail strings.
    """
    if text is None:
        return ''
    try:
        return html.escape(str(text), quote=True)
    except Exception:
        return ''


# ── Rate limiter (simple in-memory sliding window) ──
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 200    # requests per window
_rate_limit_store: dict = {}

# ── Login-specific rate limit (5 req / min per IP) ──
_LOGIN_RATE_LIMIT_WINDOW = 60
_LOGIN_RATE_LIMIT_MAX = 5
_login_rate_store: dict = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == '/health':
            return await call_next(request)

        client_ip = request.client.host if request.client else 'unknown'
        now = time.time()
        window_key = int(now / _RATE_LIMIT_WINDOW)
        key = f'{client_ip}:{window_key}'

        count = _rate_limit_store.get(key, 0)
        if count >= _RATE_LIMIT_MAX:
            logger.warning('Rate limit exceeded for %s', client_ip)
            return JSONResponse(
                status_code=429,
                content={'detail': 'Too many requests. Silakan coba lagi nanti.'},
            )
        _rate_limit_store[key] = count + 1
        return await call_next(request)


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Stricter rate limit for /api/auth/login (5 req/min per IP).

    Brute-force protection. Failed-login lockout would be a follow-up.
    """
    async def dispatch(self, request: Request, call_next):
        if request.url.path != '/api/auth/login' or request.method != 'POST':
            return await call_next(request)
        client_ip = request.client.host if request.client else 'unknown'
        now = time.time()
        window_key = int(now / _LOGIN_RATE_LIMIT_WINDOW)
        key = f'login:{client_ip}:{window_key}'
        count = _login_rate_store.get(key, 0)
        if count >= _LOGIN_RATE_LIMIT_MAX:
            logger.warning('Login rate limit exceeded for %s', client_ip)
            return JSONResponse(
                status_code=429,
                content={'detail': 'Terlalu banyak percobaan login. Coba lagi dalam 1 menit.'},
            )
        _login_rate_store[key] = count + 1
        return await call_next(request)


# ── Security headers middleware ──
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        # HSTS — only set when serving over HTTPS (via proxy header)
        if request.headers.get('x-forwarded-proto') == 'https' or request.url.scheme == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response


# ── Request size limit middleware (1 MB) ──
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > 1_048_576:
            return JSONResponse(
                status_code=413,
                content={'detail': 'Request terlalu besar. Maksimal 1 MB.'},
            )
        return await call_next(request)


# ── CORS origins (env-driven whitelist) ──
def _get_cors_origins() -> list:
    """Build CORS origin whitelist from env var SAHAM_CORS_ORIGINS (comma-separated).

    Defaults to localhost dev ports. Wildcard '*' is only allowed when
    SAHAM_CORS_ALLOW_ALL=1 (mobile app scenario).
    """
    raw = os.environ.get('SAHAM_CORS_ORIGINS', '').strip()
    if os.environ.get('SAHAM_CORS_ALLOW_ALL') == '1':
        return ['*']
    if raw:
        return [o.strip() for o in raw.split(',') if o.strip()]
    # Sensible dev defaults
    return [
        'http://localhost:5180',
        'http://localhost:5173',
        'http://127.0.0.1:5180',
        'http://127.0.0.1:5173',
    ]


# ── Lifespan (startup / shutdown) ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background worker on startup, stop on shutdown."""
    # Init Redis client singleton (lazy — first access initialises)
    from services.cache import RedisClient
    rc = RedisClient()
    if rc.available:
        logger.info('Redis cache initialized (%s)', 'Upstash' if rc.is_upstash else 'fakeredis')
    else:
        logger.warning('Redis not available — running without cache')

    # Start background worker
    from services.worker import get_worker
    worker = get_worker()
    await worker.start()
    logger.info('Background worker started')
    yield
    await worker.stop()
    logger.info('Background worker stopped')


# ── FastAPI app ──
app = FastAPI(
    title='SahamApp - Indonesian Stock Analysis API',
    description='Backend API untuk analisis saham Indonesia',
    version='1.0.0',
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
)

# CORS — env-driven whitelist (see _get_cors_origins)
_cors_origins = _get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'Accept', 'X-Requested-With'],
    expose_headers=['X-RateLimit-Remaining'],
    max_age=600,
)

# Security middleware stack — order matters: rate-limit outermost
app.add_middleware(LoginRateLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)


# ── Global error handling middleware ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a clean 500 response.

    Reports to Sentry when configured.
    """
    logger.error('Unhandled error on %s %s: %s', request.method, request.url, exc, exc_info=True)
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={'detail': 'Internal server error. Please try again later.'},
    )


# Import routes to register them on the app
from routes import stocks, auth, portfolio, learning, news, market, accuracy  # noqa: E402

# Run DB migrations at startup
from services.migration import run_migrations  # noqa: E402
run_migrations()
