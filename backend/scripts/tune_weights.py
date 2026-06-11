"""S2b: Weight tuning script.

Grid-search for optimal signal weights by:
  1. Walking-forward over the last 365 days for each tracked symbol
     to collect per-window component scores (TA, Fund, Sent, Vol, Regime)
     and forward returns.
  2. Scoring every (TA, Fund, Sent, Vol, Regime) weight combination
     using win rate, Sharpe ratio, and average return.
  3. Picking the combination that maximizes the composite score.
  4. Writing the best weights to the ``signal_weights`` table for every
     symbol evaluated and the default (empty-symbol) row.

Run manually:
    cd backend
    python -m scripts.tune_weights
    python -m scripts.tune_weights --days 180 --top-n 10
"""

import argparse
import logging
import sys
from datetime import datetime, timezone, timedelta
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis import (
    detect_market_regime,
    generate_fundamental_signal,
    generate_technical_signal,
)
from services.db import (
    _get_signal_weights,
    _upsert_signal_weights,
)
from stock_data import get_stock_history, get_stock_info, get_top_stocks

logger = logging.getLogger('saham-api')

# Grid search ranges — per spec:
#   TA 0.2-0.5, Fund 0.2-0.5, Sent 0.1-0.3, Vol 0.05-0.2, Regime 0.05-0.2
# Step 0.1 keeps search tractable (~720 combos).
GRID_TA = [0.2, 0.3, 0.4, 0.5]
GRID_FUND = [0.2, 0.3, 0.4, 0.5]
GRID_SENT = [0.1, 0.2, 0.3]
GRID_VOL = [0.05, 0.10, 0.15, 0.20]
GRID_REGIME = [0.05, 0.10, 0.15, 0.20]

DEFAULT_WEIGHTS = {
    'ta_weight': 0.3,
    'fund_weight': 0.3,
    'sent_weight': 0.2,
    'vol_weight': 0.1,
    'regime_weight': 0.1,
}

MIN_WINDOW = 60       # need this many days for indicator computation
STEP_DAYS = 5         # re-evaluate every N trading days
HORIZON = 7           # check price N days later


# ── Component extraction ──────────────────────────────────────────

def _compute_components(window: pd.DataFrame, info: Dict[str, Any]) -> Dict[str, float]:
    """Compute the 5 component scores (1-100) for a single window.

    Mirrors the logic in ``analysis.combine_signals`` so that the grid
    search evaluates the same scoring function with different weights.
    """
    try:
        tech = generate_technical_signal(window)
    except Exception:
        tech = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

    try:
        fund = generate_fundamental_signal(info or {})
    except Exception:
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

    ta_score = float(tech.get('strength', 50))
    fund_score = float(fund.get('strength', 50))

    # Sentiment score — derived from tech/fund signal agreement
    tech_sig = tech.get('signal', 'NEUTRAL')
    fund_sig = fund.get('signal', 'NEUTRAL')
    sent_signals = [
        1 if tech_sig == 'BUY' else (-1 if tech_sig == 'SELL' else 0),
        1 if fund_sig == 'BUY' else (-1 if fund_sig == 'SELL' else 0),
    ]
    sent_score = 50 + (np.mean(sent_signals) if sent_signals else 0) * 40
    sent_score = max(1.0, min(100.0, sent_score))

    # Volume score
    vol_score = 50.0
    if not window.empty and 'volume' in window.columns:
        vol_series = window['volume'].dropna()
        if len(vol_series) >= 20:
            current_vol = float(vol_series.iloc[-1])
            avg_vol = float(vol_series.tail(20).mean())
            if avg_vol > 0:
                vol_ratio = current_vol / avg_vol
                if vol_ratio > 1.5:
                    vol_score = 75
                elif vol_ratio < 0.7:
                    vol_score = 25
                else:
                    vol_score = 50

    # Regime score
    regime_str = 'ranging'
    try:
        close = window['close'] if 'close' in window.columns else window.get('Close', pd.Series(dtype=float))
        if not close.empty:
            regime_info = detect_market_regime(close)
            regime_str = regime_info.get('regime', 'ranging')
    except Exception:
        pass

    if regime_str == 'trending_up':
        regime_score = 70
    elif regime_str == 'trending_down':
        regime_score = 30
    elif regime_str == 'volatile':
        regime_score = 40
    else:
        regime_score = 50

    return {
        'ta': ta_score,
        'fund': fund_score,
        'sent': sent_score,
        'vol': vol_score,
        'regime': regime_score,
    }


# ── Window gathering ──────────────────────────────────────────────

def _gather_windows(symbols: List[str], days: int = 365) -> List[Dict[str, Any]]:
    """Walk-forward over each symbol to collect (components, forward return)."""
    rows: List[Dict[str, Any]] = []
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)

    for sym in symbols:
        full = sym if sym.endswith('.JK') else sym + '.JK'
        try:
            df = get_stock_history(full, period='1y')
        except Exception as exc:
            logger.debug('Skipping %s: %s', full, exc)
            continue
        if df is None or df.empty or len(df) < MIN_WINDOW + HORIZON + 5:
            continue

        # Filter to date range (if index is datetime)
        try:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        except Exception:
            pass
        if len(df) < MIN_WINDOW + HORIZON + 5:
            continue

        try:
            info = get_stock_info(full) or {}
        except Exception:
            info = {}

        for i in range(MIN_WINDOW, len(df) - HORIZON, STEP_DAYS):
            window = df.iloc[:i]
            lookahead = df.iloc[i:i + HORIZON]
            if lookahead.empty:
                continue
            try:
                entry = float(window['close'].iloc[-1])
                future = float(lookahead['close'].iloc[-1])
            except Exception:
                continue
            if entry <= 0:
                continue
            ret = round(((future - entry) / entry) * 100, 2)

            try:
                comp = _compute_components(window, info)
            except Exception:
                continue
            rows.append({
                'symbol': sym,
                'ta': comp['ta'],
                'fund': comp['fund'],
                'sent': comp['sent'],
                'vol': comp['vol'],
                'regime': comp['regime'],
                'return_pct': ret,
                'entry_price': entry,
            })

    return rows


# ── Scoring ───────────────────────────────────────────────────────

def _score_weights(weights: Dict[str, float],
                   windows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate win rate, avg return, Sharpe for a weight configuration."""
    w_ta = float(weights.get('ta_weight', 0))
    w_fund = float(weights.get('fund_weight', 0))
    w_sent = float(weights.get('sent_weight', 0))
    w_vol = float(weights.get('vol_weight', 0))
    w_regime = float(weights.get('regime_weight', 0))

    total_w = w_ta + w_fund + w_sent + w_vol + w_regime
    if total_w <= 0:
        return {'win_rate': 0, 'avg_return': 0, 'sharpe_ratio': 0, 'total_trades': 0}
    w_ta /= total_w
    w_fund /= total_w
    w_sent /= total_w
    w_vol /= total_w
    w_regime /= total_w

    trades: List[Dict[str, Any]] = []
    for w in windows:
        ensemble = (
            w_ta * w['ta']
            + w_fund * w['fund']
            + w_sent * w['sent']
            + w_vol * w['vol']
            + w_regime * w['regime']
        )
        ensemble = max(1.0, min(100.0, ensemble))
        if ensemble >= 65:
            sig = 'BUY'
        elif ensemble <= 35:
            sig = 'SELL'
        else:
            continue
        is_correct = (sig == 'BUY' and w['return_pct'] > 0) or (
            sig == 'SELL' and w['return_pct'] < 0
        )
        trades.append({
            'signal': sig,
            'return_pct': w['return_pct'],
            'is_correct': is_correct,
        })

    if not trades:
        return {'win_rate': 0, 'avg_return': 0, 'sharpe_ratio': 0, 'total_trades': 0}

    total = len(trades)
    wins = sum(1 for t in trades if t['is_correct'])
    win_rate = round(wins / total * 100, 2)
    rets = [t['return_pct'] for t in trades]
    avg_return = round(float(np.mean(rets)), 2)

    if len(rets) > 1:
        std = float(np.std(rets, ddof=1))
        sharpe = round((np.mean(rets) / std) * np.sqrt(252 / 5), 4) if std > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        'win_rate': win_rate,
        'avg_return': avg_return,
        'sharpe_ratio': sharpe,
        'total_trades': total,
    }


def _composite_score(metrics: Dict[str, Any]) -> float:
    """Combine win rate, Sharpe, and avg return into a single score."""
    if metrics.get('total_trades', 0) < 3:
        return -1000.0
    return (
        metrics['win_rate']
        + 5.0 * metrics['sharpe_ratio']
        + 0.1 * metrics['avg_return']
    )


# ── Grid search ───────────────────────────────────────────────────

def grid_search(windows: List[Dict[str, Any]]) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Run grid search over weight combinations.

    Returns ``(best_weights, best_metrics)``.
    """
    combos = list(product(GRID_TA, GRID_FUND, GRID_SENT, GRID_VOL, GRID_REGIME))
    logger.info('Grid search: %d combinations over %d windows', len(combos), len(windows))

    best_weights = dict(DEFAULT_WEIGHTS)
    best_metrics = _score_weights(best_weights, windows)
    best_score = _composite_score(best_metrics)

    for ta, fund, sent, vol, regime in combos:
        weights = {
            'ta_weight': ta,
            'fund_weight': fund,
            'sent_weight': sent,
            'vol_weight': vol,
            'regime_weight': regime,
        }
        m = _score_weights(weights, windows)
        s = _composite_score(m)
        if s > best_score:
            best_score = s
            best_weights = weights
            best_metrics = m

    return best_weights, best_metrics


# ── Apply best weights to DB ──────────────────────────────────────

def apply_weights(symbols: List[str], weights: Dict[str, float]) -> int:
    """Upsert weights for every symbol and the default (empty) row.

    Returns number of rows updated.
    """
    updated = 0
    for sym in symbols:
        try:
            _upsert_signal_weights(sym, weights)
            updated += 1
        except Exception as exc:
            logger.warning('Failed to update weights for %s: %s', sym, exc)
    try:
        _upsert_signal_weights('', weights)
        updated += 1
    except Exception as exc:
        logger.warning('Failed to update default weights: %s', exc)
    return updated


# ── Public entry points ──────────────────────────────────────────

def run_tune(days: int = 365,
             symbols: Optional[List[str]] = None,
             top_n: int = 20) -> Dict[str, Any]:
    """Run weight tuning. Returns a summary dict (or None on no data)."""
    if not symbols:
        try:
            raw = get_top_stocks()[:top_n]
            # get_top_stocks returns List[Dict] with 'symbol' key
            symbols = []
            for item in raw:
                if isinstance(item, dict):
                    sym = item.get('symbol')
                    if sym:
                        symbols.append(sym)
                elif isinstance(item, str):
                    symbols.append(item)
        except Exception as exc:
            logger.warning('Could not fetch top stocks: %s', exc)
            symbols = []

    if not symbols:
        logger.warning('No symbols available for tuning; aborting')
        return {
            'status': 'no_symbols',
            'best_weights': dict(DEFAULT_WEIGHTS),
            'best_metrics': _score_weights(DEFAULT_WEIGHTS, []),
        }

    logger.info('Tune weights: %d symbols, %d days', len(symbols), days)
    windows = _gather_windows(symbols, days=days)
    if not windows:
        logger.warning('No windows gathered; keeping current weights')
        return {
            'status': 'no_windows',
            'best_weights': _get_signal_weights('') if hasattr(_get_signal_weights, '__call__') else dict(DEFAULT_WEIGHTS),
            'best_metrics': {'win_rate': 0, 'avg_return': 0, 'sharpe_ratio': 0, 'total_trades': 0},
            'symbols_tuned': 0,
            'windows_evaluated': 0,
        }

    best_weights, best_metrics = grid_search(windows)
    updated = apply_weights(symbols, best_weights)

    summary = {
        'status': 'ok',
        'best_weights': best_weights,
        'best_metrics': best_metrics,
        'symbols_tuned': len(symbols),
        'windows_evaluated': len(windows),
        'db_rows_updated': updated,
    }
    logger.info('Tune complete: win_rate=%.2f%% avg_return=%.2f%% sharpe=%.4f (trades=%d, rows=%d)',
                best_metrics['win_rate'], best_metrics['avg_return'],
                best_metrics['sharpe_ratio'], best_metrics['total_trades'], updated)
    return summary


# ── CLI ───────────────────────────────────────────────────────────

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Tune signal weights via grid search.')
    parser.add_argument('--days', type=int, default=365, help='Lookback window in days')
    parser.add_argument('--top-n', type=int, default=20, help='Number of top stocks to evaluate')
    parser.add_argument('--symbols', type=str, default=None,
                        help='Comma-separated symbol list (overrides --top-n)')
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )
    args = _parse_args(argv)

    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]

    summary = run_tune(days=args.days, symbols=symbols, top_n=args.top_n)
    print('\n=== Weight Tuning Summary ===')
    for k, v in summary.items():
        print(f'  {k}: {v}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
