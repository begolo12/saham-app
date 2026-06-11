import hashlib
import hmac
import base64
import secrets
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# NOTE: Do NOT import AUTH_SECRET at module level — test fixtures reload
# services.db with a test secret, and a module-level capture would freeze
# the original value. Always import from services.db lazily at call time.
from services import db as _db

ACCESS_TOKEN_TTL = 15 * 60          # 15 menit
REFRESH_TOKEN_TTL_DAYS = 30         # 30 hari


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _sign_token(payload: str) -> str:
    return _b64url(
        hmac.new(
            _db.AUTH_SECRET.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256,
        ).digest()
    )


def _make_access_token(user: Dict[str, Any]) -> str:
    exp = int(time.time()) + ACCESS_TOKEN_TTL
    payload = f"{user['id']}.{exp}"
    return f"{payload}.{_sign_token(payload)}"


def _make_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _store_refresh_token(user_id: int, refresh_token: str):
    expiry = int(time.time()) + REFRESH_TOKEN_TTL_DAYS * 86400
    with _db._db_conn() as conn:
        conn.execute(
            'UPDATE app_users SET refresh_token = ?, refresh_token_expiry = ? WHERE id = ?',
            (refresh_token, expiry, user_id),
        )
        conn.commit()


def _validate_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate a refresh token via exact match against the stored value.

    Stored columns: ``refresh_token`` (raw token) and ``refresh_token_expiry``
    (unix seconds). Exact match + index-backed O(1) lookup, then verify the
    expiry. This avoids both the full-table scan of the old query and the
    prefix-collision risk of the previous ``startswith`` check.
    """
    if not token:
        return None
    with _db._db_conn() as conn:
        row = conn.execute(
            'SELECT id, username, role, refresh_token, refresh_token_expiry '
            'FROM app_users WHERE refresh_token = ?',
            (token,),
        ).fetchone()
    if not row:
        return None
    try:
        exp = int(row['refresh_token_expiry'] or 0)
    except (TypeError, ValueError):
        return None
    if not exp or int(time.time()) > exp:
        return None
    return _db._get_user_by_id(row['id'])


def login(username: str, password: str) -> Optional[Dict[str, Any]]:
    user = _db._get_user_by_credentials(username, password)
    if not user:
        return None
    access_token = _make_access_token(user)
    refresh_token = _make_refresh_token()
    _store_refresh_token(user['id'], refresh_token)
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token': access_token,
        'user': {'id': user['id'], 'username': user['username'], 'role': user['role']},
    }


def refresh(refresh_token: str) -> Optional[Dict[str, Any]]:
    user = _validate_refresh_token(refresh_token)
    if not user:
        return None
    access_token = _make_access_token(user)
    return {'access_token': access_token, 'token': access_token}


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    return _db._verify_token(token)
