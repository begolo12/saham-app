# 📡 API Reference

> Backend: FastAPI · Base URL: `https://api.saham-app.com` (production) / `http://localhost:8774` (dev)
> Swagger UI: `/docs` · ReDoc: `/redoc`

---

## 🔐 Authentication

Semua endpoint (kecuali `/api/auth/login` dan `/api/auth/refresh`) butuh Bearer token.

```bash
# Login
curl -X POST http://localhost:8774/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Response 200
{
  "access_token": "1.1700000000.abc...",
  "refresh_token": "def456...",
  "token": "1.1700000000.abc...",
  "user": {"id": 1, "username": "admin", "role": "superadmin"}
}

# Pakai token
curl http://localhost:8774/api/stocks \
  -H "Authorization: Bearer 1.1700000000.abc..."

# Refresh saat access token expired (15 min)
curl -X POST http://localhost:8774/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"def456..."}'
```

**Rate limit**: 5 percobaan login/menit per IP. Lebih dari itu → 429.

---

## 📊 Stocks

### `GET /api/stocks`
Ambil daftar top stocks (default 30).

**Query**: `?limit=30&sort=signal` (sort: `signal|change|volume|name`)

**Response 200**:
```json
{
  "stocks": [
    {
      "symbol": "BBCA.JK",
      "name": "Bank Central Asia",
      "sector": "Perbankan",
      "price": 10250,
      "change": 150,
      "change_percent": 1.49,
      "volume": 12345678,
      "signal": "BELI",
      "signal_strength": 78,
      "confidence": 82,
      "stop_loss": 9880,
      "take_profit": 10850,
      "risk_reward_ratio": 2.1
    }
  ],
  "total": 30,
  "updated_at": "2026-06-11T15:30:00Z"
}
```

### `GET /api/stocks/{symbol}`
Detail satu saham.

**Path**: `symbol` — ticker dengan atau tanpa `.JK`

**Response 200**: Sama seperti stock di list + fields tambahan:
```json
{
  "symbol": "BBCA.JK",
  "name": "Bank Central Asia",
  "sector": "Perbankan",
  "price": 10250,
  "change": 150,
  "change_percent": 1.49,
  "volume": 12345678,
  "high_52w": 11500,
  "low_52w": 8800,
  "market_cap": 1250000000000,
  "pe_ratio": 18.5,
  "pbv_ratio": 3.2,
  "dividend_yield": 2.1,
  "signal": "BELI",
  "signal_strength": 78,
  "confidence": 82,
  "stop_loss": 9880,
  "take_profit": 10850,
  "risk_reward_ratio": 2.1,
  "reasons": ["RSI oversold", "MACD golden cross", "Volume spike +45%"],
  "weights_used": {"ta": 0.35, "fundamental": 0.25, "sentiment": 0.20, "volume": 0.10, "regime": 0.10},
  "market_regime": "trending_up",
  "vwap": 10180,
  "atr": 250,
  "outlier_flag": false,
  "signal_version": "v2"
}
```

### `GET /api/stocks/{symbol}/history`
Data historis untuk chart.

**Query**: `?period=1y` (period: `1d|5d|1mo|3mo|6mo|1y|2y|5y|max`)

**Response 200**:
```json
{
  "symbol": "BBCA.JK",
  "period": "1y",
  "candles": [
    {"date": "2025-06-11", "open": 9800, "high": 9950, "low": 9750, "close": 9900, "volume": 8765432}
  ]
}
```

### `POST /api/stocks/batch`
Ambil multiple stocks sekaligus.

**Body**:
```json
{"symbols": ["BBCA.JK", "BBRI.JK", "BMRI.JK"]}
```

**Response 200**:
```json
{"stocks": [...], "errors": {"INVALID.JK": "not found"}}
```

### `GET /api/stocks/search?q=bbca`
Cari saham.

**Response 200**:
```json
{"results": [{"symbol": "BBCA.JK", "name": "Bank Central Asia", "sector": "Perbankan"}]}
```

---

## 🏪 Market

### `GET /api/market/summary`
IHSG + indeks utama.

**Response 200**:
```json
{
  "name": "IHSG — Indeks Harga Saham Gabungan",
  "symbol": "^JKSE",
  "price": 7150.32,
  "change": 45.21,
  "change_percent": 0.64,
  "high_52w": 7800.5,
  "low_52w": 6500.0,
  "volume": 12345678900,
  "regime": "trending_up",
  "regime_confidence": 0.78,
  "updated_at": "2026-06-11T15:30:00Z"
}
```

### `GET /api/market/regime`
Detail market regime detection.

**Response 200**:
```json
{
  "regime": "trending_up",
  "confidence": 0.78,
  "ihsg_trend": 0.045,
  "volatility": 0.012,
  "bi_rate": 6.0,
  "usd_idr": 16850,
  "inflation": 2.04,
  "macro_notes": "USD/IDR stabil, BI rate netral"
}
```

---

## 💼 Portfolio

### `GET /api/portfolio`
Positions + summary.

**Auth required** ✅

**Response 200**:
```json
{
  "positions": [
    {
      "id": 1,
      "symbol": "BBCA.JK",
      "shares": 100,
      "buy_price": 9800,
      "current_price": 10250,
      "pl": 45000,
      "pl_percent": 4.59,
      "buy_date": "2026-01-15"
    }
  ],
  "summary": {
    "total_invested": 980000,
    "current_value": 1025000,
    "total_pl": 45000,
    "total_pl_percent": 4.59,
    "best_position": "BBCA.JK",
    "worst_position": "TLKM.JK"
  }
}
```

### `POST /api/portfolio/positions`
Tambah position baru.

**Auth required** ✅

**Body**:
```json
{"symbol": "BBCA.JK", "shares": 100, "buy_price": 9800, "buy_date": "2026-01-15"}
```

**Response 201**:
```json
{"id": 1, "symbol": "BBCA.JK", "shares": 100, ...}
```

### `DELETE /api/portfolio/positions/{id}`
Hapus position.

**Auth required** ✅

**Response 204**: No content

---

## 📰 News

### `GET /api/news/{symbol}?limit=8`
Berita + sentimen untuk simbol.

**Response 200**:
```json
{
  "symbol": "BBCA.JK",
  "items": [
    {
      "title": "BBCA catat laba bersih naik 15% di Q1 2026",
      "link": "https://...",
      "source": "Kontan",
      "published": "2026-06-11T10:00:00Z",
      "summary": "Bank Central Asia (BBCA) mengumumkan...",
      "sentiment": "POSITIVE",
      "sentiment_score": 0.65,
      "sentiment_method": "vader+lexicon"
    }
  ],
  "aggregate": {"score": 0.42, "label": "POSITIVE", "method": "vader+lexicon"}
}
```

---

## 📚 Learning

### `GET /api/learning/evaluations`
Riwayat akurasi rekomendasi.

**Auth required** ✅

**Response 200**:
```json
{
  "evaluations": [
    {
      "id": 1,
      "date": "2026-06-10",
      "symbol": "BBCA.JK",
      "signal": "BELI",
      "entry_price": 9800,
      "current_price": 10250,
      "pl_percent": 4.59,
      "outcome": "WIN",
      "days_held": 1
    }
  ],
  "summary": {"total": 30, "wins": 22, "losses": 8, "win_rate": 73.3}
}
```

### `POST /api/learning/evaluate`
Trigger evaluasi manual.

**Auth required** ✅ (superadmin)

**Response 200**:
```json
{"evaluated": 30, "wins": 22, "losses": 8, "win_rate": 73.3}
```

---

## 📊 Signal Accuracy

### `GET /api/accuracy`
Dashboard akurasi lengkap.

**Auth required** ✅

**Response 200**:
```json
{
  "by_signal": {
    "BELI": {"correct": 142, "total": 200, "win_rate": 71.0},
    "JUAL": {"correct": 45, "total": 70, "win_rate": 64.3},
    "TAHAN": {"correct": 88, "total": 130, "win_rate": 67.7}
  },
  "risk_return": {
    "sharpe_ratio": 1.42,
    "avg_return": 2.3,
    "max_drawdown": -8.5
  },
  "monthly": [
    {"month": "2025-07", "win_rate": 68.5, "count": 30}
  ],
  "confusion": {
    "true_positive": 142, "false_positive": 58,
    "false_negative": 25, "true_negative": 88
  },
  "ab_test": {
    "v1": {"win_rate": 68.0, "count": 200},
    "v2": {"win_rate": 72.5, "count": 200, "winner": true}
  },
  "total_signals": 400
}
```

### `GET /api/accuracy/summary`
Versi ringkas.

**Response 200**:
```json
{
  "overall_win_rate": 69.2,
  "total_signals": 400,
  "last_updated": "2026-06-11T15:30:00Z"
}
```

---

## 👤 Admin

### `GET /api/admin/users`
List users.

**Auth required** ✅ (superadmin)

**Response 200**:
```json
{"users": [{"id": 1, "username": "admin", "role": "superadmin", "created_at": "2025-12-01"}]}
```

### `POST /api/admin/users`
Buat user baru.

**Auth required** ✅ (superadmin)

**Body**:
```json
{"username": "trader1", "password": "secret123", "role": "user"}
```

---

## 📈 Daily Report

### `GET /api/report/daily`
Laporan harian (sinyal terbaik, loss/terbesar, dll).

**Auth required** ✅

**Response 200**:
```json
{
  "date": "2026-06-11",
  "top_picks": [{"symbol": "BBCA.JK", "signal": "BELI", "strength": 92}],
  "worst_picks": [{"symbol": "TLKM.JK", "signal": "BELI", "loss": -5.2}],
  "portfolio_summary": {...}
}
```

---

## 🩺 Health

### `GET /api/health`
Status server.

**Response 200**:
```json
{
  "status": "ok",
  "version": "2.0.0",
  "db": "ok",
  "cache": "ok",
  "worker": "running",
  "uptime": 86400
}
```

### `GET /`
Health check (HTML).

---

## 🚨 Error Codes

| Code | Arti |
|------|------|
| 200 | Sukses |
| 201 | Created |
| 204 | No content |
| 400 | Bad request (body tidak valid) |
| 401 | Belum login / token invalid |
| 403 | Forbidden (role tidak cukup) |
| 404 | Not found |
| 422 | Validation error (Pydantic) |
| 429 | Rate limit exceeded |
| 500 | Server error |
| 502 | Upstream error (yfinance dll) |

**Error response format**:
```json
{"detail": "Error message"}
```

---

## 🔒 Security Headers

Response selalu include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HTTPS only)

---

## 📦 Caching

| Endpoint | TTL |
|----------|-----|
| `/api/stocks` | 15s |
| `/api/stocks/{symbol}` | 15s |
| `/api/market/summary` | 60s |
| `/api/market/regime` | 300s |
| `/api/news/{symbol}` | 1800s |
| `/api/portfolio` | 60s |
| `/api/accuracy` | 60s |
| `/api/auth/*` | No cache |

Cache di-serve dari Redis (Upstash) + fallback fakeredis. Stale data ditandai dengan `stale: true` jika >1 jam.

---

## 🧪 Testing

```bash
# Backend
cd backend
pytest tests/ -v

# Frontend
cd frontend
npm test
```

---

_Last updated: 2026-06-11_
