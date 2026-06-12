# Scanner service

Long-running scanner that covers the full ~950-ticker IDX universe and
publishes the result to the shared Postgres cache so the Vercel API
server can serve it instantly.

## What it does

Every `SCAN_INTERVAL` seconds (default 60s):
1. Reads `backend/data/idx_universe.txt` (951 tickers)
2. Fans out 80 threads to yfinance (configurable via `SCAN_WORKERS`)
3. Computes per-stock signal (potential_score, RSI, MACD, …)
4. Sorts by signal strength
5. Persists the snapshot to Neon (`scanner_results` table)

The Vercel API server reads from the same table on every `/api/stocks`
request — so the user-facing backend never blocks on yfinance and
isn't subject to Vercel's 30s function timeout.

## Run locally

```bash
export DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"
python -m scanner.scanner
# → HTTP on :8765, /health and /latest
```

## Run on the NAS

```bash
cd /volume1/docker/compose
cp /path/to/saham-app/scanner/docker-compose.yml ./saham-scanner.yml
# add NEON_DATABASE_URL to .env in this dir
docker compose -f saham-scanner.yml up -d
docker logs -f saham-scanner
```

## Environment

| Var | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | Required for persistence |
| `SCAN_INTERVAL` | 60 | Seconds between scans |
| `SCAN_WORKERS` | 80 | Thread pool size |
| `SCAN_BUDGET` | 120 | Per-scan wall-clock budget (s) |
| `MAX_UNIVERSE` | 0 | Cap, 0 = full 951 |
| `PORT` | 8765 | HTTP server port |
| `LOG_LEVEL` | INFO | — |

## Endpoints

- `GET /health` — `200` if a fresh scan exists, `503` if stale
- `GET /latest` — last cached snapshot from Neon
