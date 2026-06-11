# SahamApp API Reference

**Base URL (dev):** `http://localhost:8774`
**Base URL (prod):** `https://<your-domain>/api`
**Interactive docs:** `/docs` (Swagger UI), `/redoc` (ReDoc)
**OpenAPI schema:** `/openapi.json`

Semua endpoint prefix `/api` kecuali `/health`, `/docs`, `/redoc`, `/openapi.json`.

---

## Daftar Isi

- [Authentication](#authentication)
- [Status Codes](#status-codes)
- [Error Format](#error-format)
- [Rate Limiting](#rate-limiting)
- [Caching Strategy](#caching-strategy)
- [Endpoints](#endpoints)
  - [Stocks & Scanner](#stocks--scanner)
  - [Market Data](#market-data)
  - [News & Sentiment](#news--sentiment)
  - [Auth & Users](#auth--users)
  - [Portfolio](#portfolio)
  - [Learning Engine](#learning-engine)
  - [Accuracy Dashboard](#accuracy-dashboard)
  - [Reports](#reports)
  - [System](#system)
- [Signal Logic](#signal-logic)
- [Data Models (Schemas)](#data-models-schemas)

---

## Authentication

SahamApp menggunakan **HMAC-SHA256 signed tokens** (tidak pakai library JWT eksternal — semua vanilla Python).

### Flow

```
1. POST /api/auth/login        → access_token + refresh_token
2. GET  /api/auth/me            Bearer <access_token>   → user info
3. POST /api/auth/refresh       refresh_token           → new access_token
4. GET  /api/portfolio          Bearer <access_token>   → positions
```

### Token Format

```
<base64(payload)>.<base64(hmac_sha256(secret, payload))>
```

**Payload** (JSON):
```json
{
  "user_id": 1,
  "username": "admin",
  "role": "superadmin",
  "iat": 1718100000,
  "exp": 1720692000
}
```

- **Access token TTL:** 30 hari
- **Refresh token TTL:** 30 hari (dapat dipakai sampai kadaluarsa)
- **Header:** `Authorization: Bearer <token>`

### Login Request

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

**Response 200:**
```json
{
  "token": "eyJ1c2VyX2lkIjogMSwgLi4ufQ.<sig>",
  "refresh_token": "eyJ1c2VyX2lkIjogMSwgLi4ufQ.<sig>",
  "user": {
    "id": 1,
    "username": "admin",
    "role": "superadmin"
  }
}
```

**Response 401:** `{"detail": "Username/password salah"}`

### Refresh Request

```http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

**Response 200:** Same as login response (new tokens).
**Response 401:** `{"detail": "Refresh token tidak valid atau kedaluwarsa"}`

### Me Request

```http
GET /api/auth/me
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "role": "superadmin"
  }
}
```

---

## Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Request berhasil |
| 400 | Bad Request | Payload tidak valid / bisnis error (mis. user duplicate) |
| 401 | Unauthorized | Token missing / invalid / expired |
| 403 | Forbidden | Token valid tapi role kurang (butuh superadmin) |
| 404 | Not Found | Saham tidak ditemukan / data historis kosong |
| 413 | Payload Too Large | Request body > 1 MB |
| 429 | Too Many Requests | Rate limit terlampaui (200/min) |
| 500 | Internal Server Error | Unhandled exception — lihat log |

---

## Error Format

Semua error response pakai schema konsisten:

```json
{
  "detail": "Pesan error dalam Bahasa Indonesia / English"
}
```

Contoh:
- `{"detail": "Saham XYZ tidak ditemukan"}`
- `{"detail": "Refresh token tidak valid atau kedaluwarsa"}`
- `{"detail": "Too many requests. Silakan coba lagi nanti."}`
- `{"detail": "Request terlalu besar. Maksimal 1 MB."}`
- `{"detail": "Internal server error. Please try again later."}`

---

## Rate Limiting

| Window | Max Requests | Scope |
|--------|--------------|-------|
| 60 detik | 200 req | per IP |

Implementasi: in-memory sliding window via `RateLimitMiddleware`. **Tidak didistribusi** antar instance — di Vercel serverless setiap invocation dapat state sendiri (efektif per-instance limit).

Skip: `/health` endpoint.

**Response 429:**
```json
{
  "detail": "Too many requests. Silakan coba lagi nanti."
}
```

---

## Caching Strategy

| Layer | Backend | TTL | Scope |
|-------|---------|-----|-------|
| L1 (memory) | Python dict | 15–1800s | per-process |
| L2 (Redis) | Upstash Redis | configurable | shared cross-instance |
| L3 (HTTP) | Browser/Service Worker | varies | client-side |

### Endpoint-level Cache

| Endpoint | TTL | Cache key |
|----------|-----|-----------|
| `/api/market-summary` | 15s | `data` (single) |
| `/api/news` (per-symbol) | 30 menit | `news:{symbol}:{limit}` |
| `/api/stocks/{symbol}/history` | session (no TTL) | internal yfinance cache |
| `/api/live/summary` | none | always fresh |

### Redis (Upstash) — Opsional

Jika `REDIS_URL` diset, `services/cache.py` (RedisClient) menjadi available. Cache key pattern: `cache:{namespace}:{key}`. Otomatis fallback ke in-memory jika Redis down.

---

## Endpoints

### Stocks & Scanner

#### `GET /api/stocks`

List saham top dengan sinyal cepat (RSI, trend, volume).

**Query params:**
- `limit` (int, opsional) — jumlah hasil (default 50, max 140+)
- `all` (bool, default `false`) — return full universe

**Response 200:**
```json
{
  "stocks": [
    {
      "symbol": "BBCA",
      "name": "Bank Central Asia Tbk.",
      "price": 10250,
      "change_percent": 0.5,
      "signal": "BUY",
      "signal_strength": 78,
      "sector": "Perbankan",
      "volume": 12345678,
      "avg_volume": 10000000,
      "potential_score": 88,
      "trend_5d": 1.2,
      "trend_20d": 3.4,
      "rsi14": 62.5,
      "volume_ratio": 1.23,
      "trade_plan": {
        "stop_loss": 9850,
        "take_profit": 11050,
        "risk_reward_ratio": 2.0,
        "horizon_days": 7
      }
    }
  ],
  "updated_at": "2026-06-11T08:30:00Z",
  "mode": "fast"
}
```

**Curl:**
```bash
curl http://localhost:8774/api/stocks
curl 'http://localhost:8774/api/stocks?all=true'
curl 'http://localhost:8774/api/stocks?limit=10'
```

---

#### `GET /api/stocks/search`

Search by symbol, name, atau sector.

**Query params:**
- `q` (str, required) — keyword, max 100 char, di-sanitize

**Response 200:**
```json
{
  "stocks": [ /* same shape as /api/stocks */ ],
  "query": "BBCA",
  "count": 3,
  "updated_at": "2026-06-11T08:30:00Z"
}
```

**Curl:**
```bash
curl 'http://localhost:8774/api/stocks/search?q=bank'
curl 'http://localhost:8774/api/stocks/search?q=antm'
```

---

#### `GET /api/stocks/batch`

Full technical + fundamental analysis untuk semua saham (parallel via `asyncio.gather`).

**Response 200:**
```json
{
  "stocks": [
    {
      "symbol": "BBCA",
      "name": "Bank Central Asia Tbk.",
      "price": 10250,
      "change_percent": 0.5,
      "sector": "Perbankan",
      "technical": {
        "signal": "BUY",
        "strength": 72,
        "rsi": 62.5
      },
      "fundamental": {
        "signal": "HOLD",
        "strength": 55,
        "pe_ratio": 18.5,
        "pbv": 4.2
      },
      "overall_signal": "BUY",
      "overall_strength": 65
    }
  ],
  "updated_at": "2026-06-11T08:30:00Z"
}
```

**Catatan:** Response time ~10 detik (network-bound ke yfinance). Jangan panggil sering.

---

#### `GET /api/stocks/{symbol}`

Detail lengkap satu saham: teknikal, fundamental, sentimen berita, trade plan.

**Path params:**
- `symbol` (str) — kode saham (tanpa suffix `.JK`)

**Response 200:**
```json
{
  "symbol": "BBCA",
  "name": "Bank Central Asia Tbk.",
  "price": 10250,
  "change": 50,
  "change_percent": 0.49,
  "sector": "Perbankan",
  "industry": "Banks—Regional",
  "market_cap": 1234567890000,
  "technical": {
    "rsi": 62.5,
    "macd_line": 25.3,
    "macd_signal": 20.1,
    "macd_histogram": 5.2,
    "sma_20": 10100,
    "sma_50": 9850,
    "bollinger_upper": 10500,
    "bollinger_middle": 10100,
    "bollinger_lower": 9700,
    "signal": "BUY",
    "strength": 72,
    "reasons": [
      "RSI 62.5 dalam zona normal",
      "Harga di atas SMA 50 — tren naik",
      "MACD golden cross terdeteksi"
    ]
  },
  "fundamental": {
    "pe_ratio": 18.5,
    "pbv": 4.2,
    "dividend_yield": 1.8,
    "eps": 555.0,
    "market_cap": 1234567890000,
    "high_52w": 11000,
    "low_52w": 8800,
    "signal": "HOLD",
    "strength": 55,
    "reasons": [
      "PER 18.5x — valuasi wajar",
      "Dividend yield 1.8% — dividen cukup"
    ]
  },
  "overall_signal": "BUY",
  "overall_label": "BUY",
  "overall_strength": 68,
  "overall_reasons": [/* combined reasons */],
  "decision_summary": "Layak BUY hari ini karena momentum teknikal...",
  "key_drivers": ["RSI 14 di 62.5: zona normal", "..."],
  "risk_notes": ["Volume di bawah 100.000: sinyal diturunkan", "..."],
  "trade_plan": {
    "stop_loss": 9850,
    "take_profit": 11050,
    "risk_reward_ratio": 2.0,
    "horizon_days": 7
  },
  "daily_check": {
    "action": "HOLD",
    "current_price": 10250,
    "distance_to_sl_pct": -3.9,
    "distance_to_tp_pct": 7.8
  },
  "news_sentiment": {
    "sentiment": "POSITIVE",
    "score": 0.42,
    "positive_count": 4,
    "negative_count": 1,
    "neutral_count": 2
  },
  "volatility_pct": 2.3,
  "updated_at": "2026-06-11T08:30:00Z"
}
```

**Response 404:** `{"detail": "Saham XYZ tidak ditemukan"}` atau `{"detail": "Data historis untuk XYZ tidak tersedia"}`

**Curl:**
```bash
curl http://localhost:8774/api/stocks/BBCA
curl http://localhost:8774/api/stocks/ANTM
```

---

#### `GET /api/stocks/{symbol}/history`

OHLCV chart data dengan progressive fallback.

**Path params:**
- `symbol` (str)

**Query params:**
- `period` (str, default `6mo`) — salah satu dari: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `max`, atau alias `1m`/`3m` (→ `1mo`/`3mo`)

**Progressive fallback chain:** `requested` → `1d` → `5d` → `1mo` → `3mo` → `6mo`

**Response 200:**
```json
{
  "symbol": "BBCA",
  "period": "6mo",
  "dates": ["2026-01-01", "2026-01-02", "..."],
  "open":  [9800, 9850, "..."],
  "high":  [9900, 9950, "..."],
  "low":   [9700, 9750, "..."],
  "close": [9850, 9900, "..."],
  "volume": [10000000, 11000000, "..."],
  "updated_at": "2026-06-11T08:30:00Z"
}
```

**Curl:**
```bash
curl 'http://localhost:8774/api/stocks/BBCA/history?period=3mo'
curl 'http://localhost:8774/api/stocks/BBCA/history?period=1y'
```

---

#### `GET /api/stocks/{symbol}/signals`

Lightweight — hanya technical + fundamental summary (no news, no chart).

**Response 200:**
```json
{
  "symbol": "BBCA",
  "overall_signal": "BUY",
  "overall_strength": 68,
  "technical": {"signal": "BUY", "strength": 72},
  "fundamental": {"signal": "HOLD", "strength": 55},
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

#### `GET /api/stocks/{symbol}/news`

News + sentiment untuk saham tertentu.

**Query params:**
- `limit` (int, default 8, max 20)

**Response 200:**
```json
{
  "symbol": "BBCA",
  "items": [
    {
      "title": "BBCA catat laba bersih...",
      "summary": "...",
      "link": "https://...",
      "published": "2026-06-10T12:00:00Z",
      "source": "CNBC Indonesia",
      "sentiment": "POSITIVE",
      "sentiment_score": 6,
      "sentiment_confidence": 0.78,
      "sentiment_method": "vader+id_lexicon"
    }
  ],
  "sentiment": "POSITIVE",
  "sentiment_score": 4.2,
  "positive_count": 5,
  "negative_count": 1,
  "neutral_count": 2,
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

#### `GET /api/stocks/{symbol}/recommendation-history`

Riwayat rekomendasi + hasil evaluasi 7-hari.

**Query params:**
- `limit` (int, default 20)

**Response 200:**
```json
{
  "symbol": "BBCA",
  "history": [
    {
      "symbol": "BBCA",
      "recommendation": "BUY",
      "strength": 72,
      "price": 9850,
      "future_price": 10250,
      "return_pct": 4.06,
      "outcome": "up",
      "is_correct": 1,
      "created_at": "2026-06-04T08:30:00Z",
      "evaluated_at": "2026-06-11T08:30:00Z"
    }
  ],
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

### Market Data

#### `GET /api/market-summary`

Data IHSG (^JKSE), cached 15 detik.

**Response 200:**
```json
{
  "name": "IHSG — Indeks Harga Saham Gabungan",
  "symbol": "^JKSE",
  "price": 7125.45,
  "change": 25.30,
  "change_percent": 0.36,
  "high_52w": 9174.47,
  "low_52w": 4500.0,
  "volume": 12345678900,
  "updated_at": "2026-06-11T08:30:00Z"
}
```

Field `stale: true` ditambahkan saat data tidak valid dan menggunakan fallback.

---

#### `GET /api/live/summary`

Lightweight live data — prices + signals untuk semua saham, sorted by strength.

**Response 200:**
```json
{
  "stocks": [
    {
      "symbol": "BBCA",
      "price": 10250,
      "change_percent": 0.5,
      "overall_signal": "BUY",
      "overall_strength": 68
    }
  ],
  "market": {
    "ihsg_price": 7125.45,
    "ihsg_change": 0.36
  },
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

### News & Sentiment

#### `GET /api/news`

News + NLP sentiment. Tanpa `?symbol` → top 5 liquid stocks. Dengan `?symbol` → khusus simbol.

**Query params:**
- `symbol` (str, opsional)
- `limit` (int, default 8, max 20)

**Response 200 (no symbol):**
```json
{
  "items": [
    {
      "symbol": "BBCA",
      "items": [ /* news items */ ],
      "sentiment": "POSITIVE",
      "sentiment_score": 3.5
    }
  ],
  "updated_at": "2026-06-11T08:30:00Z"
}
```

**Response 200 (with symbol):**
```json
{
  "symbol": "BBCA",
  "items": [ /* news items */ ],
  "sentiment": "POSITIVE",
  "sentiment_score": 4.2,
  "positive_count": 5,
  "negative_count": 1,
  "neutral_count": 2,
  "updated_at": "2026-06-11T08:30:00Z"
}
```

**Catatan:** News di-scrape dari Google News RSS via `feedparser`. Sentiment dianalisa dengan VADER + Indonesian lexicon (`services/news_service.py`).

---

### Auth & Users

#### `POST /api/auth/login`

Sudah didokumentasikan di section [Authentication](#authentication).

---

#### `POST /api/auth/refresh`

Refresh access token.

**Request body:**
```json
{
  "refresh_token": "eyJ..."
}
```

---

#### `GET /api/auth/me`

Current user info. **Auth required.**

---

#### `GET /api/admin/users`

List semua user. **Auth + superadmin required.**

**Response 200:**
```json
{
  "users": [
    {"id": 1, "username": "admin", "role": "superadmin", "created_at": "2026-01-01T00:00:00Z"}
  ]
}
```

---

#### `POST /api/admin/users`

Buat user baru. **Auth + superadmin required.**

**Request body:**
```json
{
  "username": "johndoe",
  "password": "secret123",
  "role": "user"
}
```

**Response 200:** Updated user list.
**Response 400:** `{"detail": "Username dan password wajib"}` atau duplicate.

---

### Portfolio

#### `GET /api/portfolio`

Ringkasan portofolio user. **Auth required.**

**Response 200:**
```json
{
  "positions": [
    {
      "id": 1,
      "symbol": "BBCA",
      "qty": 100,
      "avg_price": 10000,
      "current_price": 10250,
      "market_value": 1025000,
      "cost": 1000000,
      "pnl": 25000,
      "pnl_pct": 2.5,
      "target_price": 11000,
      "stop_loss": 9700,
      "notes": "Hold untuk dividen"
    }
  ],
  "summary": {
    "total_cost": 5000000,
    "total_value": 5200000,
    "total_pnl": 200000,
    "total_pnl_pct": 4.0,
    "winner_count": 3,
    "loser_count": 1,
    "win_rate": 75.0,
    "lose_rate": 25.0
  },
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

#### `POST /api/portfolio`

Add atau update posisi. **Auth required.**

**Request body:**
```json
{
  "symbol": "BBCA",
  "qty": 100,
  "avg_price": 10000,
  "target_price": 11000,
  "stop_loss": 9700,
  "notes": "Hold untuk dividen"
}
```

Field `target_price`, `stop_loss`, `notes` opsional. Field `symbol` akan di-uppercase dan suffix `.JK` dihilangkan.

---

#### `DELETE /api/portfolio/{symbol}`

Hapus posisi. **Auth required.**

---

### Learning Engine

#### `GET /api/learning/summary`

Performa learning: akurasi per signal type, recent evaluations, pending count.

**Response 200:**
```json
{
  "total_records": 5000,
  "pending_evaluation": 200,
  "evaluated": 4800,
  "accuracy": 64.5,
  "by_signal": [
    {
      "recommendation": "BUY",
      "count": 2000,
      "correct": 1350,
      "accuracy": 67.5,
      "avg_return": 3.2
    },
    {
      "recommendation": "SELL",
      "count": 1800,
      "correct": 1100,
      "accuracy": 61.1,
      "avg_return": -2.8
    }
  ],
  "recent": [ /* latest 20 recommendation history */ ],
  "rule": "BUY benar jika return 7 hari > 0%; SELL benar jika return < 0%; HOLD benar jika return di antara -5% sampai +5%.",
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

#### `GET /api/learning/evaluate`

Trigger batch evaluasi untuk rekomendasi yang > 7 hari.

**Query params:**
- `limit` (int, default 50)

**Response 200:**
```json
{
  "processed": 50,
  "summary": {
    "total_evaluated": 4800,
    "correct": 3096,
    "wrong": 1704,
    "accuracy": 64.5,
    "avg_return": 1.2
  },
  "results": [
    {
      "id": 1234,
      "symbol": "BBCA",
      "recommendation": "BUY",
      "future_price": 10250,
      "return_pct": 4.06,
      "outcome": "up",
      "is_correct": 1
    }
  ],
  "updated_at": "2026-06-11T08:30:00Z"
}
```

**Aturan evaluasi (`outcome` & `is_correct`):**
- BUY + return_7d > 0% → `outcome=up`, `is_correct=1`
- SELL + return_7d < 0% → `outcome=down`, `is_correct=1`
- HOLD + |return_7d| ≤ 5% → `outcome=neutral`, `is_correct=1`
- Lainnya → `is_correct=0`

---

### Accuracy Dashboard

#### `GET /api/accuracy`

Full accuracy dashboard (win rate per signal, accuracy over time, confusion matrix, performance metrics, A/B comparison).

**Response 200:**
```json
{
  "win_rate_per_signal": [
    {"signal_type": "BUY", "wins": 1350, "total": 2000, "win_rate": 0.675}
  ],
  "accuracy_over_time": [
    {"month": "2026-01", "accuracy": 0.62, "total": 350},
    {"month": "2026-02", "accuracy": 0.65, "total": 410}
  ],
  "confusion_matrix": {
    "matrix": {
      "BUY": {"up": 1350, "down": 450, "neutral": 200},
      "SELL": {"up": 600, "down": 1100, "neutral": 100}
    },
    "labels": ["BUY", "SELL"]
  },
  "performance": {
    "avg_return": 1.2,
    "max_drawdown": -8.5,
    "sharpe_ratio": 0.85,
    "total_signals_evaluated": 4800
  },
  "version_comparison": {
    "version_a": {"accuracy": 0.62, "count": 2400, "avg_return": 0.8},
    "version_b": {"accuracy": 0.67, "count": 2400, "avg_return": 1.5},
    "winner": "B"
  },
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

#### `GET /api/accuracy/summary`

Compact accuracy summary untuk dashboard.

**Response 200:**
```json
{
  "overall_win_rate": 0.645,
  "total_evaluated": 4800,
  "avg_return": 1.2,
  "sharpe_ratio": 0.85,
  "accuracy_over_time": [ /* last 6 months */ ],
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

### Reports

#### `GET /api/report/daily`

Laporan harian: top 5 BUY, top 5 SELL, summary portofolio. **Auth required.**

**Response 200:**
```json
{
  "headline": "Laporan harian siap: lihat BUY kuat, SELL/hindari, dan posisi porto.",
  "buy_now": [ /* top 5 BUY stocks */ ],
  "sell_or_avoid": [ /* top 5 SELL stocks */ ],
  "portfolio": {
    "total_cost": 5000000,
    "total_value": 5200000,
    "total_pnl": 200000,
    "total_pnl_pct": 4.0
  },
  "rule": "BUY punya target 7 hari + stop loss. Cek tiap hari. Sinyal dievaluasi 7 hari untuk learning.",
  "updated_at": "2026-06-11T08:30:00Z"
}
```

---

### System

#### `GET /health`

Health check. **No auth, no rate limit.**

**Response 200:**
```json
{
  "status": "ok",
  "service": "saham-app-api",
  "database": "postgres"
}
```

`database` = `"postgres"` atau `"sqlite"`.

---

#### `GET /docs`

Swagger UI interaktif (auto-generated by FastAPI).

---

#### `GET /redoc`

ReDoc interaktif.

---

#### `GET /openapi.json`

OpenAPI 3.0 schema (JSON).

---

## Signal Logic

### Sinyal — Strength → Label

| Strength | Signal |
|----------|--------|
| ≥ 65 | **BUY** |
| 36 – 64 | **NEUTRAL** (label di UI: "TAHAN") |
| ≤ 35 | **SELL** |

### Weighted Ensemble (5 komponen)

Default weights (diambil dari `signal_weights` table, fallback ke hardcoded):

| Komponen | Default Weight | Rentang |
|----------|---------------|---------|
| TA (Teknikal) | 0.30 | 0.05 – 0.60 |
| Fundamental | 0.30 | 0.05 – 0.60 |
| Sentimen | 0.20 | 0.05 – 0.60 |
| Volume | 0.10 | 0.05 – 0.60 |
| Regime | 0.10 | 0.05 – 0.60 |

**Dynamic adjustment by market regime:**
- `trending_up` → TA +10%, Sent −5%
- `volatile` → Regime +10%
- `ranging` → Fundamental +10%

**Sector correlation adjustment:**
- Sector avg change < −3% AND signal BUY → strength −15
- Sector avg change > +3% AND signal SELL → strength −15

**Outlier detection (3-day smoothing):**
- Current strength > 95 with rolling avg < 80 → capped to avg+10
- |current − avg3| > 15 → blend 0.6×current + 0.4×avg3, cap ±20%

### Confidence Level

```
confidence = 0.6 × agreement_pct + 0.4 × strength_extremity
```

Di mana:
- `agreement_pct` = % komponen yang setuju dengan majority signal (max 100)
- `strength_extremity` = |avg_strength − 50| / 50 × 100

### Trade Plan (SL/TP)

ATR-based, regime-dependent:

| Regime | Stop Loss | Take Profit | Min RRR |
|--------|-----------|-------------|---------|
| trending_up | entry − 1.5×ATR | entry + 3.0×ATR | 2.0 |
| trending_down | entry + 1.5×ATR | entry − 3.0×ATR | 2.0 |
| ranging | entry − 1.0×ATR | entry + 2.0×ATR | 2.0 |
| volatile | entry − 2.0×ATR | entry + 4.0×ATR | 2.0 |

Risk:Reward Ratio (RRR) dijamin ≥ 1:2 — TP akan diperlebar jika belum memenuhi.

### Volume Threshold

- Minimum volume harian: **10,000 lembar** (config `VOLUME_THRESHOLD` di `services/db.py`).
  Tier likuiditas: 10K (minimum, +2 bias), 100K (+4), 1M (+6), 5M (+8). Di bawah 10K → strength -8.
- Jika di bawah threshold 10K: strength dikurangi 10, sinyal diturunkan
- Volume ratio:
  - < 0.7× avg → strength × 0.85
  - > 1.5× avg → strength × 1.10

### Liquidity Filter (scanner)

Saham masuk top list jika:
- Harga ≥ 50 IDR
- Avg volume ≥ 100,000
- Avg value ≥ 1 miliar IDR
- Punya ≥ 20 hari data historis
- Failed-fetch ratio ≤ 40%

---

## Data Models (Schemas)

Lokasi: `backend/schemas/`

### `LoginRequest`
```python
class LoginRequest(BaseModel):
    username: str
    password: str
```

### `LoginResponse`
```python
class LoginResponse(BaseModel):
    token: str
    refresh_token: str
    user: Dict[str, Any]
```

### `RefreshRequest`
```python
class RefreshRequest(BaseModel):
    refresh_token: str
```

### `UserCreate`
```python
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = 'user'  # 'user' atau 'superadmin'
```

### `PositionCreate`
```python
class PositionCreate(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None
```

### `PositionResponse`
```python
class PositionResponse(BaseModel):
    id: int
    symbol: str
    qty: float
    avg_price: float
    current_price: float
    market_value: float
    cost: float
    pnl: float
    pnl_pct: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None
```

---

## Concurrency & Timeouts

- yfinance call dibungkus `_fetch_stock_data_with_retry()` dengan retry + timeout
- Default timeout: 6s untuk info, 7s untuk history
- Parallelisme: `ThreadPoolExecutor(max_workers=5)` + `asyncio.gather`
- Background worker refresh setiap 60s (configurable)
- News fetch timeout 5s (non-blocking di detail endpoint)

---

## Versioning

Saat ini **v1.0** (stable). Perubahan breaking akan diumumkan di `CHANGELOG.md` dengan prefix `BREAKING:`.

---

## CORS

Semua origin diizinkan (`*`) untuk mobile app. Header yang diizinkan: semua. Methods: semua. Credentials: yes.

Untuk production, sebaiknya restrict ke domain spesifik — edit `app.py` line 100.

---

## Logging

Backend log level default: `INFO`. Format: `%(asctime)s %(levelname)s %(name)s: %(message)s`.

Logger names: `saham-api` (root), `uvicorn`, `yfinance`.

---

## Support

Bug? Feature request? Buka issue di GitHub atau lihat **[SECURITY.md](../SECURITY.md)** untuk responsible disclosure.
