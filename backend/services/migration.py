import logging

from services.db import _db_conn, USE_POSTGRES

logger = logging.getLogger('saham-api')


def run_migrations():
    """Create new signal/backtest tables + add refresh_token + outlier_reason + signal_version + macro columns."""
    with _db_conn() as conn:
        if USE_POSTGRES:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS signal_backtest (
                    id SERIAL PRIMARY KEY,
                    signal_id TEXT,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    entry_price REAL,
                    exit_price REAL,
                    entry_date TEXT,
                    exit_date TEXT,
                    return_pct REAL,
                    max_drawdown REAL,
                    sharpe_ratio REAL,
                    days_held INTEGER,
                    outcome TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS market_regime (
                    id SERIAL PRIMARY KEY,
                    date TEXT UNIQUE NOT NULL,
                    regime TEXT NOT NULL,
                    confidence REAL,
                    ihsg_trend REAL,
                    volatility REAL,
                    bi_rate REAL,
                    inflation REAL,
                    usd_idr REAL,
                    macro_notes TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS signal_weights (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT,
                    sector TEXT,
                    weight_technical REAL,
                    weight_fundamental REAL,
                    weight_sentiment REAL,
                    weight_volume REAL,
                    weight_regime REAL,
                    updated_at TEXT NOT NULL
                )
            ''')
            # IF NOT EXISTS guards: previous deploys / _init_db may have already
            # created these columns. Without the guard, the second ALTER raises
            # an error that aborts the Postgres transaction, and every later
            # execute() in the same `with` block (including CREATE INDEX) fails
            # with InFailedSqlTransaction even though we caught the exception.
            try:
                conn.execute('ALTER TABLE app_users ADD COLUMN IF NOT EXISTS refresh_token TEXT')
            except Exception:
                pass
            try:
                conn.execute('ALTER TABLE app_users ADD COLUMN IF NOT EXISTS refresh_token_expiry INTEGER')
            except Exception:
                pass
            # S17: add canonical weight columns (see SQLite branch below for rationale)
            for col, default in (
                ('ta_weight', 0.3),
                ('fund_weight', 0.3),
                ('sent_weight', 0.2),
                ('vol_weight', 0.1),
                ('regime_weight', 0.1),
            ):
                try:
                    conn.execute(
                        f'ALTER TABLE signal_weights ADD COLUMN IF NOT EXISTS {col} REAL NOT NULL DEFAULT {default}'
                    )
                except Exception:
                    pass
            # S17: legacy table has no PK on symbol; upsert uses ON CONFLICT(symbol)
            # which requires a unique index. Add one (idempotent via IF NOT EXISTS).
            try:
                conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_weights_symbol ON signal_weights(symbol)')
            except Exception:
                pass
            try:
                conn.execute('ALTER TABLE signal_recommendations ADD COLUMN IF NOT EXISTS outlier_reason TEXT')
            except Exception:
                pass
            try:
                conn.execute('ALTER TABLE signal_recommendations ADD COLUMN IF NOT EXISTS signal_version TEXT')
            except Exception:
                pass
            # Index for O(1) refresh-token lookups (added S15)
            try:
                conn.execute('CREATE INDEX IF NOT EXISTS idx_app_users_refresh_token ON app_users(refresh_token)')
            except Exception:
                pass
        else:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS signal_backtest (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    entry_price REAL,
                    exit_price REAL,
                    entry_date TEXT,
                    exit_date TEXT,
                    return_pct REAL,
                    max_drawdown REAL,
                    sharpe_ratio REAL,
                    days_held INTEGER,
                    outcome TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS market_regime (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    regime TEXT NOT NULL,
                    confidence REAL,
                    ihsg_trend REAL,
                    volatility REAL,
                    bi_rate REAL,
                    inflation REAL,
                    usd_idr REAL,
                    macro_notes TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS signal_weights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    sector TEXT,
                    weight_technical REAL,
                    weight_fundamental REAL,
                    weight_sentiment REAL,
                    weight_volume REAL,
                    weight_regime REAL,
                    updated_at TEXT NOT NULL
                )
            ''')
            # Add refresh_token column — may already exist
            try:
                conn.execute('ALTER TABLE app_users ADD COLUMN refresh_token TEXT')
            except Exception:
                pass
            # Add refresh_token_expiry column (split from token for exact-match lookup)
            try:
                conn.execute('ALTER TABLE app_users ADD COLUMN refresh_token_expiry INTEGER')
            except Exception:
                pass
            # S17: add canonical weight columns expected by _get_signal_weights /
            # _upsert_signal_weights (db.py). The table was originally created with
            # weight_technical/... columns; both name sets must coexist so that
            # code reading 'ta_weight' or 'weight_technical' both work.
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
            # S17: legacy table has no PK on symbol; upsert uses ON CONFLICT(symbol)
            # which requires a unique index. Add one (idempotent).
            try:
                conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_weights_symbol ON signal_weights(symbol)')
            except Exception:
                pass
            # New columns for S12 / S13
            try:
                conn.execute('ALTER TABLE signal_recommendations ADD COLUMN outlier_reason TEXT')
            except Exception:
                pass
            try:
                conn.execute('ALTER TABLE signal_recommendations ADD COLUMN signal_version TEXT')
            except Exception:
                pass
            # Index for O(1) refresh-token lookups (added S15)
            try:
                conn.execute('CREATE INDEX IF NOT EXISTS idx_app_users_refresh_token ON app_users(refresh_token)')
            except Exception:
                pass
            # Macro columns on existing table
            try:
                conn.execute('ALTER TABLE market_regime ADD COLUMN bi_rate REAL')
            except Exception:
                pass
            try:
                conn.execute('ALTER TABLE market_regime ADD COLUMN inflation REAL')
            except Exception:
                pass
            try:
                conn.execute('ALTER TABLE market_regime ADD COLUMN usd_idr REAL')
            except Exception:
                pass
            try:
                conn.execute('ALTER TABLE market_regime ADD COLUMN macro_notes TEXT')
            except Exception:
                pass
        conn.commit()
    logger.info('Migration done: signal_backtest, market_regime (w/ macro cols), signal_weights, refresh_token, outlier_reason, signal_version')
