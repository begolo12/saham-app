"""Routes package — every module exposes an ``app`` APIRouter mounted at /api."""

from . import auth, stocks, portfolio, learning, news, market, accuracy, ticker  # noqa: F401
