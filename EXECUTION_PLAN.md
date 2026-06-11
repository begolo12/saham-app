# 🚀 Saham ID — Eksekusi Plan (BMAD Method)

**Project:** Saham ID — Indonesian Stock Signal Analysis App
**Method:** BMAD (Breakthrough Method of Agile AI-Driven Development)
**Target:** 90% signal accuracy + silky smooth performance + premium UX
**Owner:** Irvan / Daniswara Group
**Estimasi Total:** ~5-6 minggu (parallel agent bisa potong 40% waktu)

---

## 📊 OVERVIEW — Semua Task

| Tier | Jumlah Task | Total Estimasi | Prioritas |
|------|-------------|----------------|-----------|
| 🎯 **S - Signal Accuracy** | 13 task | 16 hari | 🔥 WAJIB |
| ⚡ **P - Performance** | 10 task | 8.5 hari | 🔥 WAJIB |
| 🎨 **U - UI/UX Polish** | 10 task | 8 hari | 👍 PENTING |
| 🏗️ **A - Architecture** | 6 task | 4 hari | 🔧 DASAR |
| 🧪 **T - Testing & Monitoring** | 5 task | 5 hari | 🔥 WAJIB |
| **TOTAL** | **44 task** | **41.5 hari** | |

> **Catatan:** Dengan parallel agent (delegate ke erp-backend, erp-frontend, erp-database bersamaan), waktu real bisa 2-3 minggu kerja efektif.

---

## 🧩 DEPENDENCY GRAPH — Urutan Wajib

```
ARC: A1 Router ──→ A2 Zustand ──→ A6 Error Boundary
       │               │
       ├──────┬────────┘
       │      │
       ▼      ▼
PERF: P2 Cache ──→ P3 Code Split ──→ P1 Virtual Scroll
  │    Layer          │                   │
  │                   ▼                   │
  ├──→ P5 Redis ──→ P4 Background         │
  │                  Worker                │
  ├──→ P6 Memo Audit                      │
  ├──→ P7 Service Worker                  │
  ├──→ P8 Image Opt                       │
  ├──→ P9 Debounce                        │
  └──→ P10 Skeleton                       │
                                          │
SIGNAL: S1 Backtest ──→ S2 Ensemble ────→ S8 Correlation
  │                     │                   │
  ├──→ S3 Regime        ├──→ S4 Volume     ├──→ S9 Macro
  │                     ├──→ S5 NLP        │
  │                     ├──→ S6 Multi-TF   │
  │                     └──→ S7 SL/TP      │
  │                                        │
  └──→ S10 Fallback     S11 Dashboard      │
      ────────────────── S12 Outlier ──────┤
                         S13 A/B Test ────┘
                                           │
                                     ┌─────┘
                                     ▼
TEST: T1 Backend    T2 Frontend
      T3 Backtest   T4 Sentry
                    T5 Latency
```

---

## 📅 FASE 0 — Quick Wins (Hari 1) ~4 jam

**BMAD Step:** Develop
**Agent:** erp-frontend + erp-backend

| # | Task | Agent | Waktu | Detail |
|---|------|-------|-------|--------|
| QW1 | `React.memo` StockCard, SignalBadge | erp-frontend | 10m | Bungkus export pake React.memo |
| QW2 | Debounce search 300ms | erp-frontend | 5m | setTimeout di onChange search |
| QW3 | Abort controller semua fetch | erp-frontend | 15m | AbortController di tiap fetchJson call |
| QW4 | Lazy load 7 page | erp-frontend | 15m | React.lazy + Suspense untuk semua panel |
| QW5 | VWAP indikator | erp-backend | 1h | Fungsi calc_vwap di analysis.py |
| QW6 | Volume confirmation filter | erp-backend | 30m | Kalo signal BUY tapi volume turun → reduce strength |
| QW7 | Market regime simple | erp-backend | 1h | Deteksi trend/range pake SMA50 vs SMA200 |
| QW8 | SL/TP calculator ATR | erp-backend | 1h | ATR-based stop loss & take profit |
| QW9 | Service worker cache strat | erp-frontend | 30m | Cache-first assets, network-first data |
| QW10 | Skeleton loading all panels | erp-frontend | 1h | Skeleton tiap page punya sendiri |

**Hasil:** ✅ Signal +3-5% accuracy. Bundle split. Scroll ringan. UX lgsg naik.

---

## 📅 FASE 1 — Foundation Architecture (4-5 hari)

**BMAD Step:** Architect → Develop
**Objective:** Pisah monolith, pasang router, state management

### Day 1-2: Frontend Architecture
**Agent:** erp-architect + erp-frontend

| Task | Detail | Agent | Dependencies |
|------|--------|-------|-------------|
| **A1 — React Router** | Pasang react-router-dom, ubah App.jsx routing state-based → path-based. Pages: `/`, `/signal`, `/news`, `/portfolio`, `/learning`, `/stock/:symbol` | erp-frontend | None |
| **A2 — Zustand Store** | Store auth, stocks, portfolio, watchlist. Hilangkan prop drilling | erp-frontend | A1 |
| **A6 — Error Boundaries** | ErrorBoundary component tiap page + global fallback | erp-frontend | A1+A2 |
| **U10 — Micro-interactions** | Tap ripple effect, spring animations native | erp-frontend | A1 |

**Hasil:** ✅ App.jsx turun dari 877 → ~100 baris. Router kerja. State rapi.

### Day 3-5: Backend Architecture
**Agent:** erp-architect + erp-backend

| Task | Detail | Agent | Dependencies |
|------|--------|-------|-------------|
| **A3 — Backend Routes Pisah** | `routes/auth.py`, `routes/stocks.py`, `routes/news.py`, `routes/portfolio.py`, `routes/learning.py` pake APIRouter | erp-backend | None |
| **A4 — Pydantic Schemas** | `schemas/` folder buat request/response validation | erp-backend | A3 |
| **A5 — Refresh Token** | access token 15m + refresh token 30d. Auto-refresh di frontend | erp-backend + erp-security | A3 |
| **P4 — Redis Setup** | Upstash Redis (free tier) atau Redis lokal via Docker. Cache wrapper functions | erp-devops + erp-backend | A3 |
| **P5 — Background Worker** | ARQ/FastAPI background task refresh stock data tiap 5-15 menit, simpan di Redis | erp-backend | P4 |

**Hasil:** ✅ Backend 1761 baris → terstruktur. Token aman. Data di-cache. Ga blocking di yfinance.

### Day 5: Database
**Agent:** erp-database

| Task | Detail | Dependencies |
|------|--------|-------------|
| **DB1 — New tables** | `signal_backtest`, `market_regime`, `signal_weights` | A3 |
| **DB2 — Migration plan** | SQL migration script, index optimization | A3 |
| **DB3 — Neon optimization** | Connection pooling, query performance | None |

---

## 📅 FASE 2 — Signal Engine v2 (5-6 hari)

**BMAD Step:** Develop (parallel)
**Objective:** Signal accuracy naik dari 60-70% ke 80-85%

### Day 1-2: Backtesting Engine (S1) + Test Suite (T3)
**Agent:** erp-backend + erp-tester

| Task | Detail | Dependencies |
|------|--------|-------------|
| **S1 — Backtest Engine** | Ambil historical data 1-3 tahun, evaluate sinyal yg udah direkam. Hitung win rate, avg return, Sharpe, max drawdown. Simpan di `signal_backtest` table | A3 |
| **T3 — Backtest Suite** | pytest suite: backtest semua sinyal, verify accuracy metrics | S1 |

### Day 2-3: Weighted Ensemble (S2) + Market Regime (S3) + Volume Profile (S4)
**Agent:** erp-backend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **S2 — Weighted Ensemble** | Bobot dinamis per kondisi market. Default: TA 0.3, Fund 0.3, Sent 0.2, Vol 0.1, Regime 0.1 | A3 |
| **S3 — Market Regime** | Deteksi trending_up/trending_down/ranging/volatile pake ADX + SMA50/200 cross | A3 |
| **S4 — Volume Profile** | VWAP (dari QW5), volume trend filter, volume spike detection | A3 |

### Day 3-4: NLP Upgrade (S5) + Multi-Timeframe (S6)
**Agent:** erp-backend + erp-architect

| Task | Detail | Dependencies |
|------|--------|-------------|
| **S5 — NLP Sentiment** | Upgrade dari word counting → IndoBERT kecil (distilbert) via HuggingFace atau API sentiment eksternal | A3 |
| **S6 — Multi-Timeframe** | Daily + weekly + 1h. Sinyal valid cuma kalo 2/3 timeframe searah | S2 |

### Day 4-5: SL/TP Calculator (S7) + Correlation (S8)
**Agent:** erp-backend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **S7 — SL/TP** | ATR-based (dari QW8). Risk/reward ratio min 1:2 | S2 |
| **S8 — Sector Correlation** | Hitung korelasi return antar saham di sektor sama. Kalo sektor turun semua, signal BUY individual lemah | A3 |

### Day 5-6: Macro Data (S9) + Fallback (S10) + Dashboard (S11)
**Agent:** erp-backend + erp-database + erp-frontend

| Task | Detail | Agent | Dependencies |
|------|--------|-------|-------------|
| **S9 — Macro** | Ambil BI rate, inflasi, USD/IDR dari API publik (bi.go.id / exchangerate-api). Simpan di `market_regime` | erp-backend | A3 |
| **S10 — Fallback** | Kalo yfinance down, scrape Yahoo Finance HTML langsung atau pake API alternatif | erp-backend | A3 |
| **S11 — Dashboard Akurasi** | Halaman baru `/accuracy` — liat win rate per sinyal, grafik performa, confusion matrix | erp-frontend | A2+S1 |

---

## 📅 FASE 3 — Performance Sprint (4-5 hari)

**BMAD Step:** Develop + Review
**Objective:** App terasa "sat set" — scroll mulus, loading cepet, bundle kecil

### Day 1: Virtual Scroll (P1) + Debounce (P9)
**Agent:** erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **P1 — Virtual Scroll** | `@tanstack/react-virtual`. StockList cuma render ~10 card dari 140 | A1 |
| **P9 — Debounce** | Fuse.js + 300ms debounce di search bar (ditingkatin dari QW2) | A1 |

### Day 2: API Cache Layer (P2) + Service Worker (P7)
**Agent:** erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **P2 — Cache Layer** | In-memory TTL cache (15s default). Request dedup (2 component minta data sama → 1 fetch). Abort stale requests | A1 |
| **P7 — Service Worker** | Workbox atau custom SW. Cache-first assets (JS/CSS/images). Network-first API data. Offline fallback page | A1 |

### Day 3: Code Splitting (P3) + Memo Audit (P6)
**Agent:** erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **P3 — Code Split** | Confirm React.lazy + Suspense for all 7 pages. Verify bundle split at build time | A1 |
| **P6 — Memo Audit** | Audit 20+ components. StockCard, SignalBadge, MarketSummary, Chart, Gauge, dll | A1 |

### Day 4: Image Opt (P8) + Skeleton Refine (P10)
**Agent:** erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **P8 — Image Opt** | Compress hero.png, icon → WebP. Lazy load images below fold | None |
| **P10 — Skeleton Refine** | Skeleton spesifik per page (chart skeleton, list skeleton, detail skeleton) — ditingkatin dari QW10 | A1 |

### Day 5: Redis Cache + Background Worker (P4+P5) deep
**Agent:** erp-backend + erp-devops

| Task | Detail | Dependencies |
|------|--------|-------------|
| **P4 — Redis deep** | Cache all: stock data 5min, chart 15min, news 30min, market 1min. Stale-while-revalidate pattern | Fase 1 |
| **P5 — Worker deep** | Background job refresh top 30 stocks tiap 5 menit. Refresh all 140 tiap 15 menit. Push ke Redis | P4 |

---

## 📅 FASE 4 — Signal Deepening (4-5 hari)

**BMAD Step:** Develop + Review
**Objective:** Signal accuracy 85-90%. Robust di semua kondisi market.

### Day 1-2: Outlier Detection (S12) + A/B Test (S13)
**Agent:** erp-backend + erp-database

| Task | Detail | Dependencies |
|------|--------|-------------|
| **S12 — Outlier** | Deteksi signal strength anomali (tiba2 100 padahal biasanya 60). Flag manual review. Compare dengan historical average | S2 |
| **S13 — A/B Test** | Signal engine v1 vs v2. 50% user dapet v1, 50% v2. Compare accuracy real-time di dashboard | S1+S11 |

### Day 3: Signal Accuracy Dashboard (S11) — Frontend
**Agent:** erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **S11 Frontend** | Halaman `/accuracy` — grafik win rate, confusion matrix, Sharpe ratio trend, signal distribution per sector | A2+S11 Backend |

### Day 4-5: Weight Tuning + Optimization
**Agent:** erp-backend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **S2b — Weight Tuning** | Dari data backtest, optimize bobot ensemble. Grid search kombinasi bobot terbaik | S1+S13 |
| **S12b — Auto-fix outlier** | Kalo outlier detected, auto-adjust strength ke historical mean | S12 |

---

## 📅 FASE 5 — UI/UX Polish (4-5 hari)

**BMAD Step:** Develop + Review
**Objective:** Aplikasi feels premium, iOS 18 aesthetic, mobile-first

### Day 1: Bottom Sheet (U1) + Animations (U2)
**Agent:** erp-frontend + erp-ui-designer

| Task | Detail | Dependencies |
|------|--------|-------------|
| **U1 — Bottom Sheet** | Ganti modal filter/sort pake bottom sheet (drag down to dismiss). iOS-style | A1 |
| **U2 — Spring Animations** | Consistent spring curve di semua transisi. Page transisi slide. Card muncul staggered | A1 |

### Day 2: Dark Mode Refine (U3) + Light Mode (U4)
**Agent:** erp-ui-designer + erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **U3 — Dark Refine** | Audit konsistensi warna di semua component. Contrast ratio check. iOS 18 dark scheme | A1 |
| **U4 — Light Mode** | CSS variables untuk light theme. Toggle + system preference detect | A1 |

### Day 3: PWA Install Prompt (U5) + Haptic (U6)
**Agent:** erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **U5 — PWA Install** | beforeinstallprompt handler. Install banner setelah user buka 2x | A1 |
| **U6 — Haptic Feedback** | navigator.vibrate() untuk tap action penting. Fallback kalo ga support | A1 |

### Day 4: Empty States (U7) + Swipe Actions (U8)
**Agent:** erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **U7 — Empty States** | Desain ulang empty state tiap panel — ilustrasi + call to action | A1 |
| **U8 — Swipe Actions** | Swipe-to-delete portfolio item. Swipe-to-add watchlist. Pake library atau gesture custom | A1 |

### Day 5: UI Audit + Consistency Pass
**Agent:** erp-ui-designer + erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **U9 — UI Audit** | Cek semua halaman di 375px viewport. Spacing 4px grid. Font hierarchy. Color consistency | U1-U8 |
| **U10b — Micro-interactions** | Final polish: tab bar indicator animation, button press state, scroll indicator | U2 |

---

## 📅 FASE 6 — Testing & Monitoring (5 hari)

**BMAD Step:** Test → Review → Deliver
**Objective:** Quality assurance. Production-ready.

### Day 1-2: Backend Tests (T1)
**Agent:** erp-tester + erp-backend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **T1a — API Tests** | pytest + httpx. Test semua endpoint: stocks, auth, portfolio, news, learning | A3+A4+A5 |
| **T1b — Signal Tests** | Test signal generation functions, edge cases (data null, volume 0, etc) | S1-S10 |
| **T1c — Integration Tests** | Test full flow: fetch stock → generate signal → record → backtest | S1 |

### Day 3: Frontend Tests (T2)
**Agent:** erp-tester + erp-frontend

| Task | Detail | Dependencies |
|------|--------|-------------|
| **T2a — Component Tests** | vitest + testing-library. Test render utama: StockList, StockDetail, Chart, SignalBadge | A1+A2 |
| **T2b — API Mock Tests** | Mock API calls. Test loading state, error state, empty state | A2 |
| **T2c — Flow Tests** | Test user flow: login → market → detail → portfolio → logout | A2+A5 |

### Day 4: Sentry + Monitoring (T4+T5)
**Agent:** erp-devops + erp-security

| Task | Detail | Dependencies |
|------|--------|-------------|
| **T4 — Sentry** | Setup Sentry SDK frontend + backend. Error tracking + performance monitoring | None |
| **T5 — API Latency** | Track p50/p95/p99 latency per endpoint. Alert if >5s | P4+P5 |

### Day 5: Performance Audit + Security Audit
**Agent:** erp-devops + erp-security

| Task | Detail | Dependencies |
|------|--------|-------------|
| **T4b — Performance Audit** | Lighthouse score target: Performance ≥90, PWA ≥80, Accessibility ≥95 | P1-P10 |
| **T5b — Security Audit** | Cek SQL injection, XSS, rate limiting, auth token security, CORS, helmet headers | A5 |

---

## 📅 FASE 7 — Delivery & Docs (2 hari)

**BMAD Step:** Deliver
**Objective:** Dokumentasi, deployment, skill save

### Day 1: Documentation
**Agent:** erp-docs

| Task | Detail | Dependencies |
|------|--------|-------------|
| **D1 — API Docs** | Update OpenAPI spec. Document new endpoints | A3 |
| **D2 — README Update** | Fitur baru, cara install, env vars, architecture overview | - |
| **D3 — CHANGELOG** | Perubahan per fase versi | - |
| **D4 — SIGNAL_METHODOLOGY.md** | Dokumentasi algoritma sinyal detail — biar user percaya | S1-S13 |

### Day 2: Deployment + Release
**Agent:** erp-devops

| Task | Detail | Dependencies |
|------|--------|-------------|
| **DEP1 — Staging Deploy** | Deploy ke staging. Verifikasi semua fitur | All |
| **DEP2 — Prod Deploy** | Deploy ke Vercel (frontend) + Railway/Render (backend) | DEP1 |
| **DEP3 — Skill Save** | Save skill untuk workflow baru yang reusable | All |
| **DEP4 — Memory Save** | Save environment config, quirk produksi | All |

---

## 📊 TIMELINE — Gantt Chart

```
Minggu 1               | Minggu 2               | Minggu 3               | Minggu 4               | Minggu 5-6
Quick Wins ████████    |                        |                        |                        |
Fase 1 Arc ████████████ |                       |                        |                        |
Fase 2 Sig ████████████████████                 |                       |                        |
Fase 3 Per ██████████████████████████           |                       |                        |
Fase 4 Dpn ──────────── ████████████████████    |                       |                        |
Fase 5 UI  ──────────── ──────────── ████████████████████              |                       |
Fase 6 T&M ──────────── ──────────── ──────────── ████████████████████ |                       |
Fase 7 Doc ──────────── ──────────── ──────────── ──────────── ████████|
```

> **Dengan parallel agent (erp-frontend + erp-backend + erp-database bersamaan):** bisa potong 40% → real time **3-4 minggu**.

---

## 👥 ASSIGNMENT — Siapa Ngapain

| Agent | Fase | Total Task |
|-------|------|------------|
| **erp-architect** | Fase 1 (design), Fase 2 (signal arch) | 5 task |
| **erp-backend** | Fase 1 (routes), Fase 2 (signal engine), Fase 4 (deep) | 20 task |
| **erp-frontend** | Quick wins, Fase 1 (router/store), Fase 3 (perf), Fase 5 (UI) | 25 task |
| **erp-database** | Fase 1 (migration), Fase 4 (optimization) | 3 task |
| **erp-ui-designer** | Fase 5 (UI polish, design audit) | 4 task |
| **erp-tester** | Fase 6 (testing) | 5 task |
| **erp-devops** | Fase 6 (Sentry/deploy), Fase 7 (deploy) | 5 task |
| **erp-security** | Fase 1 (auth), Fase 6 (security audit) | 3 task |
| **erp-docs** | Fase 7 (documentation) | 4 task |

---

## 🚨 RISK & MITIGATION

| Risk | Probability | Impact | Mitigasi |
|------|:-----------:|:------:|----------|
| yfinance rate limit | Tinggi | Tinggi | Cache agresif (Redis 5-15m). Fallback provider S10 |
| Redis cost | Rendah | Rendah | Upstash free tier (30MB cukup untuk stock data) |
| NLP model too heavy | Sedang | Sedang | Start pake API sentiment dulu, upgrade ke local model kalo perlu |
| Signal accuracy < target | Sedang | Tinggi | Iterative improve: backtest → adjust weights → re-test |
| Frontend bundle grows | Rendah | Rendah | Code splitting + dynamic import. Monitor bundle size |
| User feedback negatif | Rendah | Sedang | A/B test (S13). Rollback ke v1 kalo v2 jelek |

---

## ✅ DONE DEFINED — Kapan Selesai?

Tiap fase dikatakan **selesai** kalo:

- ✅ Semua task di fase completed
- ✅ Tests passing (pytest + vitest)
- ✅ Lighthouse Performance ≥90
- ✅ Signal accuracy (backtest) ≥85%
- ✅ Manual test: login → browse → detail → portfolio — all smooth
- ✅ Deployed dan bisa diakses user

---

## 🎯 MILESTONE CHECKLIST

```
[ ] QW  — Quick Wins selesai        (target: Hari 1)
[ ] F1  — Foundation Architecture   (target: Akhir Minggu 1)
[ ] F2  — Signal Engine v2          (target: Akhir Minggu 2)
[ ] F3  — Performance Sprint        (target: Akhir Minggu 3)
[ ] F4  — Signal Deepening          (target: Akhir Minggu 4)
[ ] F5  — UI Polish                 (target: Akhir Minggu 4-5)
[ ] F6  — Testing & Monitoring      (target: Akhir Minggu 5)
[ ] F7  — Delivery & Docs           (target: Akhir Minggu 6)
```

---

*Plan ini live document — update terus sesuai progres.*
*BMAD Method: Brainstorm → Plan → Architect → Develop → Review → Test → Deliver*
