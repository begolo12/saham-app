import math
from typing import Dict, Any

from fastapi import Depends

from app import app
from schemas.portfolio import PositionCreate
from stock_data import get_top_stocks
from services.db import (
    _now_iso, _db_conn, current_user,
)


def _clean_float(v):
    """Replace NaN / +Inf / -Inf with None so JSON serialization never 500s.

    Mirrors routes.stocks._clean_float — kept local so portfolio can sanitize
    its own payloads without depending on import order.
    """
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, dict):
        return {k: _clean_float(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_clean_float(item) for item in v]
    if isinstance(v, tuple):
        return tuple(_clean_float(item) for item in v)
    return v


def _safe_price(raw, fallback):
    """Coerce a price to float, falling back if raw is None/NaN/Inf."""
    try:
        if raw is None:
            return float(fallback)
        f = float(raw)
        if math.isnan(f) or math.isinf(f):
            return float(fallback)
        return f
    except (TypeError, ValueError):
        return float(fallback)


@app.get('/api/portfolio')
async def portfolio_summary(user: Dict[str, Any] = Depends(current_user)):
    stocks = {s['symbol'].replace('.JK', '').upper(): s for s in get_top_stocks()}
    with _db_conn() as conn:
        rows = conn.execute('SELECT * FROM virtual_portfolio WHERE user_id = ? ORDER BY symbol', (user['id'],)).fetchall()
    positions = []
    total_cost = 0.0
    total_value = 0.0
    winners = 0
    losers = 0
    for row in rows:
        sym = row['symbol'].replace('.JK', '').upper()
        stock = stocks.get(sym) or {}
        current = _safe_price(stock.get('price'), row['avg_price'])
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
    payload = {
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
    return _clean_float(payload)


@app.post('/api/portfolio')
async def portfolio_upsert(pos: PositionCreate, user: Dict[str, Any] = Depends(current_user)):
    sym = pos.symbol.upper().replace('.JK', '')
    now = _now_iso()
    with _db_conn() as conn:
        existing = conn.execute('SELECT id FROM virtual_portfolio WHERE user_id = ? AND symbol = ?', (user['id'], sym)).fetchone()
        if existing:
            conn.execute('UPDATE virtual_portfolio SET qty=?, avg_price=?, target_price=?, stop_loss=?, notes=?, updated_at=? WHERE user_id=? AND symbol=?',
                         (pos.qty, pos.avg_price, pos.target_price, pos.stop_loss, pos.notes, now, user['id'], sym))
        else:
            conn.execute('INSERT INTO virtual_portfolio (user_id, symbol, qty, avg_price, target_price, stop_loss, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (user['id'], sym, pos.qty, pos.avg_price, pos.target_price, pos.stop_loss, pos.notes, now, now))
        conn.commit()
    return await portfolio_summary(user)


@app.delete('/api/portfolio/{symbol}')
async def portfolio_delete(symbol: str, user: Dict[str, Any] = Depends(current_user)):
    sym = symbol.upper().replace('.JK', '')
    with _db_conn() as conn:
        conn.execute('DELETE FROM virtual_portfolio WHERE user_id = ? AND symbol = ?', (user['id'], sym))
        conn.commit()
    return await portfolio_summary(user)


@app.get('/api/report/daily')
async def daily_report(user: Dict[str, Any] = Depends(current_user)):
    from routes.stocks import list_stocks
    stocks_resp = await list_stocks(limit=20, all=False)
    stocks = stocks_resp.get('stocks', [])
    buys = [s for s in stocks if s.get('signal') == 'BUY'][:5]
    sells = [s for s in stocks if s.get('signal') == 'SELL'][:5]
    portfolio = await portfolio_summary(user)
    payload = {
        'headline': 'Laporan harian siap: lihat BUY kuat, SELL/hindari, dan posisi porto.',
        'buy_now': buys,
        'sell_or_avoid': sells,
        'portfolio': portfolio['summary'],
        'rule': 'BUY punya target 7 hari + stop loss. Cek tiap hari. Sinyal dievaluasi 7 hari untuk learning.',
        'updated_at': _now_iso(),
    }
    return _clean_float(payload)
