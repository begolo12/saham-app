from app import app
from services.db import _evaluate_learning_batch, _db_conn, _now_iso


@app.post('/api/learning/evaluate')
async def learning_evaluate(limit: int = 50):
    """Evaluate recommendations older than 7 days against latest available price."""
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
        'rule': 'BUY benar jika return 7 hari > 0%; SELL benar jika return < 0%; HOLD benar jika return di antara -5% sampai +5%.',
        'updated_at': _now_iso(),
    }
