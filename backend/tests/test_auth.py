"""Tests for auth endpoints: login, refresh, verify_token (unit + integration)."""

import time
from unittest.mock import patch

import pytest


# ── Unit tests for token verify (no DB / no app) ──


class TestVerifyToken:
    def _fresh_token(self, user_id=1, ttl=900, secret=None):
        from services.db import _sign_token, AUTH_SECRET
        sec = secret if secret is not None else AUTH_SECRET
        exp = int(time.time()) + ttl
        payload = f"{user_id}.{exp}"
        # Use the same signing path; tests should not duplicate the algorithm.
        import hmac, hashlib
        sig = __import__('base64').urlsafe_b64encode(
            hmac.new(sec.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()
        ).decode('ascii').rstrip('=')
        return f"{payload}.{sig}"

    def test_valid_token_returns_user(self):
        with patch('services.db._get_user_by_id', return_value={'id': 1, 'username': 'admin', 'role': 'superadmin', 'created_at': 'now'}):
            from services.db import _verify_token
            tok = self._fresh_token(user_id=1)
            user = _verify_token(tok)
            assert user is not None
            assert user['id'] == 1
            assert user['role'] == 'superadmin'

    def test_expired_token_returns_none(self):
        from services.db import _verify_token
        tok = self._fresh_token(user_id=1, ttl=-10)
        assert _verify_token(tok) is None

    def test_tampered_signature_returns_none(self):
        from services.db import _verify_token
        tok = self._fresh_token(user_id=1)
        # Flip one char in the signature
        head, exp, sig = tok.split('.')
        bad_sig = ('A' if sig[0] != 'A' else 'B') + sig[1:]
        assert _verify_token(f"{head}.{exp}.{bad_sig}") is None

    def test_wrong_secret_returns_none(self):
        from services.db import _verify_token
        tok = self._fresh_token(user_id=1, secret='wrong-secret-key-1234567890')
        assert _verify_token(tok) is None

    def test_malformed_token_returns_none(self):
        from services.db import _verify_token
        for bad in ['', 'abc', 'a.b', 'a.b.c.d', '.1.999.x', '1..x', '..']:
            assert _verify_token(bad) is None, f"should reject {bad!r}"

    def test_non_digit_user_id_returns_none(self):
        from services.db import _verify_token
        # Build token with non-digit user id but valid signature for that payload
        import hmac, hashlib, base64
        from services.db import AUTH_SECRET
        payload = "abc.9999999999"
        sig = base64.urlsafe_b64encode(
            hmac.new(AUTH_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()
        ).decode('ascii').rstrip('=')
        assert _verify_token(f"{payload}.{sig}") is None

    def test_non_digit_expiry_returns_none(self):
        from services.db import _verify_token
        import hmac, hashlib, base64
        from services.db import AUTH_SECRET
        payload = "1.notanumber"
        sig = base64.urlsafe_b64encode(
            hmac.new(AUTH_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()
        ).decode('ascii').rstrip('=')
        assert _verify_token(f"{payload}.{sig}") is None

    def test_none_input_returns_none(self):
        from services.db import _verify_token
        assert _verify_token(None) is None


# ── Unit tests for password hashing ──


class TestPasswordHash:
    def test_bcrypt_format_starts_with_prefix(self):
        from services.db import _password_hash
        h = _password_hash('hunter2')
        assert h.startswith('bcrypt$') or h.startswith('sha256$')

    def test_hash_is_not_plaintext(self):
        from services.db import _password_hash
        h = _password_hash('hunter2')
        assert 'hunter2' not in h
        assert h != 'hunter2'

    def test_empty_password_returns_empty(self):
        from services.db import _password_hash
        assert _password_hash('') == ''
        assert _password_hash(None) == ''

    def test_same_password_different_hashes(self):
        from services.db import _password_hash
        a = _password_hash('abc123')
        b = _password_hash('abc123')
        # bcrypt salts — should differ
        assert a != b or a.startswith('sha256$')

    def test_verify_bcrypt_roundtrip(self):
        from services.db import _password_hash, _password_verify
        h = _password_hash('correct-horse-battery-staple')
        assert _password_verify('correct-horse-battery-staple', h)
        assert not _password_verify('wrong-password', h)

    def test_verify_legacy_sha256_fallback(self):
        from services.db import _password_hash, _password_verify
        # Simulate a legacy stored hash (no prefix)
        import hashlib
        legacy = hashlib.sha256(('saham-app:' + 'oldpass').encode('utf-8')).hexdigest()
        assert _password_verify('oldpass', legacy)
        assert not _password_verify('badpass', legacy)

    def test_verify_sha256_prefix_format(self):
        from services.db import _password_hash, _password_verify
        h = _password_hash('pw')
        if h.startswith('sha256$'):
            assert _password_verify('pw', h)
            assert not _password_verify('nope', h)


# ── Integration tests for /api/auth/* (TestClient + DB) ──


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    """TestClient with isolated SQLite DB seeded with admin user."""
    db_path = str(tmp_path / 'test_auth.db')
    monkeypatch.setenv('SAHAM_AUTH_SECRET', 'test-secret-key-for-unit-tests-12345678')
    import importlib
    import services.db as db_mod
    importlib.reload(db_mod)
    monkeypatch.setattr(db_mod, 'DB_PATH', db_path)
    monkeypatch.setattr(db_mod, 'USE_POSTGRES', False)
    db_mod._init_db()
    from services.migration import run_migrations
    run_migrations()
    db_mod._ensure_admin_user()

    # Reset in-memory rate limit stores so tests don't pollute each other
    import app as app_mod
    app_mod._rate_limit_store.clear()
    app_mod._login_rate_store.clear()

    from fastapi.testclient import TestClient
    with patch('services.stock_service.yf'), \
         patch('routes.stocks.get_top_stocks', return_value=[]), \
         patch('routes.stocks.get_stock_history'), \
         patch('routes.stocks.get_stock_info', return_value={}):
        from app import app
        client = TestClient(app)
        yield client
        # Cleanup between tests
        app_mod._rate_limit_store.clear()
        app_mod._login_rate_store.clear()


class TestAuthLoginEndpoint:
    def test_login_with_default_admin(self, auth_client):
        resp = auth_client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
        assert resp.status_code == 200
        body = resp.json()
        assert 'token' in body or 'access_token' in body
        assert 'refresh_token' in body
        assert body['user']['username'] == 'admin'

    def test_login_bad_password_returns_401(self, auth_client):
        resp = auth_client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong'})
        assert resp.status_code == 401
        assert 'detail' in resp.json()

    def test_login_unknown_user_returns_401(self, auth_client):
        resp = auth_client.post('/api/auth/login', json={'username': 'nobody', 'password': 'whatever'})
        assert resp.status_code == 401

    def test_login_missing_fields_returns_422(self, auth_client):
        resp = auth_client.post('/api/auth/login', json={'username': 'admin'})
        assert resp.status_code == 422

    def test_login_rate_limit(self, auth_client):
        # 5 attempts/min/IP — 6th should be rate-limited (429)
        statuses = []
        for _ in range(7):
            r = auth_client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong'})
            statuses.append(r.status_code)
        assert 429 in statuses, f"Expected 429 after burst, got {statuses}"
        # First 5 should be 401 (bad creds), 6th onwards 429
        assert statuses[0] == 401
        assert statuses[5] == 429

    def test_me_with_token_returns_user(self, auth_client):
        login = auth_client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'}).json()
        token = login.get('token') or login.get('access_token')
        r = auth_client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
        assert r.status_code == 200
        assert r.json()['user']['username'] == 'admin'

    def test_me_with_invalid_token_returns_401(self, auth_client):
        r = auth_client.get('/api/auth/me', headers={'Authorization': 'Bearer not-a-token'})
        assert r.status_code == 401

    def test_refresh_with_valid_token(self, auth_client):
        login = auth_client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'}).json()
        rt = login['refresh_token']
        r = auth_client.post('/api/auth/refresh', json={'refresh_token': rt})
        assert r.status_code == 200
        assert 'token' in r.json() or 'access_token' in r.json()

    def test_refresh_with_garbage_token_returns_401(self, auth_client):
        r = auth_client.post('/api/auth/refresh', json={'refresh_token': 'garbage'})
        assert r.status_code == 401


# ── Sanitize message ──


class TestSanitizeMessage:
    def test_escapes_script_tag(self):
        from app import sanitize_message
        out = sanitize_message('<script>alert(1)</script>')
        assert '<script>' not in out
        assert '&lt;script&gt;' in out

    def test_handles_none(self):
        from app import sanitize_message
        assert sanitize_message(None) == ''

    def test_passes_through_safe_text(self):
        from app import sanitize_message
        assert sanitize_message('hello') == 'hello'
