"""Signal Accuracy Dashboard API (S11).

Endpoints:
  GET /api/accuracy         — full accuracy dashboard
  GET /api/accuracy/summary — compact summary
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from app import app
from services.db import _db_conn, USE_POSTGRES, _now_iso
from services.abtest import compare_versions

logger = logging.getLogger('saham-api')


def _win_rate_per_signal() -> List[Dict[str, Any]]:
    """Win rate per signal type (BUY/SELL/NEUTRAL)."""
    with _db_conn() as conn:
        rows = conn.execute(
            '''SELECT recommendation, is_correct, COUNT(*) as cnt
               FROM signal_recommendations
               WHERE is_correct IS NOT NULL
               GROUP BY recommendation, is_correct''',
        ).fetchall()
    stats: Dict[str, Dict[str, float]] = {}
    for row in rows:
        rec = row['recommendation']
        correct = int(row['is_correct'])
        cnt = int(row['cnt'])
        if rec not in stats:
            stats[rec] = {'wins': 0, 'total': 0}
        stats[rec]['total'] += cnt
        if correct == 1:
            stats[rec]['wins'] += cnt
    result = []
    for rec, s in sorted(stats.items()):
        result.append({
            'signal_type': rec,
            'wins': int(s['wins']),
            'total': int(s['total']),
            'win_rate': round(s['wins'] / s['total'], 4) if s['total'] > 0 else 0.0,
        })
    return result


def _accuracy_over_time() -> List[Dict[str, Any]]:
    """Accuracy over time in monthly buckets."""
    with _db_conn() as conn:
        if USE_POSTGRES:
            rows = conn.execute(
                '''SELECT substr(created_at, 1, 7) as month,
                          AVG(CASE WHEN is_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy,
                          COUNT(*) as total
                   FROM signal_recommendations
                   WHERE is_correct IS NOT NULL
                   GROUP BY month
                   ORDER BY month ASC'''
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT substr(created_at, 1, 7) as month,
                          AVG(CASE WHEN is_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy,
                          COUNT(*) as total
                   FROM signal_recommendations
                   WHERE is_correct IS NOT NULL
                   GROUP BY substr(created_at, 1, 7)
                   ORDER BY month ASC'''
            ).fetchall()
    return [
        {'month': r['month'], 'accuracy': round(float(r['accuracy']), 4), 'total': int(r['total'])}
        for r in rows
    ]


def _confusion_matrix() -> Dict[str, Any]:
    """Build confusion matrix: actual direction vs predicted signal."""
    with _db_conn() as conn:
        rows = conn.execute(
            '''SELECT recommendation, outcome, COUNT(*) as cnt
               FROM signal_recommendations
               WHERE is_correct IS NOT NULL AND outcome IS NOT NULL
               GROUP BY recommendation, outcome''',
        ).fetchall()
    matrix: Dict[str, Dict[str, int]] = {}
    for row in rows:
        rec = row['recommendation'] or 'UNKNOWN'
        outcome = row['outcome'] or 'unknown'
        if rec not in matrix:
            matrix[rec] = {}
        matrix[rec][outcome] = int(row['cnt'])
    return {
        'matrix': matrix,
        'labels': list(matrix.keys()),
    }


def _performance_metrics() -> Dict[str, Any]:
    """Sharpe ratio-like metric, avg return, max drawdown."""
    with _db_conn() as conn:
        rows = conn.execute(
            '''SELECT return_pct, is_correct, outcome
               FROM signal_recommendations
               WHERE return_pct IS NOT NULL AND is_correct IS NOT NULL''',
        ).fetchall()

    returns = [float(r['return_pct']) for r in rows]
    if not returns:
        return {'avg_return': 0.0, 'max_drawdown': 0.0, 'sharpe_ratio': 0.0, 'total_signals_evaluated': 0}

    avg_ret = round(sum(returns) / len(returns), 4)
    max_dd = round(min(returns), 2) if returns else 0.0
    # Approximate Sharpe: mean / std * sqrt(252) — using daily-like returns (stocks moved over ~7 day horizon)
    std = pd.Series(returns).std()
    sharpe = round((avg_ret / std) * (252 ** 0.5), 4) if std > 0 else 0.0

    return {
        'avg_return': avg_ret,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'total_signals_evaluated': len(returns),
    }


# ═══════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════


@app.get('/api/accuracy')
async def accuracy_dashboard():
    """Full accuracy dashboard."""
    return {
        'win_rate_per_signal': _win_rate_per_signal(),
        'accuracy_over_time': _accuracy_over_time(),
        'confusion_matrix': _confusion_matrix(),
        'performance': _performance_metrics(),
        'version_comparison': compare_versions(),
        'updated_at': _now_iso(),
    }


@app.get('/api/accuracy/summary')
async def accuracy_summary():
    """Compact accuracy summary."""
    perf = _performance_metrics()
    win_rates = _win_rate_per_signal()
    overall_wins = sum(w['wins'] for w in win_rates)
    overall_total = sum(w['total'] for w in win_rates)
    return {
        'overall_win_rate': round(overall_wins / overall_total, 4) if overall_total > 0 else 0.0,
        'total_evaluated': overall_total,
        'avg_return': perf['avg_return'],
        'sharpe_ratio': perf['sharpe_ratio'],
        'accuracy_over_time': _accuracy_over_time()[-6:],  # last 6 months
        'updated_at': _now_iso(),
    }
