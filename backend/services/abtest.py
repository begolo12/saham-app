"""A/B Test Framework (S13).

Simple split: hash(symbol + date) % 2 == 0 -> v1, else v2.
Tracks version used in signal_recommendations.signal_version.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.db import _db_conn, USE_POSTGRES

logger = logging.getLogger('saham-api')


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def get_signal_version(symbol: str) -> str:
    """Return 'v1' or 'v2' based on hash of symbol + today's date."""
    raw = f'{symbol.upper()}:{_today_str()}'
    h = hashlib.md5(raw.encode('utf-8')).hexdigest()
    return 'v1' if int(h, 16) % 2 == 0 else 'v2'


def _compute_v1_signal(tech: Dict[str, Any], fund: Dict[str, Any]) -> Dict[str, Any]:
    """V1: equal-weight technical + fundamental (existing approach)."""
    return {
        'signal': tech.get('signal', 'NEUTRAL'),
        'strength': (tech.get('strength', 50) + fund.get('strength', 50)) // 2,
        'reasons': tech.get('reasons', []) + fund.get('reasons', []),
    }


def _compute_v2_signal(tech: Dict[str, Any], fund: Dict[str, Any]) -> Dict[str, Any]:
    """V2: technical-weighted (70/30) with stronger threshold.

    - Tech weighs 70%, fundamental 30%
    - BUY threshold raised to 70, SELL threshold lowered to 30
    """
    strength = int(round(tech.get('strength', 50) * 0.7 + fund.get('strength', 50) * 0.3))
    strength = max(1, min(100, strength))

    if strength >= 70:
        signal = 'BUY'
    elif strength <= 30:
        signal = 'SELL'
    else:
        signal = 'NEUTRAL'

    return {
        'signal': signal,
        'strength': strength,
        'reasons': [
            '[V2] ' + r for r in tech.get('reasons', [])
        ] + [
            '[V2-Fund] ' + r for r in fund.get('reasons', [])
        ],
    }


def compute_signal(symbol: str, tech: Dict[str, Any],
                   fund: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Compute signal using A/B test versioning.

    Returns (signal_version, signal_dict).
    """
    version = get_signal_version(symbol)
    if version == 'v2':
        return version, _compute_v2_signal(tech, fund)
    return version, _compute_v1_signal(tech, fund)


def compare_versions() -> Dict[str, Any]:
    """Compare accuracy between v1 and v2 from signal_recommendations.

    Returns dict with per-version win rates, counts, and comparison.
    """
    with _db_conn() as conn:
        rows = conn.execute(
            '''SELECT signal_version, is_correct, COUNT(*) as cnt
               FROM signal_recommendations
               WHERE signal_version IS NOT NULL
                 AND signal_version IN ('v1', 'v2')
                 AND is_correct IS NOT NULL
               GROUP BY signal_version, is_correct''',
        ).fetchall()

    stats: Dict[str, Dict[str, float]] = {'v1': {'wins': 0, 'total': 0}, 'v2': {'wins': 0, 'total': 0}}
    for row in rows:
        v = row['signal_version']
        correct = int(row['is_correct'])
        cnt = int(row['cnt'])
        if v in stats:
            stats[v]['total'] += cnt
            if correct == 1:
                stats[v]['wins'] += cnt

    result: Dict[str, Any] = {
        'v1': {
            'wins': int(stats['v1']['wins']),
            'total': int(stats['v1']['total']),
            'win_rate': round(stats['v1']['wins'] / stats['v1']['total'], 4) if stats['v1']['total'] > 0 else 0.0,
        },
        'v2': {
            'wins': int(stats['v2']['wins']),
            'total': int(stats['v2']['total']),
            'win_rate': round(stats['v2']['wins'] / stats['v2']['total'], 4) if stats['v2']['total'] > 0 else 0.0,
        },
    }
    wr1 = result['v1']['win_rate']
    wr2 = result['v2']['win_rate']
    if wr1 > 0 and wr2 > 0:
        if wr2 > wr1:
            result['winner'] = 'v2'
            result['improvement'] = round((wr2 - wr1) / wr1 * 100, 2)
        elif wr1 > wr2:
            result['winner'] = 'v1'
            result['improvement'] = round((wr1 - wr2) / wr2 * 100, 2)
        else:
            result['winner'] = 'tie'
            result['improvement'] = 0.0
    else:
        result['winner'] = 'insufficient_data'
        result['improvement'] = 0.0

    return result
