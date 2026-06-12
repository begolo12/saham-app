"""Tests for save/load of the shared scanner_results cache.

Uses SQLite (the local dev/test path). The Postgres branch uses the same
function signatures, so we don't need a real Neon to test the logic.
"""
import os
import time
import pytest

# Force SQLite (no DATABASE_URL) before importing db module
os.environ.pop('DATABASE_URL', None)
os.environ.pop('DATABASE_URL_UNPOOLED', None)

from services.db import (  # noqa: E402
    _init_db, save_scanner_result, load_latest_scanner_result,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Point the SQLite cache at a temp file and (re)create tables."""
    db = tmp_path / 'test_scanner.db'
    monkeypatch.setattr('services.db.DB_PATH', str(db), raising=False)
    _init_db()
    yield
    try:
        db.unlink()
    except FileNotFoundError:
        pass


def test_save_then_load_returns_payload():
    rows = [
        {'symbol': 'BBCA', 'price': 10250, 'potential_score': 88},
        {'symbol': 'BBRI', 'price': 5650, 'potential_score': 84},
    ]
    save_scanner_result(rows, duration_ms=1500)

    out = load_latest_scanner_result(max_age_seconds=60)
    assert out is not None
    assert out['count'] == 2
    assert out['duration_ms'] == 1500
    assert len(out['rows']) == 2
    assert out['rows'][0]['symbol'] == 'BBCA'
    assert out['rows'][0]['price'] == 10250


def test_save_overwrites_previous_snapshot():
    """A second save_scanner_result replaces the first (single-row table)."""
    save_scanner_result([{'symbol': 'OLD'}], duration_ms=100)
    save_scanner_result(
        [{'symbol': 'NEW1'}, {'symbol': 'NEW2'}, {'symbol': 'NEW3'}],
        duration_ms=200,
    )
    out = load_latest_scanner_result(max_age_seconds=60)
    assert out['count'] == 3
    assert [r['symbol'] for r in out['rows']] == ['NEW1', 'NEW2', 'NEW3']


def test_stale_snapshot_returns_none(monkeypatch):
    """A snapshot older than max_age_seconds is treated as missing."""
    # Pre-write the table with a snapshot from 10 minutes ago
    save_scanner_result([{'symbol': 'STALE'}], duration_ms=100)
    # Patch the in-memory timestamp parser by lying about the row's scanned_at
    import services.db as db_mod
    original = db_mod._now_iso

    def _ten_min_ago():
        # Return a timestamp 10 minutes before original now — but the snapshot
        # was just written, so we need to overwrite it directly.
        from datetime import datetime, timezone, timedelta
        return (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    monkeypatch.setattr(db_mod, '_now_iso', _ten_min_ago)
    save_scanner_result([{'symbol': 'STALE'}], duration_ms=100)
    monkeypatch.undo()

    out = load_latest_scanner_result(max_age_seconds=60)
    assert out is None


def test_empty_save_is_a_noop():
    """save_scanner_result([]) must not write a useless empty snapshot."""
    save_scanner_result([], duration_ms=0)
    out = load_latest_scanner_result(max_age_seconds=60)
    # No prior write — should still be None
    assert out is None
