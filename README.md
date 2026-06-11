# SahamApp — Indonesian Stock Analysis Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a86b?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61dafb?logo=react)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8-646cff?logo=vite)](https://vite.dev)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)
[![PWA](https://img.shields.io/badge/PWA-installable-blueviolet)](https://web.dev/progressive-web-apps/)
[![iOS 18 Design](https://img.shields.io/badge/UI-iOS%2018-007aff)](#)

> **SahamApp** — Platform analisis saham Indonesia (IDX) real-time dengan scanner 140+ emiten, sinyal teknikal + fundamental, sentimen berita, portofolio virtual, dan mesin belajar yang meningkat seiring waktu. Antarmuka berbahasa Indonesia dengan desain iOS 18.

**Live demo:** [saham-app.vercel.app](https://saham-app.vercel.app)

---

## Daftar Isi

- [Gambaran Singkat](#gambaran-singkat)
- [Fitur (Features)](#fitur-features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Available Scripts](#available-scripts)
- [Testing](#testing)
- [API Endpoints](#api-endpoints)
- [Arsitektur](#arsitektur)
- [Deployment](#deployment)
- [Dokumentasi Lain](#dokumentasi-lain)
- [Berkontribusi](#berkontribusi)
- [Lisensi](#lisensi)

---

## Gambaran Singkat

SahamApp adalah aplikasi web (PWA) dan desktop (Electron) untuk investor ritel Indonesia. Backend FastAPI melakukan scanning 140+ saham IDX, menggabungkan:

- **Teknikal** — RSI, MACD, SMA 20/50, Bollinger Bands, Stochastic, VWAP, ATR
- **Fundamental** — PER, PBV, dividend yield, market cap, EPS
- **Sentimen Berita** — Google News RSS + NLP Indonesia
- **Volume confirmation** — filter likuiditas & konfirmasi
- **Market regime detection** — trending/ranging/volatile

Semua digabung lewat **weighted ensemble engine** yang bobotnya bisa disesuaikan per simbol via tabel `signal_weights` (machine-learned from past 7-day outcomes).

Hasilnya: sinyal **BELI / JUAL / TAHAN** plus **SL/TP otomatis** berbasis ATR.

---

## Fitur (Features)

| Fitur | Deskripsi |
|-------|-----------|
| **Scanner 140+ Saham IDX** | Scan otomatis seluruh sektor IDX (perbankan, energi, konsumer, teknologi, dll) — refresh paralel via ThreadPoolExecutor |
| **Weighted Ensemble Signals** | 5 komponen (TA, Fund, Sent, Vol, Regime) dengan bobot dinamis per market regime |
| **Sinyal Teknikal** | RSI 14, MACD golden/death cross, SMA 20/50, Bollinger Bands, Stochastic, VWAP, ATR — penjelasan dalam Bahasa Indonesia |
| **Sinyal Fundamental** | PER, PBV, dividend yield, market cap, EPS — klasifikasi valuasi murah/mahal/premium |
| **Sentimen Berita** | Google News RSS → NLP Indonesia (VADER + Indonesian lexicon) |
| **Portofolio Virtual** | Multi-user, P/L real-time, win rate tracker, target & stop loss |
| **Self-Learning Engine** | Rekomendasi dievaluasi 7-hari kemudian, akurasi dicatat, bobot disesuaikan |
| **Market Regime Detection** | trending_up/down, ranging, volatile via SMA50 vs SMA200 + ATR |
| **Sector Correlation** | Sinyal dikurangi jika berlawanan dengan tren sektor |
| **Outlier Detection** | Smoothing 3-hari untuk cegah lonjakan strength palsu |
| **Multi-Timeframe** | Analisis di 1d/1wk/1mo untuk konfirmasi tren |
| **Macro Data** | IHSG, BI rate, USD/IDR, inflasi — konteks pasar |
| **A/B Testing** | Bandingkan dua versi model sinyal, ukur mana yang lebih akurat |
| **Backtest Engine** | Replay data historis, hitung Sharpe ratio, max drawdown |
| **Laporan Harian** | Top 5 BUY, top 5 SELL, ringkasan portofolio |
| **PWA** | Installable di mobile/desktop, service worker untuk offline |
| **Desktop (Electron)** | Native app bundle backend + frontend |
| **iOS 18 Design** | Liquid glass, spring animations, haptic feedback |
| **Bottom Navigation** | Navigasi mobile-first, swipe gesture, pull-to-refresh |
| **Watchlist** | Simpan saham favorit di localStorage |
| **Dark/Light Mode** | Theme toggle, persist via localStorage |
| **Multi-user Auth** | HMAC-signed token, superadmin role, refresh token |
| **Rate Limiting** | 200 req/menit per IP, sliding window |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, Permissions-Policy |
| **Caching** | Redis (Upstash) di production, fakeredis di dev, in-memory fallback |
| **Background Worker** | Auto-refresh data saham di background setiap 60s |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com) 0.115+ |
| **Backend Server** | [uvicorn](https://www.uvicorn.org) + [Mangum](https://mangum.io) (serverless) |
| **Frontend** | [React 19](https://react.dev) + [React Router 7](https://reactrouter.com) |
| **State Management** | [Zustand](https://github.com/pmndrs/zustand) |
| **Build Tool** | [Vite 8](https://vite.dev) |
| **Charts** | [Recharts](https://recharts.org) 3.x |
| **Virtualization** | [TanStack Virtual](https://tanstack.com/virtual) |
| **Market Data** | [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance) |
| **News** | Google News RSS + NLTK VADER + Indonesian lexicon |
| **Database** | SQLite (dev) / PostgreSQL via [Neon](https://neon.tech) (prod) |
| **DB Driver** | [psycopg](https://www.psycopg.org) 3 |
| **Cache** | [Redis](https://redis.io) / [Upstash](https://upstash.com) / fakeredis (fallback) |
| **Auth** | HMAC-SHA256 signed tokens (no external JWT lib) |
| **Desktop** | [Electron](https://www.electronjs.org) 39 |
| **PWA** | Service worker + manifest.json |
| **Deployment** | [Vercel](https://vercel.com) (serverless Python + static SPA) |
| **Testing** | [Vitest](https://vitest.dev) + React Testing Library + pytest |
| **Linting** | ESLint 10 + react-hooks plugin |

---

## Quick Start

### Prerequisites

- **Python** 3.11+ (tested on 3.11.15)
- **Node.js** 20+ dan **npm**
- **Git**

### 1. Clone & Install

```bash
git clone <repo-url> saham-app
cd saham-app

# Python deps
pip install -r requirements.txt
pip install -r requirements-dev.txt   # opsional, untuk testing
```

### 2. Backend (Terminal 1)

```bash
cd backend
python run.py
# → API listening on http://localhost:8774
# → Swagger docs:  http://localhost:8774/docs
```

### 3. Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
# → UI listening on http://localhost:5180
# → Vite proxies /api/* → http://localhost:8774
```

Buka **http://localhost:5180** di browser. Login default: `admin` / `admin123`.

### 4. (Opsional) Environment Variables

Buat `.env` di root atau set di shell:

```bash
SAHAM_ADMIN_USERNAME=admin
SAHAM_ADMIN_PASSWORD=admin123
SAHAM_AUTH_SECRET=your-secret-key-min-32-chars
POSTGRES_URL=postgresql://user:pass@host/db
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379
```

Tanpa `POSTGRES_URL`, app otomatis pakai SQLite di `backend/signals.db`.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SAHAM_ADMIN_USERNAME` | No | `admin` | Default admin user (auto-created on first run) |
| `SAHAM_ADMIN_PASSWORD` | No | `admin123` | Default admin password |
| `SAHAM_AUTH_SECRET` | No | `SAHAM_ADMIN_PASSWORD` | HMAC secret untuk token signing. **WAJIB** diset di production |
| `POSTGRES_URL` | No | — | Full PostgreSQL connection string (Neon/Supabase/Railway) |
| `POSTGRES_URL_NON_POOLING` | No | — | Direct (non-pooler) connection — dicek duluan |
| `DATABASE_URL` | No | — | Generic DB URL fallback |
| `DATABASE_URL_UNPOOLED` | No | — | Unpooled DB URL fallback |
| `REDIS_URL` | No | — | Redis/Upstash connection string (format `rediss://...`) |
| `SENTRY_DSN` | No | — | (Opsional) Error tracking |

Priority order: `POSTGRES_URL_NON_POOLING` > `DATABASE_URL_UNPOOLED` > `DATABASE_URL` > `POSTGRES_URL`.

---

## Available Scripts

### Backend (root + backend/)

```bash
python backend/run.py          # Dev server with hot reload (port 8774)
uvicorn main:app --reload      # Alternative
pytest                         # Run all tests
pytest tests/test_analysis.py  # Specific file
pytest -k rsi                  # Pattern match
```

### Frontend (frontend/)

```bash
npm run dev          # Dev server with HMR (port 5180)
npm run build        # Production build → dist/
npm run preview      # Preview production build
npm run lint         # ESLint
npm test             # Vitest run once
npm run test:watch   # Vitest watch mode
npm run electron     # Launch Electron dev (need backend running too)
npm run electron:build  # Build + launch Electron
```

---

## Testing

```bash
# Backend
pytest                          # All tests
pytest -v --tb=short            # Verbose
pytest backend/tests/           # Specific dir

# Frontend
cd frontend && npm test         # One-shot
cd frontend && npm run test:watch
```

Test coverage:
- Technical indicators (RSI, MACD, SMA, Bollinger, Stochastic, VWAP, ATR)
- Regime detection edge cases
- Outlier detection & smoothing
- Weighted ensemble
- Sector correlation
- Backtest metrics
- Frontend components (SignalBadge, StockCard, LearningPanel, AccuracyDashboard)
- Auth flow
- Rate limiting

---

## API Endpoints

Semua endpoint prefix `/api`. Lihat **[backend/docs/API.md](backend/docs/API.md)** untuk dokumentasi lengkap (request body, response schema, contoh curl).

### Quick Reference

| Kategori | Endpoint | Method | Auth |
|----------|----------|--------|------|
| Saham | `/api/stocks` | GET | No |
| Saham | `/api/stocks/search?q=` | GET | No |
| Saham | `/api/stocks/batch` | GET | No |
| Saham | `/api/stocks/{symbol}` | GET | No |
| Saham | `/api/stocks/{symbol}/history` | GET | No |
| Saham | `/api/stocks/{symbol}/signals` | GET | No |
| Saham | `/api/stocks/{symbol}/news` | GET | No |
| Pasar | `/api/market-summary` | GET | No |
| Pasar | `/api/live/summary` | GET | No |
| Berita | `/api/news` | GET | No |
| Auth | `/api/auth/login` | POST | No |
| Auth | `/api/auth/refresh` | POST | No |
| Auth | `/api/auth/me` | GET | Bearer |
| Admin | `/api/admin/users` | GET | Bearer + superadmin |
| Admin | `/api/admin/users` | POST | Bearer + superadmin |
| Portofolio | `/api/portfolio` | GET/POST/DELETE | Bearer |
| Belajar | `/api/learning/summary` | GET | No |
| Belajar | `/api/learning/evaluate` | GET | No |
| Akurasi | `/api/accuracy` | GET | No |
| Akurasi | `/api/accuracy/summary` | GET | No |
| Laporan | `/api/report/daily` | GET | Bearer |
| System | `/health` | GET | No |
| System | `/docs` | GET | No (Swagger UI) |
| System | `/redoc` | GET | No (ReDoc) |

---

## Arsitektur

```
┌────────────────────────────────────────────────┐
│            Browser / PWA / Electron            │
│   React 19 + Vite 8 + Recharts + Zustand      │
│   • iOS 18 design system                      │
│   • Bottom nav, pull-to-refresh, haptics      │
└──────────────────┬─────────────────────────────┘
                   │ HTTPS / JSON
                   ▼
┌────────────────────────────────────────────────┐
│         FastAPI Backend (Vercel Serverless)    │
│  • Rate limit 200/min  • CORS  • Security hdrs │
│  • Background worker (60s refresh)             │
└──┬──────────┬──────────┬──────────┬──────────┬─┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│yfin- │  │Google│  │  DB  │  │Redis │  │Worker│
│ance  │  │ News │  │  PG  │  │(Upst)│  │ loop │
│Yahoo │  │ RSS  │  │SQLite│  │      │  │      │
└──────┘  └──────┘  └──────┘  └──────┘  └──────┘

Services: cache • analysis • auth • stock • news
          abtest • backtest • macro • multitf
          migration • worker • fallback
```

Detail lengkap: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## Deployment

### Lokal (Python + Node)

```bash
# Terminal 1
cd backend && python run.py

# Terminal 2
cd frontend && npm install && npm run dev
```

### Docker

```bash
docker build -t saham-app .
docker run -d --name saham-app -p 8774:8774 \
  -e SAHAM_ADMIN_USERNAME=admin \
  -e SAHAM_ADMIN_PASSWORD=changeme \
  -e SAHAM_AUTH_SECRET=$(openssl rand -hex 32) \
  -e POSTGRES_URL=postgresql://... \
  -e REDIS_URL=rediss://... \
  saham-app
```

### Vercel (Recommended)

Project sudah pre-configured untuk Vercel:
- Build command: `cd frontend && npm install && npm run build`
- Output: `frontend/dist`
- API routes → `api/index.py` (Mangum wrapper)
- Static SPA → fallback via FastAPI

Setup lengkap: **[DEPLOY.md](DEPLOY.md)**.

---

## Dokumentasi Lain

- 📖 **[backend/docs/API.md](backend/docs/API.md)** — API reference lengkap
- 📘 **[USER_GUIDE.md](USER_GUIDE.md)** — Panduan pengguna (Bahasa Indonesia)
- 🔬 **[METHODOLOGY.md](METHODOLOGY.md)** — Metodologi sinyal (weighted ensemble, backtest, A/B)
- 📜 **[CHANGELOG.md](CHANGELOG.md)** — Version history
- 🚀 **[DEPLOY.md](DEPLOY.md)** — Deployment guide (Vercel + Neon + Upstash)
- 🏗️ **[ARCHITECTURE.md](ARCHITECTURE.md)** — System architecture
- 🔒 **[SECURITY.md](SECURITY.md)** — Security policy & reporting
- 🤝 **[CONTRIBUTING.md](CONTRIBUTING.md)** — Panduan kontribusi
- 📋 **[IMPROVEMENT_PLAN.md](IMPROVEMENT_PLAN.md)** — Roadmap enhancement (F0–F7)
- 📊 **[EXECUTION_PLAN.md](EXECUTION_PLAN.md)** — Execution plan & timeline

---

## Berkontribusi

Lihat **[CONTRIBUTING.md](CONTRIBUTING.md)** untuk:
- Code style (PEP 8 backend, ESLint frontend)
- Branch naming (`feature/...`, `fix/...`)
- Commit message format (`feat:`, `fix:`, `docs:`)
- Pull request process
- Test requirements

**Quick start untuk kontributor:**

```bash
git checkout -b feature/nama-fitur
# ... edit code ...
pytest                            # Backend tests pass
cd frontend && npm test           # Frontend tests pass
cd frontend && npm run lint       # No lint errors
git commit -m "feat: tambah indikator XYZ"
git push origin feature/nama-fitur
# Buka Pull Request
```

---

## Lisensi

MIT License — lihat [LICENSE](LICENSE).

Bebas digunakan untuk keperluan pribadi, komersial, dan edukasi. Mohon cantumkan atribusi.

---

## Disclaimer

> ⚠️ **SahamApp adalah alat bantu analisis, BUKAN saran investasi.** 
> 
> - Sinyal yang dihasilkan oleh model machine learning TIDAK menjamin profit.
> - Keputusan investasi sepenuhnya menjadi tanggung jawab pengguna.
> - Data harga bersumber dari Yahoo Finance (yfinance), dapat tertunda atau tidak akurat.
> - Performa di masa lalu TIDAK mencerminkan hasil di masa depan.
> - Selalu lakukan riset sendiri (DYOR — Do Your Own Research) dan konsultasikan dengan penasihat keuangan profesional.

---

<p align="center">Made with ❤️ for Indonesian stock investors & traders</p>
<p align="center">SahamApp © 2024-2026</p>
