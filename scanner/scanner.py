"""Saham ID scanner service — runs on the NAS, scans all 951 IDX stocks.

Designed to run as a long-lived Docker container on the NAS. Every 60
seconds it:
  1. Reads the full universe from data/idx_universe.txt
  2. Fans out 80 workers via yfinance
  3. Computes per-stock signal (potential_score, RSI, MACD, etc.)
  4. Sorts by signal strength
  5. Persists the snapshot to Neon via the same backend module

The Vercel API server reads from the same Neon table
(`scanner_results`) on every /api/stocks call — so the user-facing
backend never blocks on yfinance or hits a timeout.

A small HTTP server on PORT (default 8765) exposes:
  GET /health  — liveness + last scan timestamp
  GET /latest  — last cached snapshot (read from Neon)

Environment variables:
  DATABASE_URL  — Neon connection string (required)
  SCAN_INTERVAL — seconds between scans (default 60)
  SCAN_WORKERS  — thread-pool size (default 80)
  SCAN_BUDGET   — per-scan wall-clock budget in seconds (default 120)
  MAX_UNIVERSE  — cap the list size, default 0 = use all
  PORT          — HTTP port for /health and /latest (default 8765)
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Dict, Any, Optional

# Make the backend module importable — we reuse its _fetch_stock_card
_BACKEND = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(_BACKEND))

from stock_data import _fetch_stock_card, _load_full_universe  # noqa: E402
from services.db import save_scanner_result, load_latest_scanner_result, USE_POSTGRES  # noqa: E402

logger = logging.getLogger('saham-scanner')
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

SCAN_INTERVAL = int(os.environ.get('SCAN_INTERVAL', '60'))
SCAN_WORKERS = int(os.environ.get('SCAN_WORKERS', '80'))
SCAN_BUDGET = int(os.environ.get('SCAN_BUDGET', '120'))
MAX_UNIVERSE = int(os.environ.get('MAX_UNIVERSE', '0'))

_shutdown = threading.Event()

# Set by the scan loop after each completed persistence — used by /health
_last_scan_ts: Optional[float] = None
_last_scan_count: Optional[int] = None
_last_scan_duration_ms: Optional[int] = None
_stats_lock = threading.Lock()


def _scan_once():
    """Run a single scan of the full IDX universe. Returns (rows, duration_ms)."""
    universe = _load_full_universe()
    if MAX_UNIVERSE and MAX_UNIVERSE < len(universe):
        universe = universe[:MAX_UNIVERSE]
    logger.info('scanning %d symbols with %d workers (budget %ds)',
                len(universe), SCAN_WORKERS, SCAN_BUDGET)

    start = time.time()
    results: List[Dict[str, Any]] = []
    failed = 0
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as executor:
        futures = {executor.submit(_fetch_stock_card, sym): sym for sym in universe}
        deadline = start + SCAN_BUDGET
        try:
            for fut in as_completed(futures, timeout=SCAN_BUDGET + 5):
                if _shutdown.is_set():
                    break
                if time.time() > deadline:
                    logger.warning('deadline reached, aborting remaining futures')
                    break
                sym = futures[fut]
                try:
                    item = fut.result()
                except Exception as exc:
                    failed += 1
                    logger.debug('fetch failed %s: %s', sym, exc)
                    continue
                if item:
                    results.append(item)
        finally:
            for fut in futures:
                fut.cancel()

    results.sort(
        key=lambda x: (
            x.get('potential_score', 0),
            x.get('volume', 0),
            x.get('avg_value', 0),
        ),
        reverse=True,
    )
    duration = int((time.time() - start) * 1000)
    logger.info('scan complete: %d ok / %d failed in %d ms',
                len(results), failed, duration)
    return results, duration


def _scan_loop():
    """Main background loop. Scans every SCAN_INTERVAL seconds, persists result."""
    # Wait for Neon to be ready on cold boot
    if not USE_POSTGRES:
        logger.error('DATABASE_URL not set — scanner will only run in-memory, '
                     'but it cannot persist to the shared cache. Exiting.')
        return

    while not _shutdown.is_set():
        try:
            rows, duration = _scan_once()
            if rows:
                save_scanner_result(rows, duration)
                with _stats_lock:
                    global _last_scan_ts, _last_scan_count, _last_scan_duration_ms
                    _last_scan_ts = time.time()
                    _last_scan_count = len(rows)
                    _last_scan_duration_ms = duration
                logger.info('persisted %d rows (%d ms) to scanner_results',
                            len(rows), duration)
        except Exception as exc:
            logger.exception('scan iteration failed: %s', exc)

        # Sleep, but respond to shutdown quickly
        _shutdown.wait(SCAN_INTERVAL)
    logger.info('scan loop stopped')


class _Handler(BaseHTTPRequestHandler):
    """Tiny HTTP server: /health for k8s/NAS, /latest for Vercel fallback."""

    def log_message(self, *args, **kwargs):
        return  # silence default access log

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == '/health':
            with _stats_lock:
                last = _last_scan_ts
                count = _last_scan_count
                duration = _last_scan_duration_ms
            age = (time.time() - last) if last else None
            healthy = last is not None and age is not None and age < SCAN_INTERVAL * 3
            self._send_json(200 if healthy else 503, {
                'status': 'ok' if healthy else 'stale',
                'last_scan': last,
                'last_scan_age_seconds': age,
                'last_scan_count': count,
                'last_scan_duration_ms': duration,
                'scan_interval': SCAN_INTERVAL,
            })
            return
        if self.path == '/latest':
            try:
                payload = load_latest_scanner_result(max_age_seconds=SCAN_INTERVAL * 5)
            except Exception as exc:
                self._send_json(500, {'error': str(exc)})
                return
            if not payload:
                self._send_json(503, {'error': 'no scan yet'})
                return
            self._send_json(200, payload)
            return
        self._send_json(404, {'error': 'not found'})


def _http_server_thread():
    port = int(os.environ.get('PORT', '8765'))
    server = ThreadingHTTPServer(('0.0.0.0', port), _Handler)
    logger.info('HTTP server listening on :%d', port)
    try:
        server.serve_forever()
    except Exception:
        logger.exception('HTTP server crashed')
    finally:
        server.server_close()


def main():
    logger.info('saham-scanner starting (interval=%ds, workers=%d, budget=%ds, max_universe=%s)',
                SCAN_INTERVAL, SCAN_WORKERS, SCAN_BUDGET,
                MAX_UNIVERSE or 'all')

    # Graceful shutdown
    def _sig(*_):
        logger.info('shutdown signal received')
        _shutdown.set()
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    # If DATABASE_URL missing, scanner can still run in-memory (just won't persist)
    if not USE_POSTGRES:
        logger.warning('DATABASE_URL not set — scanner will not persist to shared cache')

    # Background threads
    scan_t = threading.Thread(target=_scan_loop, name='scan-loop', daemon=True)
    scan_t.start()
    http_t = threading.Thread(target=_http_server_thread, name='http', daemon=True)
    http_t.start()

    # Block main thread until shutdown
    while not _shutdown.is_set():
        _shutdown.wait(60)
    logger.info('bye')


if __name__ == '__main__':
    main()
