import asyncio
import json
import logging
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from stock_data import get_top_stocks, get_stock_history, get_stock_info, SECTOR_MAP, INDONESIAN_STOCKS
from analysis import (
    calc_rsi, calc_macd, calc_sma, calc_bollinger, calc_stochastic,
    analyze_fundamentals,
    generate_technical_signal, generate_fundamental_signal, combine_signals,
)

# ── Logging to stderr for debugging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger('saham-api')

# ── Constants ──
VOLUME_THRESHOLD = 500000  # min daily volume for valid signal
DB_PATH = os.path.join(os.path.dirname(__file__), 'signals.db')
DATABASE_URL = (
    os.environ.get('POSTGRES_URL_NON_POOLING')
    or os.environ.get('DATABASE_URL_UNPOOLED')
    or os.environ.get('DATABASE_URL')
    or os.environ.get('POSTGRES_URL')
    or ''
)
DATABASE_URL_CLEAN = re.sub(r'(\?.*)', '', DATABASE_URL) if DATABASE_URL else ''
USE_POSTGRES = bool(DATABASE_URL_CLEAN)
LEARNING_WINDOW_DAYS = 30
TRADE_HORIZON_DAYS = 7
STOP_LOSS_PCT = -5.0
TAKE_PROFIT_PCT = 8.0

# ── Thread pool for parallel yfinance calls ──
_executor = ThreadPoolExecutor(max_workers=5)

# ── Simple in-memory cache for market-summary ──
_market_summary_cache = {}  # { 'data': ..., 'timestamp': ... }

# ── FastAPI app ──
app = FastAPI(
    title='SahamApp - Indonesian Stock Analysis API',
    description='Backend API untuk analisis saham Indonesia',
    version='1.0.0',
)

# CORS — allow mobile app from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

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
                learning_adjustment REAL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_signal_rec_created_at ON signal_recommendations(created_at);
            CREATE INDEX IF NOT EXISTS idx_signal_rec_symbol ON signal_recommendations(symbol);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_rec_daily ON signal_recommendations(symbol, recommendation, substr(created_at, 1, 10));
            CREATE TABLE IF NOT EXISTS virtual_portfolio (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL UNIQUE,
                qty REAL NOT NULL,
                avg_price REAL NOT NULL,
                target_price REAL,
                stop_loss REAL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_virtual_portfolio_symbol ON virtual_portfolio(symbol);
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
            learning_adjustment REAL DEFAULT 0
        )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_signal_rec_created_at ON signal_recommendations(created_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_signal_rec_symbol ON signal_recommendations(symbol)')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_rec_daily ON signal_recommendations(symbol, recommendation, substr(created_at, 1, 10))')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS virtual_portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            qty REAL NOT NULL,
            avg_price REAL NOT NULL,
            target_price REAL,
            stop_loss REAL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_virtual_portfolio_symbol ON virtual_portfolio(symbol)')


def _record_recommendation(stock: dict, recommendation: dict):
    """Record one daily recommendation per symbol+signal for learning evaluation."""
    try:
        symbol = _ensure_symbol(stock.get('symbol', ''))
        signal = recommendation.get('signal') or 'NEUTRAL'
        with _db_conn() as conn:
            insert_sql = '''INSERT OR IGNORE INTO signal_recommendations
                (symbol, name, recommendation, strength, price, volume, avg_volume, potential_score, reasons_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
            if USE_POSTGRES:
                insert_sql = '''INSERT INTO signal_recommendations
                (symbol, name, recommendation, strength, price, volume, avg_volume, potential_score, reasons_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    results = []
    for row in rows:
        symbol = row['symbol']
        try:
            df = get_stock_history(symbol, period='6mo')
            if df.empty or len(df) < 2:
                continue
            future_price = float(df['close'].iloc[-1])
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


_init_db()


def _stock_bias(stock: Dict[str, Any]) -> Dict[str, float]:
    volume = float(stock.get('volume') or 0)
    avg_volume = float(stock.get('avg_volume') or 0)
    price = float(stock.get('price') or 0)
    potential = float(stock.get('potential_score') or 0)
    volume_bias = 0.0
    price_bias = 0.0
    if volume >= 5_000_000 or avg_volume >= 5_000_000:
        volume_bias += 8
    elif volume >= 1_000_000 or avg_volume >= 1_000_000:
        volume_bias += 6
    elif volume >= VOLUME_THRESHOLD or avg_volume >= VOLUME_THRESHOLD:
        volume_bias += 3
    else:
        volume_bias -= 8
    if 50 <= price < 200:
        price_bias += 2
    if potential >= 70:
        volume_bias += 3
    elif potential and potential < 45:
        volume_bias -= 5
    return {'volume_bias': volume_bias, 'price_bias': price_bias}


def _apply_learning_signal(df: pd.DataFrame, stock: Dict[str, Any]) -> Dict[str, Any]:
    bias = _stock_bias(stock)
    learning_bias = _learning_bias_for_symbol(stock.get('symbol', ''))
    signal = generate_technical_signal(
        df,
        volume_bias=bias['volume_bias'] + learning_bias,
        price_bias=bias['price_bias'],
    )
    if bias['volume_bias'] > 0:
        signal['reasons'].append('Volume/likuiditas mendukung — sinyal lebih dipercaya')
    elif bias['volume_bias'] < 0:
        signal['reasons'].append('Volume rendah — sinyal diturunkan')
    if learning_bias > 0:
        signal['reasons'].append(f'Learning historis positif (+{learning_bias:.1f}) untuk saham ini')
    elif learning_bias < 0:
        signal['reasons'].append(f'Learning historis negatif ({learning_bias:.1f}) untuk saham ini')
    return signal


def _ensure_symbol(symbol: str) -> str:
    """Add .JK suffix if missing."""
    s = symbol.upper().strip()
    if not s.endswith('.JK'):
        s = s + '.JK'
    return s


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class PortfolioPosition(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None


def _fmt_action(signal: str) -> str:
    return 'BUY' if signal == 'BUY' else 'SELL' if signal == 'SELL' else 'WAIT'


def _make_trade_plan(symbol: str, price: float, signal: str, strength: float, volatility_pct: Optional[float] = None) -> Dict[str, Any]:
    vol = max(3.0, min(12.0, float(volatility_pct or 5.0)))
    action = _fmt_action(signal)
    if action == 'BUY':
        target_pct = max(4.0, min(12.0, 3.0 + (strength - 50) * 0.18 + vol * 0.25))
        stop_pct = min(-3.0, max(-8.0, -vol * 0.9))
        target_price = round(price * (1 + target_pct / 100), 2)
        stop_loss = round(price * (1 + stop_pct / 100), 2)
        instruction = f'BUY area Rp {price:,.0f}. Target jual 7 hari Rp {target_price:,.0f} (+{target_pct:.1f}%). Stop loss Rp {stop_loss:,.0f} ({stop_pct:.1f}%). Cek tiap hari.'
    elif action == 'SELL':
        target_pct = max(3.0, min(10.0, 2.5 + (50 - strength) * 0.15 + vol * 0.20))
        stop_pct = max(3.0, min(8.0, vol * 0.8))
        target_price = round(price * (1 - target_pct / 100), 2)
        stop_loss = round(price * (1 + stop_pct / 100), 2)
        instruction = f'SELL / hindari entry. Target turun 7 hari Rp {target_price:,.0f} (-{target_pct:.1f}%). Invalid jika naik ke Rp {stop_loss:,.0f} (+{stop_pct:.1f}%). Cek tiap hari.'
    else:
        target_price = round(price * 1.04, 2)
        stop_loss = round(price * 0.96, 2)
        instruction = f'WAIT. Belum ada edge kuat. Range pantau Rp {stop_loss:,.0f} - Rp {target_price:,.0f}. Cek tiap hari.'
    return {
        'action': action,
        'entry_price': round(float(price), 2),
        'target_price': target_price,
        'stop_loss': stop_loss,
        'horizon_days': TRADE_HORIZON_DAYS,
        'check_every': 'daily',
        'take_profit_pct': round(((target_price - price) / price) * 100, 2) if price else 0,
        'stop_loss_pct': round(((stop_loss - price) / price) * 100, 2) if price else 0,
        'instruction': instruction.replace(',', '.'),
        'confidence': 'tinggi' if strength >= 75 or strength <= 25 else 'sedang' if strength >= 62 or strength <= 38 else 'rendah',
    }


def _daily_check_from_plan(price: float, plan: Dict[str, Any]) -> Dict[str, Any]:
    action = plan.get('action')
    target = float(plan.get('target_price') or 0)
    stop = float(plan.get('stop_loss') or 0)
    if action == 'BUY':
        if target and price >= target:
            return {'status': 'TAKE_PROFIT', 'message': 'Target 7 hari kena. Realisasi profit / trailing stop.'}
        if stop and price <= stop:
            return {'status': 'STOP_LOSS', 'message': 'Stop loss kena. Cut loss, jangan averaging.'}
        return {'status': 'HOLD', 'message': 'Masih dalam rencana. Cek ulang besok.'}
    if action == 'SELL':
        if target and price <= target:
            return {'status': 'SELL_VALID', 'message': 'Sinyal jual valid, harga turun sesuai rencana.'}
        if stop and price >= stop:
            return {'status': 'SELL_INVALID', 'message': 'Sinyal jual invalid, harga tembus batas atas.'}
        return {'status': 'WAIT', 'message': 'Masih hindari entry sampai sinyal membaik.'}
    return {'status': 'WATCH', 'message': 'Belum entry. Tunggu sinyal lebih jelas.'}


async def _run_sync_with_timeout(fn, *args, timeout=10, **kwargs):
    """Run a sync function in executor thread with timeout."""
    return await asyncio.wait_for(
        asyncio.get_event_loop().run_in_executor(_executor, lambda: fn(*args, **kwargs)),
        timeout=timeout,
    )


async def _fetch_stock_data_with_retry(fetch_func, *args, max_retries=2, timeout=10, **kwargs):
    """Fetch yfinance data with retry and timeout. Returns None on total failure."""
    for attempt in range(max_retries):
        try:
            return await _run_sync_with_timeout(fetch_func, *args, timeout=timeout, **kwargs)
        except asyncio.TimeoutError:
            logger.warning('Timeout fetching data (attempt %d/%d) for %s', attempt + 1, max_retries, args[0] if args else '?')
        except Exception as exc:
            logger.warning('Error fetching data (attempt %d/%d) for %s: %s', attempt + 1, max_retries, args[0] if args else '?', exc)
        if attempt < max_retries - 1:
            await asyncio.sleep(1)
    return None


def _analyze_stock(s: dict) -> dict:
    """Analyze a single stock dict (from get_top_stocks) and return enriched data."""
    symbol_full = s['symbol']
    if not symbol_full.endswith('.JK'):
        symbol_full = symbol_full + '.JK'

    df = get_stock_history(symbol_full, period='3mo')
    info = get_stock_info(symbol_full)

    tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
    fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

    if not df.empty:
        tech_signal = _apply_learning_signal(df, s)
    if info:
        fund_signal = generate_fundamental_signal(info)

    overall = combine_signals(tech_signal, fund_signal)

    # RSI from technical analysis
    rsi_val = None
    if not df.empty:
        rsi_series = calc_rsi(df['close'])
        rsi_val = round(float(rsi_series.iloc[-1]), 2) if not pd.isna(rsi_series.iloc[-1]) else None

    # Fundamental vals
    pe_ratio = None
    pbv = None
    if info:
        pe_ratio = round(info.get('trailingPE') or info.get('forwardPE') or 0, 2) if (info.get('trailingPE') or info.get('forwardPE')) else None
        pbv = round(info.get('priceToBook') or 0, 2) if info.get('priceToBook') else None

    return {
        'symbol': s['symbol'].replace('.JK', ''),
        'name': s['name'],
        'price': s['price'],
        'change_percent': s['change_percent'],
        'sector': s['sector'],
        'technical': {
            'signal': tech_signal['signal'],
            'strength': tech_signal['strength'],
            'rsi': rsi_val,
        },
        'fundamental': {
            'signal': fund_signal['signal'],
            'strength': fund_signal['strength'],
            'pe_ratio': pe_ratio,
            'pbv': pbv,
        },
        'overall_signal': overall['signal'],
        'overall_strength': overall['strength'],
    }


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get('/api/stocks')
async def list_stocks(limit: Optional[int] = None, all: bool = False):
    """
    Return list of Indonesian stocks with basic info + overall signal.
    - Default: returns TOP 10 stocks sorted by signal strength (best recs)
    - ?limit=30: returns top N sorted by signal strength
    - ?all=true: returns ALL tracked stocks sorted by signal strength
    """
    stocks = get_top_stocks()
    updated_at = _now_iso()

    async def _analyze_one(s):
        try:
            symbol_full = s['symbol']
            if not symbol_full.endswith('.JK'):
                symbol_full = symbol_full + '.JK'
            df = await _fetch_stock_data_with_retry(get_stock_history, symbol_full, '3mo')
            info = await _fetch_stock_data_with_retry(get_stock_info, symbol_full)

            tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
            fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

            if df is not None and not df.empty:
                tech_signal = _apply_learning_signal(df, s)
            if info:
                fund_signal = generate_fundamental_signal(info)

            overall = combine_signals(tech_signal, fund_signal)

            result = {
                'symbol': s['symbol'].replace('.JK', ''),
                'name': s['name'],
                'price': s['price'],
                'change_percent': s['change_percent'],
                'signal': overall['signal'],
                'signal_strength': overall['strength'],
                'sector': s['sector'],
                'volume': s.get('volume', 0),
                'avg_volume': s.get('avg_volume', 0),
                'potential_score': s.get('potential_score', 0),
                'trade_plan': _make_trade_plan(s['symbol'].replace('.JK', ''), float(s.get('price') or 0), overall['signal'], overall['strength']),
            }
            _record_recommendation(s, overall)
            return result
        except Exception as exc:
            logger.warning('List stocks: failed to analyze %s: %s', s['symbol'], exc)
            return {
                'symbol': s['symbol'].replace('.JK', ''),
                'name': s['name'],
                'price': s['price'],
                'change_percent': s['change_percent'],
                'signal': 'NEUTRAL',
                'signal_strength': 50,
                'sector': s['sector'],
            }

    tasks = [_analyze_one(s) for s in stocks]
    outcomes = await asyncio.gather(*tasks)
    results = [r for r in outcomes if r is not None]

    # Sort by signal strength descending (best recommendations first)
    results.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)

    # Apply limit/all logic AFTER analysis + sorting
    if not all:
        max_count = limit if limit is not None else 10
        results = results[:max_count]

    return {'stocks': results, 'updated_at': updated_at}


@app.get('/api/stocks/search')
async def search_stocks(q: str):
    """
    Search stocks by symbol, name, or sector (case-insensitive, partial match).
    Returns matching stocks with basic info + signal, sorted by signal strength.
    """
    if not q or q.strip() == '':
        return {'stocks': [], 'query': q, 'updated_at': _now_iso()}

    q_lower = q.strip().lower()

    # Search across ALL tracked stocks
    all_stocks = get_top_stocks()
    updated_at = _now_iso()

    # Filter matching stocks first (cheap), then analyze (expensive)
    matching = []
    for s in all_stocks:
        symbol_lower = s['symbol'].lower()
        name_lower = s['name'].lower()
        sector_lower = s['sector'].lower()
        if q_lower in symbol_lower or q_lower in name_lower or q_lower in sector_lower:
            matching.append(s)

    if not matching:
        return {'stocks': [], 'query': q, 'count': 0, 'updated_at': updated_at}

    async def _analyze_one(s):
        try:
            symbol_full = s['symbol']
            if not symbol_full.endswith('.JK'):
                symbol_full = symbol_full + '.JK'
            df = await _fetch_stock_data_with_retry(get_stock_history, symbol_full, '3mo')
            info = await _fetch_stock_data_with_retry(get_stock_info, symbol_full)

            tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
            fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

            if df is not None and not df.empty:
                tech_signal = _apply_learning_signal(df, s)
            if info:
                fund_signal = generate_fundamental_signal(info)

            overall = combine_signals(tech_signal, fund_signal)

            result = {
                'symbol': s['symbol'].replace('.JK', ''),
                'name': s['name'],
                'price': s['price'],
                'change_percent': s['change_percent'],
                'signal': overall['signal'],
                'signal_strength': overall['strength'],
                'sector': s['sector'],
                'volume': s.get('volume', 0),
                'avg_volume': s.get('avg_volume', 0),
                'potential_score': s.get('potential_score', 0),
                'trade_plan': _make_trade_plan(s['symbol'].replace('.JK', ''), float(s.get('price') or 0), overall['signal'], overall['strength']),
            }
            _record_recommendation(s, overall)
            return result
        except Exception as exc:
            logger.warning('Search: failed to analyze %s: %s', s['symbol'], exc)
            return {
                'symbol': s['symbol'].replace('.JK', ''),
                'name': s['name'],
                'price': s['price'],
                'change_percent': s['change_percent'],
                'signal': 'NEUTRAL',
                'signal_strength': 50,
                'sector': s['sector'],
            }

    tasks = [_analyze_one(s) for s in matching]
    outcomes = await asyncio.gather(*tasks)
    results = [r for r in outcomes if r is not None]

    # Sort by signal strength descending
    results.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)

    return {'stocks': results, 'query': q, 'count': len(results), 'updated_at': updated_at}


@app.get('/api/stocks/batch')
async def stocks_batch():
    """
    Return detailed analysis for ALL 10 stocks in ONE call.
    Uses ThreadPoolExecutor (max_workers=5) to parallelize yfinance calls.
    """
    stocks = get_top_stocks()
    results = []
    errors = []
    updated_at = _now_iso()

    async def _analyze_one(s):
        try:
            symbol_full = s['symbol']
            if not symbol_full.endswith('.JK'):
                symbol_full = symbol_full + '.JK'

            # Fetch with retry + timeout via executor
            df = await _fetch_stock_data_with_retry(get_stock_history, symbol_full, '3mo')
            info = await _fetch_stock_data_with_retry(get_stock_info, symbol_full)

            tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
            fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

            if df is not None and not df.empty:
                tech_signal = _apply_learning_signal(df, s)
            if info:
                fund_signal = generate_fundamental_signal(info)

            overall = combine_signals(tech_signal, fund_signal)

            # RSI
            rsi_val = None
            if df is not None and not df.empty:
                rsi_series = calc_rsi(df['close'])
                rsi_val = round(float(rsi_series.iloc[-1]), 2) if not pd.isna(rsi_series.iloc[-1]) else None

            # Fundamental vals
            pe_ratio = None
            pbv = None
            if info:
                pe_ratio = round(info.get('trailingPE') or info.get('forwardPE') or 0, 2) if (info.get('trailingPE') or info.get('forwardPE')) else None
                pbv = round(info.get('priceToBook') or 0, 2) if info.get('priceToBook') else None

            return {
                'symbol': s['symbol'].replace('.JK', ''),
                'name': s['name'],
                'price': s['price'],
                'change_percent': s['change_percent'],
                'sector': s['sector'],
                'technical': {
                    'signal': tech_signal['signal'],
                    'strength': tech_signal['strength'],
                    'rsi': rsi_val,
                },
                'fundamental': {
                    'signal': fund_signal['signal'],
                    'strength': fund_signal['strength'],
                    'pe_ratio': pe_ratio,
                    'pbv': pbv,
                },
                'overall_signal': overall['signal'],
                'overall_strength': overall['strength'],
            }
        except Exception as exc:
            logger.error('Batch analysis failed for %s: %s', s['symbol'], exc)
            errors.append(s['symbol'])
            return None

    tasks = [_analyze_one(s) for s in stocks]
    outcomes = await asyncio.gather(*tasks)

    for result in outcomes:
        if result is not None:
            results.append(result)

    # Sort by overall strength descending (best recommendations first)
    results.sort(key=lambda x: x.get('overall_strength', 0), reverse=True)

    if errors:
        logger.warning('Batch endpoint: %d stocks failed analysis: %s', len(errors), errors)

    return {'stocks': results, 'updated_at': updated_at}


@app.get('/api/live/summary')
async def live_summary():
    """
    Super lightweight endpoint — returns just prices + signals for all stocks.
    Sorted by overall strength descending. Should complete in < 5 seconds.
    """
    stocks = get_top_stocks()
    updated_at = _now_iso()

    async def _analyze_one(s):
        try:
            symbol_full = s['symbol']
            if not symbol_full.endswith('.JK'):
                symbol_full = symbol_full + '.JK'
            df = await _fetch_stock_data_with_retry(get_stock_history, symbol_full, '3mo')
            info = await _fetch_stock_data_with_retry(get_stock_info, symbol_full)

            tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
            fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

            if df is not None and not df.empty:
                tech_signal = _apply_learning_signal(df, s)
            if info:
                fund_signal = generate_fundamental_signal(info)

            overall = combine_signals(tech_signal, fund_signal)

            return {
                'symbol': s['symbol'].replace('.JK', ''),
                'price': s['price'],
                'change_percent': s['change_percent'],
                'overall_signal': overall['signal'],
                'overall_strength': overall['strength'],
            }
        except Exception as exc:
            logger.warning('Live summary failed for %s: %s', s['symbol'], exc)
            return {
                'symbol': s['symbol'].replace('.JK', ''),
                'price': s['price'],
                'change_percent': s['change_percent'],
                'overall_signal': 'NEUTRAL',
                'overall_strength': 50,
            }

    tasks = [_analyze_one(s) for s in stocks]
    outcomes = await asyncio.gather(*tasks)
    results = [r for r in outcomes if r is not None]

    # Sort by overall strength descending
    results.sort(key=lambda x: x.get('overall_strength', 0), reverse=True)

    # Market data (IHSG)
    ihsg_price = None
    ihsg_change = 0.0
    try:
        ihsg = yf.Ticker('^JKSE')
        info_ihsg = ihsg.info
        history_ihsg = ihsg.history(period='2d')
        ihsg_price = info_ihsg.get('currentPrice') or info_ihsg.get('regularMarketPrice')
        if ihsg_price is None and not history_ihsg.empty:
            ihsg_price = float(history_ihsg['Close'].iloc[-1])
        prev_close = info_ihsg.get('previousClose')
        if prev_close is None and len(history_ihsg) >= 2:
            prev_close = float(history_ihsg['Close'].iloc[-2])
        if ihsg_price and prev_close:
            ihsg_change = round(((ihsg_price - prev_close) / prev_close) * 100, 2)
    except Exception as exc:
        logger.error('Failed to fetch IHSG for live summary: %s', exc)

    return {
        'stocks': results,
        'market': {
            'ihsg_price': ihsg_price,
            'ihsg_change': ihsg_change,
        },
        'updated_at': updated_at,
    }


@app.get('/api/stocks/{symbol}')
async def stock_detail(symbol: str):
    """
    Return detailed analysis for a single stock.
    """
    sym = _ensure_symbol(symbol)

    try:
        info = get_stock_info(sym)
        df = get_stock_history(sym, period='6mo')
    except Exception as e:
        logger.error('stock_detail failed for %s: %s', symbol, e)
        raise HTTPException(status_code=404, detail=f'Saham {symbol} tidak ditemukan')

    if df.empty:
        raise HTTPException(status_code=404, detail=f'Data historis untuk {symbol} tidak tersedia')

    # ── Prices ──
    close = df['close']
    high = df['high']
    low = df['low']
    latest_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else latest_close
    change = round(latest_close - prev_close, 2)
    change_percent = round((change / prev_close) * 100, 2) if prev_close else 0.0

    # ── Technical Analysis ──
    rsi_series = calc_rsi(close)
    macd_line, macd_signal, macd_hist = calc_macd(close)
    sma20 = calc_sma(close, 20) if len(close) >= 20 else pd.Series([None])
    sma50 = calc_sma(close, 50) if len(close) >= 50 else pd.Series([None])
    upper_bb, middle_bb, lower_bb = calc_bollinger(close) if len(close) >= 20 else (pd.Series([None]), pd.Series([None]), pd.Series([None]))

    recent_volume = int(df['volume'].iloc[-1]) if not df.empty and 'volume' in df.columns else 0
    tech_signal = _apply_learning_signal(df, {'symbol': sym, 'price': latest_close, 'volume': recent_volume, 'avg_volume': int(df['volume'].tail(20).mean()) if 'volume' in df.columns else 0})

    # ── Volume Threshold Check ──
    if recent_volume < VOLUME_THRESHOLD:
        tech_signal['reasons'].append('Volume rendah — sinyal kurang reliable')
        tech_signal['strength'] = max(1, tech_signal['strength'] - 10)
        # Recalculate signal after strength adjustment
        if tech_signal['strength'] >= 65:
            tech_signal['signal'] = 'BUY'
        elif tech_signal['strength'] <= 35:
            tech_signal['signal'] = 'SELL'
        else:
            tech_signal['signal'] = 'NEUTRAL'

    # ── Fundamental Analysis ──
    fundamentals = analyze_fundamentals(info)
    fund_signal = generate_fundamental_signal(info)

    # ── Combined signal ──
    overall = combine_signals(tech_signal, fund_signal)
    volatility_pct = round(float(close.pct_change().tail(20).std() * 100), 2) if len(close) >= 20 else None
    trade_plan = _make_trade_plan(symbol.upper().replace('.JK', ''), latest_close, overall['signal'], overall['strength'], volatility_pct)
    daily_check = _daily_check_from_plan(latest_close, trade_plan)

    name = info.get('longName', info.get('shortName', symbol.replace('.JK', '')))
    _record_recommendation({
        'symbol': sym,
        'name': name,
        'price': latest_close,
        'volume': recent_volume,
        'avg_volume': int(df['volume'].tail(20).mean()) if 'volume' in df.columns else 0,
        'potential_score': 0,
    }, overall)
    sector = SECTOR_MAP.get(sym, info.get('sector', 'Lainnya'))
    industry = info.get('industry', None)
    market_cap = info.get('marketCap')

    def _safe(val):
        return None if (val is None or (isinstance(val, float) and pd.isna(val))) else round(float(val), 2)

    return {
        'symbol': symbol.upper().replace('.JK', ''),
        'name': name,
        'price': latest_close,
        'change': change,
        'change_percent': change_percent,
        'sector': sector,
        'industry': industry,
        'market_cap': market_cap,
        'technical': {
            'rsi': _safe(rsi_series.iloc[-1]),
            'macd_line': _safe(macd_line.iloc[-1]),
            'macd_signal': _safe(macd_signal.iloc[-1]),
            'macd_histogram': _safe(macd_hist.iloc[-1]),
            'sma_20': _safe(sma20.iloc[-1]),
            'sma_50': _safe(sma50.iloc[-1]),
            'bollinger_upper': _safe(upper_bb.iloc[-1]),
            'bollinger_middle': _safe(middle_bb.iloc[-1]),
            'bollinger_lower': _safe(lower_bb.iloc[-1]),
            'signal': tech_signal['signal'],
            'strength': tech_signal['strength'],
            'reasons': tech_signal['reasons'],
        },
        'fundamental': {
            'pe_ratio': fundamentals.get('pe_ratio'),
            'pbv': fundamentals.get('pbv'),
            'dividend_yield': fundamentals.get('dividend_yield'),
            'eps': fundamentals.get('eps'),
            'market_cap': fundamentals.get('market_cap'),
            'high_52w': fundamentals.get('high_52w'),
            'low_52w': fundamentals.get('low_52w'),
            'signal': fund_signal['signal'],
            'strength': fund_signal['strength'],
            'reasons': fund_signal['reasons'],
        },
        'overall_signal': overall['signal'],
        'overall_strength': overall['strength'],
        'overall_reasons': overall['reasons'],
        'trade_plan': trade_plan,
        'daily_check': daily_check,
        'volatility_pct': volatility_pct,
        'updated_at': _now_iso(),
    }


@app.get('/api/stocks/{symbol}/history')
async def stock_history(symbol: str, period: str = '6mo'):
    """
    Return OHLCV chart data for a stock.
    Falls back progressively when short periods return empty:
    1d -> 5d -> 1mo -> 3mo -> 6mo.
    """
    sym = _ensure_symbol(symbol)
    period = period.lower()
    # Normalize short period aliases
    period_map = {'1m': '1mo', '3m': '3mo'}
    period = period_map.get(period, period)
    original_period = period

    # Progressive fallback chain
    FALLBACK_CHAIN = ['1d', '5d', '1mo', '3mo', '6mo']

    df = pd.DataFrame()
    tried_periods = []

    for p in [period] + FALLBACK_CHAIN:
        if p in tried_periods:
            continue
        tried_periods.append(p)
        try:
            df = get_stock_history(sym, period=p)
            if not df.empty:
                period = p
                logger.info('History for %s: found data with period=%s', sym, p)
                break
            logger.warning('History for %s: empty data with period=%s, trying longer...', sym, p)
        except Exception as exc:
            logger.warning('History for %s: error with period=%s: %s', sym, p, exc)
            continue

    if df.empty:
        logger.error('History for %s: no data found after trying periods %s', sym, tried_periods)
        raise HTTPException(status_code=404, detail=f'Tidak ada data untuk {symbol} dengan periode {original_period}')

    dates = [d.strftime('%Y-%m-%d') for d in df.index]
    opens = [round(float(v), 2) for v in df['open']]
    highs = [round(float(v), 2) for v in df['high']]
    lows = [round(float(v), 2) for v in df['low']]
    closes = [round(float(v), 2) for v in df['close']]
    volumes = [int(v) for v in df['volume']]

    return {
        'symbol': symbol.upper().replace('.JK', ''),
        'period': period,
        'dates': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
        'updated_at': _now_iso(),
    }


@app.get('/api/stocks/{symbol}/signals')
async def stock_signals(symbol: str):
    """
    Lightweight endpoint returning just technical + fundamental signals summary.
    Faster than full detail endpoint.
    """
    sym = _ensure_symbol(symbol)

    try:
        info = get_stock_info(sym)
        df = get_stock_history(sym, period='6mo')
    except Exception as e:
        raise HTTPException(status_code=404, detail=f'Saham {symbol} tidak ditemukan')

    tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
    fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

    if not df.empty:
        tech_signal = _apply_learning_signal(df, {'symbol': sym, 'price': float(df['close'].iloc[-1]) if not df.empty else 0, 'volume': int(df['volume'].iloc[-1]) if not df.empty and 'volume' in df.columns else 0})
    if info:
        fund_signal = generate_fundamental_signal(info)

    overall = combine_signals(tech_signal, fund_signal)

    return {
        'symbol': symbol.upper().replace('.JK', ''),
        'overall_signal': overall['signal'],
        'overall_strength': overall['strength'],
        'technical': {
            'signal': tech_signal['signal'],
            'strength': tech_signal['strength'],
        },
        'fundamental': {
            'signal': fund_signal['signal'],
            'strength': fund_signal['strength'],
        },
        'updated_at': _now_iso(),
    }


@app.get('/api/learning/evaluate')
async def learning_evaluate(limit: int = 50):
    """Evaluate recommendations older than 30 days against latest available price."""
    results = _evaluate_learning_batch(limit=limit)
    with _db_conn() as conn:
        summary = conn.execute(
            """SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,
                SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS wrong,
                AVG(return_pct) AS avg_return
               FROM signal_recommendations
               WHERE evaluated_at IS NOT NULL"""
        ).fetchone()
    total = summary['total'] or 0
    correct = summary['correct'] or 0
    return {
        'processed': len(results),
        'summary': {
            'total_evaluated': total,
            'correct': correct,
            'wrong': summary['wrong'] or 0,
            'accuracy': round((correct / total) * 100, 2) if total else 0,
            'avg_return': round(float(summary['avg_return'] or 0), 2),
        },
        'results': results,
        'updated_at': _now_iso(),
    }


@app.get('/api/learning/summary')
async def learning_summary():
    """Return learning performance by signal type plus recent history."""
    _evaluate_learning_batch(limit=25)
    with _db_conn() as conn:
        rows = conn.execute(
            """SELECT recommendation, COUNT(*) AS count,
                      SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,
                      AVG(return_pct) AS avg_return
               FROM signal_recommendations
               WHERE evaluated_at IS NOT NULL
               GROUP BY recommendation
               ORDER BY recommendation"""
        ).fetchall()
        pending = conn.execute(
            'SELECT COUNT(*) AS count FROM signal_recommendations WHERE evaluated_at IS NULL'
        ).fetchone()['count']
        total = conn.execute('SELECT COUNT(*) AS count FROM signal_recommendations').fetchone()['count']
        recent = conn.execute(
            """SELECT symbol, name, recommendation, strength, price, future_price, return_pct, outcome, is_correct, created_at, evaluated_at
               FROM signal_recommendations
               ORDER BY id DESC
               LIMIT 20"""
        ).fetchall()

    by_signal = []
    correct_total = 0
    evaluated_total = 0
    for row in rows:
        count = row['count'] or 0
        correct = row['correct'] or 0
        evaluated_total += count
        correct_total += correct
        by_signal.append({
            'recommendation': row['recommendation'],
            'count': count,
            'correct': correct,
            'accuracy': round((correct / count) * 100, 2) if count else 0,
            'avg_return': round(float(row['avg_return'] or 0), 2),
        })

    return {
        'total_records': total,
        'pending_evaluation': pending,
        'evaluated': evaluated_total,
        'accuracy': round((correct_total / evaluated_total) * 100, 2) if evaluated_total else 0,
        'by_signal': by_signal,
        'recent': [dict(r) for r in recent],
        'rule': 'BUY benar jika return 30 hari > 0%; SELL benar jika return < 0%; HOLD benar jika return di antara -5% sampai +5%.',
        'updated_at': _now_iso(),
    }


@app.get('/api/stocks/{symbol}/recommendation-history')
async def stock_recommendation_history(symbol: str, limit: int = 20):
    sym = symbol.upper().replace('.JK', '')
    with _db_conn() as conn:
        rows = conn.execute(
            """SELECT symbol, recommendation, strength, price, future_price, return_pct, outcome, is_correct, created_at, evaluated_at
               FROM signal_recommendations
               WHERE REPLACE(symbol, '.JK', '') = ?
               ORDER BY id DESC
               LIMIT ?""",
            (sym, limit),
        ).fetchall()
    return {'symbol': sym, 'history': [dict(r) for r in rows], 'updated_at': _now_iso()}


@app.get('/api/portfolio')
async def portfolio_summary():
    stocks = {s['symbol'].replace('.JK', '').upper(): s for s in get_top_stocks()}
    with _db_conn() as conn:
        rows = conn.execute('SELECT * FROM virtual_portfolio ORDER BY symbol').fetchall()
    positions = []
    total_cost = 0.0
    total_value = 0.0
    winners = 0
    losers = 0
    for row in rows:
        sym = row['symbol'].replace('.JK', '').upper()
        stock = stocks.get(sym) or {}
        current = float(stock.get('price') or row['avg_price'])
        qty = float(row['qty'])
        cost = qty * float(row['avg_price'])
        value = qty * current
        pnl = value - cost
        pnl_pct = (pnl / cost) * 100 if cost else 0
        winners += 1 if pnl > 0 else 0
        losers += 1 if pnl < 0 else 0
        positions.append({
            'id': row['id'], 'symbol': sym, 'qty': qty, 'avg_price': row['avg_price'],
            'current_price': current, 'market_value': round(value, 2), 'cost': round(cost, 2),
            'pnl': round(pnl, 2), 'pnl_pct': round(pnl_pct, 2),
            'target_price': row['target_price'], 'stop_loss': row['stop_loss'], 'notes': row['notes'],
        })
        total_cost += cost
        total_value += value
    total_pnl = total_value - total_cost
    closed = winners + losers
    return {
        'positions': positions,
        'summary': {
            'total_cost': round(total_cost, 2), 'total_value': round(total_value, 2),
            'total_pnl': round(total_pnl, 2), 'total_pnl_pct': round((total_pnl / total_cost) * 100, 2) if total_cost else 0,
            'winner_count': winners, 'loser_count': losers,
            'win_rate': round((winners / closed) * 100, 2) if closed else 0,
            'lose_rate': round((losers / closed) * 100, 2) if closed else 0,
        },
        'updated_at': _now_iso(),
    }


@app.post('/api/portfolio')
async def portfolio_upsert(pos: PortfolioPosition):
    sym = pos.symbol.upper().replace('.JK', '')
    now = _now_iso()
    with _db_conn() as conn:
        existing = conn.execute('SELECT id FROM virtual_portfolio WHERE symbol = ?', (sym,)).fetchone()
        if existing:
            conn.execute('UPDATE virtual_portfolio SET qty=?, avg_price=?, target_price=?, stop_loss=?, notes=?, updated_at=? WHERE symbol=?',
                         (pos.qty, pos.avg_price, pos.target_price, pos.stop_loss, pos.notes, now, sym))
        else:
            conn.execute('INSERT INTO virtual_portfolio (symbol, qty, avg_price, target_price, stop_loss, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                         (sym, pos.qty, pos.avg_price, pos.target_price, pos.stop_loss, pos.notes, now, now))
        conn.commit()
    return await portfolio_summary()


@app.delete('/api/portfolio/{symbol}')
async def portfolio_delete(symbol: str):
    sym = symbol.upper().replace('.JK', '')
    with _db_conn() as conn:
        conn.execute('DELETE FROM virtual_portfolio WHERE symbol = ?', (sym,))
        conn.commit()
    return await portfolio_summary()


@app.get('/api/report/daily')
async def daily_report():
    stocks_resp = await list_stocks(limit=20, all=True)
    stocks = stocks_resp.get('stocks', [])
    buys = [s for s in stocks if s.get('signal') == 'BUY'][:5]
    sells = [s for s in stocks if s.get('signal') == 'SELL'][:5]
    portfolio = await portfolio_summary()
    return {
        'headline': 'Laporan harian siap: lihat BUY kuat, SELL/hindari, dan posisi porto.',
        'buy_now': buys,
        'sell_or_avoid': sells,
        'portfolio': portfolio['summary'],
        'rule': 'BUY punya target 7 hari + stop loss. Cek tiap hari. Sinyal dievaluasi 30 hari untuk learning.',
        'updated_at': _now_iso(),
    }


@app.get('/api/market-summary')
async def market_summary():
    """
    Return IHSG index data (^JKSE). Cached for 60s.
    """
    now = time.time()
    cached = _market_summary_cache.get('data')
    if cached and (now - cached['timestamp']) < 60:
        return cached['data']

    try:
        ihsg = yf.Ticker('^JKSE')
        info = ihsg.info
        history = ihsg.history(period='2d')
    except Exception as e:
        logger.error('market_summary failed: %s', e)
        raise HTTPException(status_code=502, detail='Gagal mengambil data IHSG')

    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
    if current_price is None and not history.empty:
        current_price = float(history['Close'].iloc[-1])

    prev_close = info.get('previousClose')
    if prev_close is None and len(history) >= 2:
        prev_close = float(history['Close'].iloc[-2])

    change = 0.0
    change_percent = 0.0
    if prev_close and current_price:
        change = round(current_price - prev_close, 2)
        change_percent = round((change / prev_close) * 100, 2)

    result = {
        'name': 'IHSG — Indeks Harga Saham Gabungan',
        'symbol': '^JKSE',
        'price': current_price,
        'change': change,
        'change_percent': change_percent,
        'high_52w': info.get('fiftyTwoWeekHigh'),
        'low_52w': info.get('fiftyTwoWeekLow'),
        'volume': info.get('volume'),
        'updated_at': _now_iso(),
    }
    _market_summary_cache['data'] = {'data': result, 'timestamp': now}
    return result


@app.get('/health')
async def health():
    return {'status': 'ok', 'service': 'saham-app-api'}

