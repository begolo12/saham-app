# 🚀 Saham ID — Improvement Plan (BMAD Method)

**Project:** Saham ID — Indonesian Stock Signal Analysis App
**Method:** BMAD (Breakthrough Method of Agile AI-Driven Development)
**Target:** 90% signal accuracy + silky smooth performance + premium UX
**Owner:** Irvan / Daniswara Group

---

## 📋 Phase 1: BRAINSTORM — Current State Analysis

### A. Kondisi Sekarang

| Aspek | Status | Catatan |
|-------|--------|---------|
| **Signal Engine** | Rule-based: teknikal (RSI, MACD, SMA, Bollinger, Stochastic) + fundamental + news sentiment | Manual TA, no ML, basic ensemble |
| **Frontend** | React 19 + Vite + Recharts | 877-line App.jsx monolith, no router |
| **Backend** | FastAPI + SQLite/Postgres + yfinance | 1761-line monolith |
| **Cache** | In-memory dict (hilang restart) | No Redis |
| **Data** | yfinance real-time + Google News RSS | Single source, no fallback |
| **Testing** | 0 tests | Empty tests/ dir |
| **UI** | iOS 18 minimal (good bones) | Inconsistent, some rough edges |
| **Auth** | JWT sederhana, 30d expiry | No refresh token |

### B. Root Cause Signal Kurang Akurat

1. **Data tunggal** — cuma yfinance + Google News. Tidak ada macro data, sector correlation, insider flow
2. **Rule-based statis** — threshold kaku (RSI >70 = overbought). Tidak adaptif sama market regime
3. **No backtesting rigor** — evaluasi cuma 7 hari window, ga cukup
4. **Sentimen mentah** — cuma word counting, no NLP
5. **No volume confirmation** — sinyal tanpa validasi volume sering false positive
6. **No weighting** — fundamental & teknikal bobot sama, padahal tiap situasi beda
7. **Ensemble sederhana** — linear combination, no stacking

---

## 🎯 Phase 2: PLAN — Prioritized Task Breakdown

### Tier S — Signal Accuracy (MUST HAVE — target 90%)

| # | Task | Effort | Impact | Detail |
|---|------|--------|--------|--------|
| S1 | **Backtesting Engine** | 2 hari | 🔥🔥🔥🔥🔥 | Evaluasi sinyal historis 1-3 tahun, hitung win rate, Sharpe, max drawdown |
| S2 | **Weighted Ensemble** | 1 hari | 🔥🔥🔥🔥🔥 | Bobot dinamis: teknikal 0.3, fundamental 0.3, sentimen 0.2, volume 0.1, macro 0.1 |
| S3 | **Market Regime Detection** | 2 hari | 🔥🔥🔥🔥 | Deteksi trending/ranging/volatile, ubah threshold otomatis |
| S4 | **Volume Profile Analysis** | 1 hari | 🔥🔥🔥🔥 | VWAP, volume confirmation filter (kalo signal BUY tapi volume turun → reduce strength) |
| S5 | **NLP Sentiment Upgrade** | 2 hari | 🔥🔥🔥🔥 | Ganti keyword counting → lightweight transformer (IndoBERT kecil) atau API |
| S6 | **Multi-Timeframe Analysis** | 1 hari | 🔥🔥🔥 | Cek sinyal di daily + weekly + 1h, sinyal valid cuma kalo semua timeframe searah |
| S7 | **Stop Loss / Take Profit Calculator** | 1 hari | 🔥🔥🔥 | ATR-based SL/TP, risk/reward ratio per sinyal |
| S8 | **Correlation & Sector Analysis** | 1 hari | 🔥🔥🔥 | Cek korelasi sinyal dengan sektor. Kalo sektor turun semua, BUY saham tertentu jadi lemah |
| S9 | **Macro Data Integration** | 2 hari | 🔥🔥🔥 | Inflasi, BI rate, USD/IDR, IHSG correlation — berdampak ke sektor tertentu |
| S10 | **Fallback Data Provider** | 1 hari | 🔥🔥🔥 | Cadangan kalo yfinance down: pake Yahoo Finance scrape atau API lain |
| S11 | **Signal Accuracy Dashboard** | 1 hari | 🔥🔥🔥 | Dashboard untuk user liat akurasi historical sinyal per tipe (BUY/SELL/NEUTRAL) |
| S12 | **Outlier Detection** | 1 hari | 🔥🔥 | Deteksi sinyal yang terlalu bagus/aneh — flag manual review |
| S13 | **A/B Test Framework Signal** | 1 hari | 🔥🔥 | Bisa compare signal engine v1 vs v2 real-time di production |

### Tier P — Performance (MUST HAVE — silky smooth)

| # | Task | Effort | Impact | Detail |
|---|------|--------|--------|--------|
| P1 | **Virtual Scroll** | 0.5 hari | 🔥🔥🔥🔥🔥 | @tanstack/react-virtual — 140 stocks render hanya yang visible |
| P2 | **API Cache Layer + Dedup + Abort** | 1 hari | 🔥🔥🔥🔥🔥 | In-memory TTL cache, request deduplication, stale request abort |
| P3 | **Code Splitting per Route** | 0.5 hari | 🔥🔥🔥🔥 | React.lazy tiap page, bundle split otomatis |
| P4 | **Redis Integration** | 1 hari | 🔥🔥🔥🔥 | Cache stock data (5 menit), IHSG (1 menit), news (30 menit) |
| P5 | **Background Data Refresh** | 2 hari | 🔥🔥🔥🔥 | Background worker refresh stock data, API tinggal read cache |
| P6 | **React.memo + useMemo Audit** | 0.5 hari | 🔥🔥🔥 | Audit semua komponen, tambah memo untuk pure components |
| P7 | **Service Worker Cache Strategy** | 0.5 hari | 🔥🔥🔥 | Cache-first untuk assets, network-first untuk data, offline fallback |
| P8 | **Image Optimization** | 0.5 hari | 🔥🔥 | Compress PNG/WebP, lazy load images below fold |
| P9 | **Debounced Search (300ms)** | 0.5 hari | 🔥🔥🔥 | Fuse.js fuzzy search + 300ms debounce |
| P10 | **Skeleton Loading Everywhere** | 1 hari | 🔥🔥🔥🔥 | Skeleton spesifik per page (ga cuma spinner) |

### Tier U — UI/UX (WANT — premium feel)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| U1 | Bottom Sheet (ganti modal) | 1 hari | 🔥🔥🔥 |
| U2 | Apple-style spring animations | 1 hari | 🔥🔥🔥🔥 |
| U3 | Skeleton screens per page | 1 hari | 🔥🔥🔥🔥 |
| U4 | Dark mode refinement | 1 hari | 🔥🔥🔥 |
| U5 | Light mode option | 1 hari | 🔥🔥 |
| U6 | PWA install prompt | 0.5 hari | 🔥🔥🔥 |
| U7 | Haptic feedback simulation | 0.5 hari | 🔥🔥 |
| U8 | Empty states better design | 0.5 hari | 🔥🔥 |
| U9 | Swipe actions on stock list | 1 hari | 🔥🔥🔥 |
| U10 | Micro-interactions (tap ripple) | 1 hari | 🔥🔥🔥 |

### Tier A — Architecture (SHOULD HAVE)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| A1 | React Router setup | 0.5 hari | 🔥🔥🔥🔥 |
| A2 | Zustand store (auth, stocks, portfolio) | 0.5 hari | 🔥🔥🔥🔥 |
| A3 | Backend routes pecah | 1 hari | 🔥🔥🔥 |
| A4 | Pydantic schemas separate | 0.5 hari | 🔥🔥🔥 |
| A5 | Refresh token auth | 1 hari | 🔥🔥🔥 |
| A6 | Error boundaries per page | 0.5 hari | 🔥🔥🔥 |

### Tier T — Testing & Monitoring (MUST HAVE — quality)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| T1 | Backend tests (pytest) | 2 hari | 🔥🔥🔥🔥🔥 |
| T2 | Frontend tests (vitest) | 1 hari | 🔥🔥🔥🔥 |
| T3 | Signal accuracy backtest suite | 1 hari | 🔥🔥🔥🔥🔥 |
| T4 | Sentry monitoring | 0.5 hari | 🔥🔥🔥 |
| T5 | API latency monitoring | 0.5 hari | 🔥🔥🔥 |

---

## 🏗️ Phase 3: ARCHITECT — Technical Design

### Signal Engine Architecture (NEW)

```
┌─────────────────────────────────────────────────┐
│                 SIGNAL ENGINE                      │
├─────────────────────────────────────────────────┤
│                                                   │
│  INPUT LAYER                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │
│  │ yfinance  │ │ Google   │ │ Macro    │ │  3rd │ │
│  │ (primary) │ │ News RSS │ │ API (BI) │ │ Data │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──┬───┘ │
│       │            │            │           │      │
│  PROCESSING LAYER                                │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐│
│  │ TA   │ │ Fund │ │ Sent │ │ Vol  │ │ Regime ││
│  │ Calc │ │ Calc │ │ NLP  │ │ Prof │ │ Detect ││
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └───┬────┘│
│     │        │        │        │          │      │
│  ENSEMBLE LAYER (Weighted - adaptive)          │
│  ┌──────────────────────────────────────────┐  │
│  │  Final Strength = TA*0.3 + Fund*0.3 +   │  │
│  │  Sent*0.2 + Vol*0.1 + Regime*0.1        │  │
│  └──────────────────────────────────────────┘  │
│         │                                       │
│  OUTPUT LAYER                                   │
│  ┌──────────────┐ ┌────────────────────────┐  │
│  │ BUY/SELL/    │ │ SL/TP, Risk Score,     │  │
│  │ NEUTRAL + 1-100│ Confidence Level       │  │
│  └──────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### New Data Flow

```
[yfinance] ──→ [Background Worker (every 5-15min)]
                  │
                  ├──→ [Redis Cache]
                  │       ├── stock:data:{symbol} → TTL 5min
                  │       ├── market:summary      → TTL 1min
                  │       └── news:{symbol}       → TTL 30min
                  │
[API Request] ──→ [FastAPI] ──→ [Redis Check]
                  │               ├── HIT  → return cached
                  │               └── MISS → background worker -> store -> return
                  │
[Frontend] ──→ [apiClient Layer] ──→ [In-memory TTL Cache (15s)]
                  │                       ├── same request in 15s → cache
                  │                       └── dedup concurrent requests
```

### Database Changes

```sql
-- New: backtest results table
CREATE TABLE IF NOT EXISTS signal_backtest (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES signal_recommendations(id),
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    entry_price REAL,
    exit_price REAL,
    entry_date TEXT,
    exit_date TEXT,
    return_pct REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    days_held INTEGER,
    outcome TEXT,  -- win/loss/pending
    created_at TEXT
);

-- New: market regime table
CREATE TABLE IF NOT EXISTS market_regime (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    regime TEXT NOT NULL,  -- trending_up/trending_down/ranging/volatile
    confidence REAL,
    ihsg_trend REAL,
    volatility REAL
);

-- New: signal_weights (adaptive per symbol/sektor)
CREATE TABLE IF NOT EXISTS signal_weights (
    id SERIAL PRIMARY KEY,
    symbol TEXT,
    sector TEXT,
    weight_technical REAL DEFAULT 0.3,
    weight_fundamental REAL DEFAULT 0.3,
    weight_sentiment REAL DEFAULT 0.2,
    weight_volume REAL DEFAULT 0.1,
    weight_regime REAL DEFAULT 0.1,
    updated_at TEXT
);
```

---

## 📅 Phase 2 (Detail): ROADMAP Eksekusi

### Sprint 1 — Foundation (Week 1)
```
BMAD Steps: Plan → Architect → Develop (partial)

Day 1-2:   A1 Router + A2 Zustand + A3 Backend routes
Day 3:     P2 API Cache layer (frontend + backend)
Day 4:     P3 Code splitting + P6 React memo audit
Day 5:     A6 Error boundaries
```

### Sprint 2 — Signal Engine v2 (Week 2)
```
BMAD Steps: Develop

Day 1-2:   S1 Backtesting engine + T3 Backtest suite
Day 3-4:   S2 Weighted ensemble + S3 Market regime
Day 5:     S4 Volume profile
```

### Sprint 3 — Performance + Data (Week 3)
```
Day 1:     P1 Virtual scroll + P9 Debounce
Day 2:     P4 Redis + P5 Background worker
Day 3:     S5 NLP upgrade (or API)
Day 4:     S6 Multi-timeframe + S7 SL/TP calculator
Day 5:     P7 Service worker + P10 Skeleton
```

### Sprint 4 — Signal Deepening (Week 4)
```
Day 1-2:   S8 Correlation + S9 Macro data
Day 3:     S10 Fallback provider + S11 Dashboard
Day 4:     S12 Outlier detection + S13 A/B test
Day 5:     U1-U10 UI polish batch
```

### Sprint 5 — Quality (Week 5+)
```
T1 Backend tests
T2 Frontend tests
T4 Sentry monitoring
A5 Refresh token
U5 Light mode
```

---

## 📊 Signal Accuracy — Target & Measurement

### Metric Definition

| Metric | Target | Cara Ukur |
|--------|--------|-----------|
| **Win Rate BUY** | ≥75% | (BUY benar) / (Total BUY) × 100 |
| **Win Rate SELL** | ≥70% | (SELL benar) / (Total SELL) × 100 |
| **Overall Accuracy** | ≥85% | Semua sinyal benar / total sinyal |
| **Avg Return per Signal** | ≥3% | Average return dari sinyal BUY |
| **Sharpe Ratio** | ≥1.5 | Risk-adjusted return |
| **Max Drawdown** | ≤-15% | Drawdown terbesar portfolio virtual |
| **Signal Consistency** | ≥70% | Sinyal yang konsisten di multi-timeframe |

### Evaluation Method

1. **Walk-forward analysis** — train 6 bulan, test 1 bulan, roll forward
2. **Out-of-sample test** — 20% data terakhir ga dipake training
3. **Monte Carlo simulation** — randomize entry timing, 1000x simulasi
4. **Benchmark vs IHSG** — sinyal harus outperform market

### Realistic Expectation

| Skenario | Target Accuracy | Notes |
|----------|----------------|-------|
| BUY signal (trending market) | 75-85% | Paling gampang karena market naik |
| SELL signal (trending down) | 70-80% | Agak susah karena short-term bounce |
| NEUTRAL (ranging market) | 80-90% | Paling aman |
| **Overall blended** | **80-85%** | Realistic target market campuran |
| With regime detection | 85-90% | Bisa naik kalau deteksi regime akurat |

---

## ⚡ Quick Wins — Ngerjain Hari Ini

Prioritas: ngerjain dulu yang effort kecil tapi impact gede.

| # | Task | Time | Signal Impact | Performance Impact |
|---|------|------|:---:|:---:|
| 1 | `React.memo` StockCard, SignalBadge | 10m | - | 🔥🔥🔥🔥 |
| 2 | Debounce search 300ms | 5m | - | 🔥🔥🔥 |
| 3 | Abort controller all fetch calls | 15m | - | 🔥🔥🔥 |
| 4 | Lazy load all remaining pages | 15m | - | 🔥🔥🔥🔥 |
| 5 | Skeleton loading for all panels | 1h | - | 🔥🔥🔥 |
| 6 | VWAP indicator tambahan | 1h | 🔥🔥🔥 | - |
| 7 | Volume confirmation filter | 30m | 🔥🔥🔥🔥 | - |
| 8 | Market regime detection (simple) | 1h | 🔥🔥🔥🔥 | - |
| 9 | SL/TP calculator basic (ATR) | 1h | 🔥🔥🔥 | - |
| 10 | Service worker cache strategi | 30m | - | 🔥🔥🔥 |

---

## 📁 Dokumen Terkait

- `IMPROVEMENT_PLAN.md` — Plan ini (hidup, update terus)
- `AGENTS.md` — Agent behavior rules
- `README.md` — Project overview
- `docs/ARCHITECTURE.md` — Technical architecture (todo)
- `docs/SIGNAL_METHODOLOGY.md` — Detail algoritma sinyal (todo)
- `docs/CHANGELOG.md` — Perubahan per release

---

## 🧠 BMAD Method — Cara Pakai

Skill `bmad-method-personalized` udah disimpen di Hermes. Setiap mulai task baru:

1. Load skill: `skill_view(name='bmad-method-personalized')`
2. Ikutin 7 langkah: Brainstorm → Plan → Architect → Develop → Review → Test → Deliver
3. Update plan ini kalo nemu insight baru
4. Save memory kalo nemu preference baru user
5. Save skill kalo nemu workflow reusable baru

---

*Plan ini live document — update terus sesuai progres.*
*Last updated: June 2026*
