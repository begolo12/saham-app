import hashlib
import hmac
import base64
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger('saham-api')

# ── Constants ──
VOLUME_THRESHOLD = 10000
LIQUIDITY_TIER_100K = 100_000
LIQUIDITY_TIER_1M = 1_000_000
LIQUIDITY_TIER_5M = 5_000_000
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'signals.db')
DATABASE_URL = (
    os.environ.get('POSTGRES_URL_NON_POOLING')
    or os.environ.get('DATABASE_URL_UNPOOLED')
    or os.environ.get('DATABASE_URL')
    or os.environ.get('POSTGRES_URL')
    or ''
)
DATABASE_URL_CLEAN = re.sub(r'(\?.*)', '', DATABASE_URL) if DATABASE_URL else ''
USE_POSTGRES = bool(DATABASE_URL_CLEAN)
DEFAULT_ADMIN_USERNAME = os.environ.get('SAHAM_ADMIN_USERNAME', 'admin')

# ── Environment mode ──
# 'development' (or unset) allows the dev-only-secret fallback for AUTH_SECRET
# and the predictable 'admin123' default password.
# Any other value (production / staging / test) is treated as a hardened
# environment and refuses to start without explicit credentials.
ENV_MODE = (os.environ.get('ENV') or os.environ.get('SAHAM_ENV') or 'development').lower()
IS_DEVELOPMENT = ENV_MODE in ('development', 'dev', 'local', '')


def _resolve_default_admin_password() -> str:
    """Return the admin password, generating a random one in non-dev envs.

    In dev (or when ENV is unset), keep the predictable ``admin123`` default so
    local development stays friction-free. In any other environment, generate a
    cryptographically random password and log it once at startup — the operator
    is responsible for capturing it. A pre-set ``SAHAM_ADMIN_PASSWORD`` always
    wins.
    """
    explicit = os.environ.get('SAHAM_ADMIN_PASSWORD')
    if explicit:
        return explicit
    if IS_DEVELOPMENT:
        return 'admin123'
    generated = secrets.token_urlsafe(18)
    logger.warning(
        'SAHAM_ADMIN_PASSWORD not set in non-development env (ENV=%s). '
        'Generated ephemeral admin password (capture now, it is not stored): %s',
        ENV_MODE, generated,
    )
    return generated


DEFAULT_ADMIN_PASSWORD = _resolve_default_admin_password()


def _resolve_auth_secret() -> str:
    """Resolve the HMAC signing secret for auth tokens.

    Production-grade: require ``SAHAM_AUTH_SECRET`` in any non-development
    environment. Fall back to a dev-only literal only when running locally,
    and log a loud warning so it is never silent in prod.
    """
    secret = os.environ.get('SAHAM_AUTH_SECRET')
    if secret:
        return secret
    if IS_DEVELOPMENT:
        logger.warning(
            'SAHAM_AUTH_SECRET not set — using dev-only fallback. '
            'Set SAHAM_AUTH_SECRET before deploying.'
        )
        return 'dev-only-secret'
    raise RuntimeError(
        'SAHAM_AUTH_SECRET must be set in non-development environments '
        f'(ENV={ENV_MODE}). Refusing to start with a weak auth secret.'
    )


AUTH_SECRET = _resolve_auth_secret()
AUTH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30
LEARNING_WINDOW_DAYS = 7
TRADE_HORIZON_DAYS = 7
STOP_LOSS_PCT = -5.0
TAKE_PROFIT_PCT = 8.0


# ── Helpers ──

def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _password_hash(password: str) -> str:
    """Hash a password using bcrypt (preferred) with a salted-SHA256 fallback.

    New passwords get ``bcrypt$`` prefix so we can identify the algorithm.
    Legacy ``saham-app:sha256`` hashes still verify (no migration needed).
    """
    if not isinstance(password, str) or not password:
        return ''
    try:
        import bcrypt as _bcrypt
        salt = _bcrypt.gensalt(rounds=12)
        digest = _bcrypt.hashpw(password.encode('utf-8'), salt)
        return 'bcrypt$' + digest.decode('ascii')
    except Exception:
        # Fallback to legacy salted SHA256 if bcrypt unavailable
        return 'sha256$' + hashlib.sha256(('saham-app:' + password).encode('utf-8')).hexdigest()


def _password_verify(password: str, stored: str) -> bool:
    """Constant-time verify of (password, stored_hash)."""
    if not stored or not password:
        return False
    try:
        if stored.startswith('bcrypt$'):
            import bcrypt as _bcrypt
            return _bcrypt.checkpw(password.encode('utf-8'), stored[7:].encode('ascii'))
        if stored.startswith('sha256$'):
            return hmac.compare_digest(
                stored[7:],
                hashlib.sha256(('saham-app:' + password).encode('utf-8')).hexdigest(),
            )
        # Legacy unsalted format (pre-prefix hashes): best-effort match
        legacy = hashlib.sha256(('saham-app:' + password).encode('utf-8')).hexdigest()
        return hmac.compare_digest(stored, legacy)
    except Exception:
        return False


def _row_to_dict(row):
    return dict(row) if row is not None else None


# ── DB Connection ──

class _PgConn:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()

    def execute(self, sql, params=None):
        sql = sql.replace('?', '%s')
        if params is None and ';' in sql.strip().rstrip(';'):
            cur = None
            for stmt in [x.strip() for x in sql.split(';') if x.strip()]:
                cur = self.conn.execute(stmt)
            return cur
        cur = self.conn.execute(sql, params or ())
        return cur

    def commit(self):
        self.conn.commit()


def _db_conn():
    if USE_POSTGRES:
        try:
            import psycopg
            from psycopg.rows import dict_row
            conn = psycopg.connect(DATABASE_URL_CLEAN, sslmode='require', row_factory=dict_row)
            return _PgConn(conn)
        except Exception as exc:
            logger.warning('Postgres unavailable, fallback SQLite: %s', exc)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _sql(sql: str) -> str:
    if not USE_POSTGRES:
        return sql
    return sql.replace('?', '%s')


def _init_db():
    with _db_conn() as conn:
        if USE_POSTGRES:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS signal_recommendations (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                name TEXT,
                recommendation TEXT NOT NULL,
                strength REAL NOT NULL,
                price REAL,
                volume INTEGER,
                avg_volume INTEGER,
                potential_score REAL,
                reasons_json TEXT,
                created_at TEXT NOT NULL,
                evaluated_at TEXT,
                future_price REAL,
                return_pct REAL,
                outcome TEXT,
                is_correct INTEGER,
                learning_adjustment REAL DEFAULT 0,
                outlier_reason TEXT,
                signal_version TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_signal_rec_created_at ON signal_recommendations(created_at);
            CREATE INDEX IF NOT EXISTS idx_signal_rec_symbol ON signal_recommendations(symbol);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_rec_daily ON signal_recommendations(symbol, recommendation, substr(created_at, 1, 10));
            CREATE TABLE IF NOT EXISTS app_users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            );
            ALTER TABLE app_users ADD COLUMN IF NOT EXISTS refresh_token TEXT;
            ALTER TABLE app_users ADD COLUMN IF NOT EXISTS refresh_token_expiry INTEGER;
            CREATE TABLE IF NOT EXISTS virtual_portfolio (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                symbol TEXT NOT NULL,
                qty REAL NOT NULL,
                avg_price REAL NOT NULL,
                target_price REAL,
                stop_loss REAL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            ALTER TABLE virtual_portfolio ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1;
            DROP INDEX IF EXISTS idx_virtual_portfolio_symbol;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_virtual_portfolio_user_symbol ON virtual_portfolio(user_id, symbol);
            CREATE INDEX IF NOT EXISTS idx_virtual_portfolio_symbol ON virtual_portfolio(symbol);
            CREATE INDEX IF NOT EXISTS idx_app_users_refresh_token ON app_users(refresh_token);
            ''')
            return
        conn.execute('''
        CREATE TABLE IF NOT EXISTS signal_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            name TEXT,
            recommendation TEXT NOT NULL,
            strength REAL NOT NULL,
            price REAL,
            volume INTEGER,
            avg_volume INTEGER,
            potential_score REAL,
            reasons_json TEXT,
            created_at TEXT NOT NULL,
            evaluated_at TEXT,
            future_price REAL,
            return_pct REAL,
            outcome TEXT,
            is_correct INTEGER,
            learning_adjustment REAL DEFAULT 0,
            outlier_reason TEXT,
            signal_version TEXT
        )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_signal_rec_created_at ON signal_recommendations(created_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_signal_rec_symbol ON signal_recommendations(symbol)')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_rec_daily ON signal_recommendations(symbol, recommendation, substr(created_at, 1, 10))')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS app_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
        ''')
        # Add refresh_token + refresh_token_expiry columns — may already exist
        try:
            conn.execute('ALTER TABLE app_users ADD COLUMN refresh_token TEXT')
        except Exception:
            pass
        try:
            conn.execute('ALTER TABLE app_users ADD COLUMN refresh_token_expiry INTEGER')
        except Exception:
            pass
        conn.execute('''
        CREATE TABLE IF NOT EXISTS virtual_portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            symbol TEXT NOT NULL,
            qty REAL NOT NULL,
            avg_price REAL NOT NULL,
            target_price REAL,
            stop_loss REAL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        try:
            conn.execute('ALTER TABLE virtual_portfolio ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1')
        except Exception:
            pass
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_virtual_portfolio_user_symbol ON virtual_portfolio(user_id, symbol)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_virtual_portfolio_symbol ON virtual_portfolio(symbol)')
        # Index on refresh_token for fast O(1) refresh-token validation lookups
        conn.execute('CREATE INDEX IF NOT EXISTS idx_app_users_refresh_token ON app_users(refresh_token)')

        # signal_weights table — canonical schema (ta_weight, fund_weight, ...).
        # Migrations also create a legacy variant (weight_technical, ...) for
        # older DBs; we tolerate both via _get_signal_weights, but on greenfield
        # installs we want the canonical PK-by-symbol schema so the worker's
        # ON CONFLICT(symbol) upsert works without a second migration pass.
        conn.execute('''
        CREATE TABLE IF NOT EXISTS signal_weights (
            symbol TEXT PRIMARY KEY,
            ta_weight REAL NOT NULL DEFAULT 0.3,
            fund_weight REAL NOT NULL DEFAULT 0.3,
            sent_weight REAL NOT NULL DEFAULT 0.2,
            vol_weight REAL NOT NULL DEFAULT 0.1,
            regime_weight REAL NOT NULL DEFAULT 0.1,
            updated_at TEXT NOT NULL
        )
        ''')
        # Idempotent self-heal: if a legacy install created this table with the
        # weight_technical/... schema (no ta_weight, no symbol PK), add the
        # canonical columns here so the worker upsert can run. This avoids the
        # "no column named ta_weight" error after fresh DBs that predate the
        # migration pass.
        for col, default in (
            ('ta_weight', 0.3),
            ('fund_weight', 0.3),
            ('sent_weight', 0.2),
            ('vol_weight', 0.1),
            ('regime_weight', 0.1),
        ):
            try:
                conn.execute(
                    f'ALTER TABLE signal_weights ADD COLUMN {col} REAL NOT NULL DEFAULT {default}'
                )
            except Exception:
                pass
        # Ensure unique index on symbol for ON CONFLICT(symbol) upsert.
        try:
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_weights_symbol ON signal_weights(symbol)')
        except Exception:
            pass
        conn.commit()
        # signal_backtest table
        conn.execute('''
        CREATE TABLE IF NOT EXISTS signal_backtest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            entry_price REAL,
            exit_price REAL,
            return_pct REAL,
            signal_strength REAL,
            regime TEXT,
            outcome TEXT,
            is_correct INTEGER,
            win_rate REAL,
            avg_return REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            total_trades INTEGER,
            start_date TEXT,
            end_date TEXT,
            created_at TEXT NOT NULL
        )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_signal_backtest_symbol ON signal_backtest(symbol)')


# ── Signal weights helpers ──

def _get_signal_weights(symbol: str = '') -> Dict[str, float]:
    """Get signal weights from DB. Returns default weights if none found.

    Tolerant of both schema variants: the canonical ``ta_weight``/... columns
    (set by ``_init_db`` and added by the S17 migration) AND the legacy
    ``weight_technical``/... columns (created by an older ``run_migrations``).
    Falls back to hardcoded defaults when neither is present.
    """
    defaults = {'ta_weight': 0.3, 'fund_weight': 0.3, 'sent_weight': 0.2, 'vol_weight': 0.1, 'regime_weight': 0.1}
    # Mapping from canonical key to (canonical_col, legacy_col)
    key_to_cols = {
        'ta_weight': ('ta_weight', 'weight_technical'),
        'fund_weight': ('fund_weight', 'weight_fundamental'),
        'sent_weight': ('sent_weight', 'weight_sentiment'),
        'vol_weight': ('vol_weight', 'weight_volume'),
        'regime_weight': ('regime_weight', 'weight_regime'),
    }
    try:
        with _db_conn() as conn:
            row = conn.execute('SELECT * FROM signal_weights WHERE symbol = ?', (symbol,)).fetchone()
        if row:
            try:
                row_keys = set(row.keys())
            except Exception:
                row_keys = set(row.keys() if hasattr(row, 'keys') else [])
            result = {}
            for key, (canon, legacy) in key_to_cols.items():
                if canon in row_keys:
                    result[key] = float(row[canon])
                elif legacy in row_keys:
                    result[key] = float(row[legacy])
                else:
                    result[key] = defaults[key]
            return result
    except Exception:
        pass
    return defaults


def _upsert_signal_weights(symbol: str, weights: Dict[str, float]):
    """Insert or update signal weights for a symbol."""
    try:
        with _db_conn() as conn:
            conn.execute('''
                INSERT INTO signal_weights (symbol, ta_weight, fund_weight, sent_weight, vol_weight, regime_weight, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    ta_weight = excluded.ta_weight,
                    fund_weight = excluded.fund_weight,
                    sent_weight = excluded.sent_weight,
                    vol_weight = excluded.vol_weight,
                    regime_weight = excluded.regime_weight,
                    updated_at = excluded.updated_at
            ''', (
                symbol,
                float(weights.get('ta_weight', 0.3)),
                float(weights.get('fund_weight', 0.3)),
                float(weights.get('sent_weight', 0.2)),
                float(weights.get('vol_weight', 0.1)),
                float(weights.get('regime_weight', 0.1)),
                _now_iso(),
            ))
            conn.commit()
    except Exception as exc:
        logger.warning('Failed to upsert signal weights for %s: %s', symbol, exc)


def _record_backtest_result(symbol: str, result: dict):
    """Record one backtest result row."""
    try:
        with _db_conn() as conn:
            conn.execute('''
                INSERT INTO signal_backtest
                    (symbol, signal_type, entry_price, exit_price, return_pct, signal_strength, regime,
                     outcome, is_correct, win_rate, avg_return, sharpe_ratio, max_drawdown, total_trades,
                     start_date, end_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                result.get('signal_type', ''),
                result.get('entry_price'),
                result.get('exit_price'),
                result.get('return_pct'),
                result.get('signal_strength'),
                result.get('regime'),
                result.get('outcome'),
                1 if result.get('outcome') == 'win' else 0,
                result.get('win_rate'),
                result.get('avg_return'),
                result.get('sharpe_ratio'),
                result.get('max_drawdown'),
                result.get('total_trades'),
                result.get('start_date'),
                result.get('end_date'),
                _now_iso(),
            ))
            conn.commit()
    except Exception as exc:
        logger.warning('Failed to record backtest for %s: %s', symbol, exc)


def _get_backtest_history(symbol: str, limit: int = 50) -> list:
    """Get backtest history for a symbol."""
    try:
        with _db_conn() as conn:
            rows = conn.execute(
                'SELECT * FROM signal_backtest WHERE symbol = ? ORDER BY created_at DESC LIMIT ?',
                (symbol, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _ensure_admin_user():
    try:
        with _db_conn() as conn:
            if not DEFAULT_ADMIN_PASSWORD:
                return
            row = conn.execute('SELECT id FROM app_users WHERE username = ?', (DEFAULT_ADMIN_USERNAME,)).fetchone()
            if not row:
                conn.execute('INSERT INTO app_users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
                             (DEFAULT_ADMIN_USERNAME, _password_hash(DEFAULT_ADMIN_PASSWORD), 'superadmin',
                              datetime.now(timezone.utc).isoformat(timespec='seconds')))
            else:
                conn.execute('UPDATE app_users SET password_hash = ?, role = ? WHERE username = ?',
                             (_password_hash(DEFAULT_ADMIN_PASSWORD), 'superadmin', DEFAULT_ADMIN_USERNAME))
            conn.commit()
    except Exception as exc:
        logger.warning('ensure admin user failed: %s', exc)


# ── Auth helpers ──

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _sign_token(payload: str) -> str:
    return _b64url(hmac.new(AUTH_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest())


def _make_token(user: Dict[str, Any]) -> str:
    exp = int(time.time()) + AUTH_TOKEN_TTL_SECONDS
    payload = f"{user['id']}.{exp}"
    return f"{payload}.{_sign_token(payload)}"


def _get_user_by_id(user_id: int):
    with _db_conn() as conn:
        row = conn.execute('SELECT id, username, role, created_at FROM app_users WHERE id = ?', (user_id,)).fetchone()
    return _row_to_dict(row)


def _verify_token(token: str):
    """Validate an access token.

    Token format: ``user_id.exp.signature``
    - Reject malformed tokens (not 3 dot-separated parts)
    - Reject non-integer user_id / exp
    - Reject expired tokens
    - Verify HMAC-SHA256 signature with constant-time compare
    """
    if not token or not isinstance(token, str):
        return None
    parts = token.split('.')
    if len(parts) != 3:
        return None
    user_id_s, exp_s, sig = parts
    if not user_id_s or not exp_s or not sig:
        return None
    # Reject anything that's not pure digits (avoids weird int() errors / tricks)
    if not user_id_s.isdigit() or not exp_s.isdigit():
        return None
    try:
        exp_int = int(exp_s)
        user_id_int = int(user_id_s)
    except ValueError:
        return None
    if exp_int < int(time.time()):
        return None
    payload = f"{user_id_s}.{exp_s}"
    if not hmac.compare_digest(sig, _sign_token(payload)):
        return None
    return _get_user_by_id(user_id_int)


def current_user(authorization: str = '') -> Dict[str, Any]:
    """Dependency: extract and verify Bearer token from Authorization header."""
    from fastapi import HTTPException, Header
    # Re-declare with Header dependency to work with FastAPI injection
    pass

# We export the function for use with FastAPI's Header dependency.
# The actual dependency is defined below using the Header import.

# Re-implement to avoid Header import issues at module level
from fastapi import Header, HTTPException, Depends


def current_user(authorization: str = Header(default='')) -> Dict[str, Any]:
    if not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Login required')
    token = authorization.replace('Bearer ', '', 1).strip()
    user = _verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid session')
    return user


def superadmin_user(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    if user.get('role') != 'superadmin':
        raise HTTPException(status_code=403, detail='Super admin only')
    return user


def _get_user_by_credentials(username: str, password: str):
    if not username or not password:
        return None
    with _db_conn() as conn:
        row = conn.execute(
            'SELECT id, username, role, password_hash, created_at FROM app_users WHERE username = ?',
            (username.strip(),)
        ).fetchone()
    if not row:
        return None
    if not _password_verify(password, row['password_hash']):
        return None
    return {'id': row['id'], 'username': row['username'], 'role': row['role'], 'created_at': row['created_at']}


# ── Learning / Recommendation helpers ──

def _record_recommendation(stock: dict, recommendation: dict):
    """Record one daily recommendation per symbol+signal for learning evaluation."""
    try:
        from services.stock_service import _ensure_symbol
        symbol = _ensure_symbol(stock.get('symbol', ''))
        signal = recommendation.get('signal') or 'NEUTRAL'
        outlier_reason = recommendation.get('outlier_reason') or None
        signal_version = recommendation.get('signal_version') or None
        with _db_conn() as conn:
            insert_sql = '''INSERT OR IGNORE INTO signal_recommendations
                (symbol, name, recommendation, strength, price, volume, avg_volume, potential_score, reasons_json, created_at, outlier_reason, signal_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
            if USE_POSTGRES:
                insert_sql = '''INSERT INTO signal_recommendations
                (symbol, name, recommendation, strength, price, volume, avg_volume, potential_score, reasons_json, created_at, outlier_reason, signal_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (symbol, recommendation, substr(created_at, 1, 10)) DO NOTHING'''
            conn.execute(
                insert_sql,
                (
                    symbol,
                    stock.get('name'),
                    signal,
                    recommendation.get('strength', 50),
                    stock.get('price'),
                    stock.get('volume'),
                    stock.get('avg_volume'),
                    stock.get('potential_score'),
                    json.dumps(recommendation.get('reasons', []), ensure_ascii=False),
                    _now_iso(),
                    outlier_reason,
                    signal_version,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning('record recommendation failed for %s: %s', stock.get('symbol'), exc)


def _evaluate_learning_batch(limit: int = 50):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LEARNING_WINDOW_DAYS)).isoformat(timespec='seconds')
    with _db_conn() as conn:
        rows = conn.execute(
            '''SELECT * FROM signal_recommendations
               WHERE evaluated_at IS NULL AND created_at <= ?
               ORDER BY created_at ASC
               LIMIT ?''',
            (cutoff, limit),
        ).fetchall()

    from stock_data import get_stock_history
    results = []
    for row in rows:
        symbol = row['symbol']
        try:
            df = get_stock_history(symbol, period='6mo')
            if df.empty or len(df) < 2:
                continue
            created_at = datetime.fromisoformat(str(row['created_at']).replace('Z', '+00:00'))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            target_date = (created_at + timedelta(days=LEARNING_WINDOW_DAYS)).date()
            target_rows = df[df.index.date >= target_date]
            if target_rows.empty:
                continue
            future_price = float(target_rows['close'].iloc[0])
            entry_price = float(row['price'] or 0)
            if entry_price <= 0:
                continue
            return_pct = round(((future_price - entry_price) / entry_price) * 100, 2)
            rec = row['recommendation']
            if rec == 'BUY':
                correct = 1 if return_pct > 0 else 0
                outcome = 'win' if correct else 'loss'
            elif rec == 'SELL':
                correct = 1 if return_pct < 0 else 0
                outcome = 'win' if correct else 'loss'
            else:
                correct = 1 if abs(return_pct) <= 5 else 0
                outcome = 'stable' if correct else 'volatile'
            adjustment = 5 if correct else -5
            with _db_conn() as conn:
                conn.execute(
                    '''UPDATE signal_recommendations
                       SET evaluated_at = ?, future_price = ?, return_pct = ?, outcome = ?, is_correct = ?, learning_adjustment = ?
                       WHERE id = ?''',
                    (_now_iso(), future_price, return_pct, outcome, correct, adjustment, row['id']),
                )
                conn.commit()
            results.append({'symbol': symbol, 'recommendation': rec, 'outcome': outcome, 'return_pct': return_pct})
        except Exception as exc:
            logger.warning('evaluate learning failed for %s: %s', symbol, exc)
    return results


def _learning_bias_for_symbol(symbol: str) -> float:
    try:
        with _db_conn() as conn:
            rows = conn.execute(
                '''SELECT AVG(learning_adjustment) AS adj
                   FROM signal_recommendations
                   WHERE symbol = ? AND evaluated_at IS NOT NULL''',
                (symbol,),
            ).fetchone()
        adj = rows['adj'] if rows else 0
        return float(adj or 0)
    except Exception:
        return 0.0
