# 🔬 METHODOLOGY — Metodologi Sinyal SahamApp

Dokumen ini menjelaskan **secara teknis** bagaimana SahamApp menghasilkan sinyal saham. Ditujukan untuk developer, quant researcher, dan pengguna yang ingin memahami logika di balik rekomendasi.

> **Audience:** Engineer, data scientist, technical PM
> **Reading time:** ~25 menit
> **Last updated:** v2.0.0

---

## Daftar Isi

1. [Filosofi Desain](#filosofi-desain)
2. [Arsitektur Sinyal](#arsitektur-sinyal)
3. [Technical Indicators](#technical-indicators)
4. [Fundamental Factors](#fundamental-factors)
5. [Sentiment Analysis](#sentiment-analysis)
6. [Volume Confirmation](#volume-confirmation)
7. [Market Regime Detection](#market-regime-detection)
8. [Multi-Timeframe Analysis](#multi-timeframe-analysis)
9. [Macro Data Integration](#macro-data-integration)
10. [Sector Correlation](#sector-correlation)
11. [Outlier Detection & Smoothing](#outlier-detection--smoothing)
12. [Weighted Ensemble Engine](#weighted-ensemble-engine)
13. [Confidence Calculation](#confidence-calculation)
14. [Stop Loss & Take Profit](#stop-loss--take-profit)
15. [Backtest Methodology](#backtest-methodology)
16. [A/B Testing Methodology](#ab-testing-methodology)
17. [Learning Loop](#learning-loop)
18. [Risk Disclaimers](#risk-disclaimers)

---

## Filosofi Desain

SahamApp dibangun dengan prinsip:

1. **Ensemble over single-model** — Tidak ada satu indikator yang sempurna. Kombinasi 5+ komponen lebih robust.
2. **Explainable over black-box** — Setiap sinyal punya `reasons[]` yang bisa diaudit.
3. **Adaptive over static** — Bobot ensemble berubah sesuai market regime.
4. **Self-improving** — Akurasi historis diumpan-balik untuk tweaking bobot.
5. **Risk-first** — SL/TP wajib di setiap rekomendasi, dengan RRR ≥ 1:2.

**Target akurasi:** ≥ 65% (vs random ~33% untuk 3-class signal).

---

## Arsitektur Sinyal

```
┌─────────────────────────────────────────────────────────────┐
│                  SIGNAL GENERATION PIPELINE                  │
└─────────────────────────────────────────────────────────────┘

  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  Tech Score  │  │  Fund Score  │  │  Sent Score  │
  │  (1-100)     │  │  (1-100)     │  │  (1-100)     │
  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
         │                 │                 │
         │     ┌───────────┴─────────┐       │
         │     │                     │       │
         │  ┌──▼──────┐        ┌─────▼─────┐ │
         │  │ Vol     │        │  Regime   │ │
         │  │ Score   │        │  Score    │ │
         │  │ (1-100) │        │  (1-100)  │ │
         │  └────┬────┘        └─────┬─────┘ │
         │       │                   │       │
         ▼       ▼                   ▼       ▼
       ┌─────────────────────────────────────────┐
       │       WEIGHTED ENSEMBLE (5 inputs)      │
       │     w_ta + w_fund + w_sent +            │
       │     w_vol + w_regime = 1.0              │
       └────────────────────┬────────────────────┘
                            │
                  ┌─────────▼─────────┐
                  │  Dynamic Weights  │
                  │  (regime-based)   │
                  └─────────┬─────────┘
                            │
                  ┌─────────▼─────────┐
                  │ Sector Correlation│
                  │   Adjustment      │
                  └─────────┬─────────┘
                            │
                  ┌─────────▼─────────┐
                  │ Outlier Detection │
                  │ & 3-day Smoothing │
                  └─────────┬─────────┘
                            │
                  ┌─────────▼─────────┐
                  │ Final Signal +    │
                  │ Confidence Level  │
                  └───────────────────┘
```

**Lokasi kode:** `backend/analysis.py` (indikator + ensemble), `backend/services/analysis_service.py` (orchestration).

---

## Technical Indicators

Semua indikator diimplementasi manual tanpa `pandas-ta` untuk transparansi dan kontrol penuh.

### RSI (Relative Strength Index)

**Formula** (Wilder's smoothing):
```
delta = close - close.shift(1)
gain = max(delta, 0)
loss = -min(delta, 0)
avg_gain = Wilder(gain, 14)
avg_loss = Wilder(loss, 14)
RS = avg_gain / avg_loss
RSI = 100 - (100 / (1 + RS))
```

**Interpretasi untuk sinyal:**
- RSI < 30 → +20 strength (oversold, peluang rebound)
- RSI 30–70 → netral, +0
- RSI > 70 → −20 strength (overbought, rawan koreksi)

### MACD (Moving Average Convergence Divergence)

**Komponen:**
- `EMA_12` — fast
- `EMA_26` — slow
- `MACD_line = EMA_12 − EMA_26`
- `Signal_line = EMA_9(MACD_line)`
- `Histogram = MACD_line − Signal_line`

**Crossover signals:**
- **Golden cross:** MACD crosses above Signal → +15 strength
- **Death cross:** MACD crosses below Signal → −15 strength

### SMA (Simple Moving Average)

- **SMA 20** — short-term trend
- **SMA 50** — medium-term trend

**Price position:**
- Price > SMA 50 → +10 strength (tren naik)
- Price < SMA 50 → −10 strength (tren turun)

### Bollinger Bands

**Komponen:**
- `Middle = SMA_20`
- `Upper = Middle + 2σ`
- `Lower = Middle − 2σ`

**Touch signals:**
- Price ≤ Lower × 1.01 → +10 strength (bounce potential)
- Price ≥ Upper × 0.99 → −10 strength (correction potential)

### Stochastic Oscillator

**Formula:**
```
%K = 100 × (Close − Low_14) / (High_14 − Low_14)
%D = SMA_3(%K)
```

**Interpretasi:** (tidak di-bonus langsung, hanya di-aggregate)

### VWAP (Volume Weighted Average Price)

**Formula:**
```
typical_price = (high + low + close) / 3
VWAP = cumsum(typical_price × volume) / cumsum(volume)
```

**Penggunaan:** VWAP sebagai reference level intraday. Harga di atas VWAP = buying pressure.

### ATR (Average True Range)

**Wilder's formula:**
```
TR = max(high − low, |high − prev_close|, |low − prev_close|)
ATR = EMA(TR, 14, alpha=1/14)
```

**Penggunaan utama:** basis untuk SL/TP calculation.

### EMA (Exponential Moving Average)

```
EMA_t = price × α + EMA_{t-1} × (1 − α)
α = 2 / (period + 1)
```

---

## Fundamental Factors

Sumber: `info` dict dari `yf.Ticker(symbol).info`.

| Metric | Key di yfinance | Bullish | Bearish | Weight |
|--------|-----------------|---------|---------|--------|
| PER (P/E Ratio) | `trailingPE` / `forwardPE` | < 15 (+15) | > 30 (−15) | Tinggi |
| PBV (P/B Ratio) | `priceToBook` | < 2 (+10) | > 5 (−10) | Sedang |
| Dividend Yield | `dividendYield` | > 3% (+10) | < 1% (+0) | Rendah |
| Market Cap | `marketCap` | > 50T (+5) | < 10T (+0) | Rendah |
| EPS | `trailingEps` | > 0 (+5) | < 0 (tidak dihitung) | Rendah |

**Catatan dividend yield:** yfinance kadang return decimal (0.06) atau percent (6.0). Auto-detect: `if dy > 1: assume_percent, else: * 100`.

---

## Sentiment Analysis

### Sumber Data

- **Google News RSS** via `feedparser`
- Query: `{symbol} OR {company_name} site:id OR saham`
- Bahasa: Indonesia + English (mixed)
- Limit: 5–20 berita per simbol
- Cache: 30 menit per simbol

### NLP Pipeline

`backend/services/news_service.py`:

1. **VADER** (NLTK): untuk teks Inggris/campuran
2. **Indonesian Lexicon** (kamus custom): untuk teks Indonesia
3. **Keyword Fallback**: untuk konteks spesifik (akuisisi, dividen, dll)

**Output per berita:**
```python
{
    "sentiment": "POSITIVE" | "NEUTRAL" | "NEGATIVE",
    "score": float,           # -1.0 to +1.0
    "confidence": float,      # 0.0 to 1.0
    "method": "vader" | "vader+id_lexicon" | "keyword"
}
```

**Score normalization ke −10 sampai +10:**
```python
sentiment_score_10 = int(round(result['score'] * 6))
```

### Agregasi

`aggregate_batch_sentiment()` menjumlahkan scores dari multiple berita:
- Positive ratio > 60% → `sentiment=POSITIVE`
- Negative ratio > 60% → `sentiment=NEGATIVE`
- Lainnya → `sentiment=NEUTRAL`

### Dampak ke Sinyal

Di `services/stock_service.py::_apply_news_bias()`:
- Sentimen positif kuat → bias +5 ke strength
- Sentimen negatif kuat → bias −5 ke strength

---

## Volume Confirmation

### Volume Ratio

```
volume_ratio = current_volume / avg_volume_20d
```

**Interpretasi:**
- `ratio > 1.5` → strength × 1.10 (boost)
- `ratio < 0.7` → strength × 0.85 (reduce)
- `0.7 ≤ ratio ≤ 1.5` → netral

### Volume Threshold

`VOLUME_THRESHOLD = 100_000` (config di `services/db.py`).

Saham dengan volume hari ini < 100,000 lembar:
- Sinyal teknikal dikurangi 10 strength
- Recalculate signal label

**Justifikasi:** Saham tidak likuid = spread lebar, slippage tinggi, sinyal kurang reliable.

### Volume Score (komponen ensemble)

`combine_signals()`:
- `ratio > 1.5` → vol_score = 75
- `ratio < 0.7` → vol_score = 25
- `0.7 ≤ ratio ≤ 1.5` → vol_score = 50

---

## Market Regime Detection

**Lokasi:** `analysis.py::detect_market_regime()`

### Algoritma

1. Compute SMA 50 dan SMA 200 (kalau data cukup)
2. Bandingkan:
   - `diff_pct = (SMA_50 − SMA_200) / SMA_200 × 100`
3. Klasifikasi:
   - `diff_pct > 2%` → `trending_up` (confidence 0.5 + diff_pct/20, cap 1.0)
   - `diff_pct < −2%` → `trending_down`
   - `−2% ≤ diff_pct ≤ 2%` → `ranging`
4. **Volatility override:**
   - ATR(14) > 1.5 × ATR(50) avg → `volatile`
5. **Fallback** untuk data < 200 hari:
   - Pakai close vs SMA 50
   - Threshold ±3% untuk trending

### Return

```python
{
    "regime": "trending_up" | "trending_down" | "ranging" | "volatile",
    "confidence": float  # 0.0–1.0
}
```

### Impact ke Bobot

Di `combine_signals()`:

| Regime | Adjustment |
|--------|-----------|
| `trending_up` | TA +10%, Sent −5% |
| `trending_down` | (no adjustment default) |
| `ranging` | Fund +10% |
| `volatile` | Regime +10% |

**Regime Score:**
- `trending_up` → 70
- `trending_down` → 30
- `volatile` → 40 (cautious)
- `ranging` → 50

---

## Multi-Timeframe Analysis

**Lokasi:** `backend/services/multitf.py`

Saham dianalisa di 3 timeframe secara paralel:

| Timeframe | Use Case |
|-----------|----------|
| 1d (daily) | Sinyal utama, intraday noise filter |
| 1wk (weekly) | Tren jangka menengah |
| 1mo (monthly) | Konteks makro |

**Composite score:** weighted average dari 3 timeframe signals.
- Daily: 50% weight
- Weekly: 30% weight
- Monthly: 20% weight

**Konfirmasi tren:** Sinyal HARIAN + MINGGUAN + BULANAN semua BUY → confidence boost.
**Divergence:** Sinyal harian BUY tapi weekly SELL → strength dikurangi.

---

## Macro Data Integration

**Lokasi:** `backend/services/macro.py`

### Data yang Diambil

- **IHSG** (^JKSE) — index utama
- **BI Rate** — Bank Indonesia rate
- **USD/IDR** — kurs dollar
- **Inflasi** — CPI bulanan

### Implementasi

Cache agresif (1 jam+) karena data makro berubah jarang. Update dari sumber publik (BI, BPS, Yahoo Finance).

### Impact ke Sinyal

- IHSG down > 3% intraday → semua sinyal BUY strength −5
- USD/IDR spike > 2% → saham import-dependent (terutama konsumer) dikurangi
- BI rate naik → bank/financial stocks di-boost

---

## Sector Correlation

**Lokasi:** `analysis.py::correlation_analysis()`

### Algoritma

1. Hitung rata-rata `change_percent` per sektor
2. Bandingkan dengan sinyal individual:
   - **Sektor turun > 3%** + signal **BUY** → strength −15
   - **Sektor naik > 3%** + signal **SELL** → strength −15

### Justifikasi

Saham individual sulit melawan tren sektor. Fight the trend = high risk.

### Sumber Data

`SECTOR_MAP` di `stock_data.py` — mapping symbol → sector (Perbankan, Energi, Telekomunikasi, dll).

---

## Outlier Detection & Smoothing

**Lokasi:** `analysis.py::detect_outlier()` dan `_smooth_over_3day()`

### Masalah

Lonjakan strength palsu bisa terjadi karena:
- Single-day price spike (gap up karena rumor/akuisisi)
- Data error dari yfinance
- Volume spike tidak sustainable

### Aturan

1. **Strength > 95 dengan rolling avg < 80** → cap ke `avg + 10`
2. **|current − avg_3d| > 15** → blend:
   ```
   adjusted = 0.6 × current + 0.4 × avg_3d
   ```
3. **Cap adjustment** ke ±20% dari original signal
4. Bound ke [1, 100]

### Sumber Historical Strengths

Di-load dari `signal_recommendations` table (DB) — 3–10 rekomendasi terakhir per simbol.

---

## Weighted Ensemble Engine

**Lokasi:** `analysis.py::combine_signals()`

### Default Weights

| Komponen | Weight |
|----------|--------|
| TA (Teknikal) | 0.30 |
| Fundamental | 0.30 |
| Sentimen | 0.20 |
| Volume | 0.10 |
| Regime | 0.10 |

Weights disimpan per-symbol di `signal_weights` table — bisa di-tune via A/B test results.

### Formula

```python
ensemble = (
    w_ta * ta_score
    + w_fund * fund_score
    + w_sent * sent_score
    + w_vol * vol_score
    + w_regime * regime_score
)
avg_strength = clamp(round(ensemble), 1, 100)
```

### Komponen Score

- **TA score** = technical signal strength (1–100)
- **Fund score** = fundamental signal strength (1–100)
- **Sent score** = derived dari agreement TA & Fund:
  ```
  sent_signals = [+1 if BUY, -1 if SELL, 0 if NEUTRAL] × [TA, Fund]
  sent_score = 50 + mean(sent_signals) × 40
  ```
  Range: 10 (full disagreement SELL) sampai 90 (full BUY agreement)
- **Vol score** = 25 / 50 / 75 (3-tier)
- **Regime score** = 30 / 40 / 50 / 70 (4-tier)

### Final Label

| avg_strength | Signal |
|--------------|--------|
| ≥ 65 | **BUY** |
| 36–64 | **NEUTRAL** |
| ≤ 35 | **SELL** |

---

## Confidence Calculation

**Formula:**
```python
component_signals = [label(score) for score in 5 components]
agreeing = count(component_signals == majority_signal)
agreement_pct = agreeing / 5 × 100
strength_extremity = |avg_strength - 50| / 50 × 100
confidence = min(100, round(agreement_pct × 0.6 + strength_extremity × 0.4))
```

**Contoh:**
- 5/5 komponen BUY + strength 80 → confidence 100
- 3/5 BUY + strength 65 → confidence ~52
- 3/5 NEUTRAL + strength 50 → confidence ~40

Confidence rendah = banyak komponen yang berbeda pendapat. **Sinyal bisa di-filter** jika confidence < threshold (default 30).

---

## Stop Loss & Take Profit

**Lokasi:** `analysis.py::calc_sl_tp()`

### Algoritma

ATR-based, regime-dependent:

| Regime | SL | TP | Min RRR |
|--------|----|----|---------|
| `trending_up` | entry − 1.5×ATR | entry + 3.0×ATR | 2.0 |
| `trending_down` | entry + 1.5×ATR | entry − 3.0×ATR | 2.0 |
| `ranging` | entry − 1.0×ATR | entry + 2.0×ATR | 2.0 |
| `volatile` | entry − 2.0×ATR | entry + 4.0×ATR | 2.0 |

**Risk-Reward Ratio (RRR):**
```
RRR = |TP - entry| / |entry - SL|
```

**Auto-widening:** jika RRR < 2.0, TP diperlebar sampai RRR = 2.0.

**Horizon:** 7 hari (default `TRADE_HORIZON_DAYS`).

### Output

```python
{
    "stop_loss": float,
    "take_profit": float,
    "risk_reward_ratio": float,
    "horizon_days": int
}
```

### Daily Check

`services/analysis_service.py::_daily_check_from_plan()`:
- `current_price` vs SL → "hold" / "near_sl" / "hit_sl"
- `current_price` vs TP → "hold" / "near_tp" / "hit_tp"
- Distance % dihitung

---

## Backtest Methodology

**Lokasi:** `backend/services/backtest.py`

### Konsep

Replay data historis, hitung return hipotetis jika kita follow semua sinyal.

### Algoritma

```python
1. Ambil data historis 1–2 tahun
2. Untuk setiap hari:
   a. Generate sinyal (as-if real-time)
   b. Jika BUY dan belum punya posisi → entry @ next open
   c. Track position sampai SL/TP hit atau horizon (7 hari) habis
3. Hitung cumulative return
```

### Metrics yang Dihitung

- **Total return** — cumulative %
- **Win rate** — % trade yang profit
- **Avg win / Avg loss** — rata-rata per trade
- **Max drawdown** — peak-to-trough terbesar
- **Sharpe ratio** — return / std × √252
- **Sortino ratio** — return / downside_std × √252
- **Calmar ratio** — return / max_drawdown

### Catatan

- Tidak include commission/slippage (idealized)
- Asumsi 100% allocation per trade (tidak realistic)
- Used for **research**, bukan live trading

---

## A/B Testing Methodology

**Lokasi:** `backend/services/abtest.py`

### Tujuan

Bandingkan dua versi model sinyal (mis. v1.0 vs v2.0) untuk lihat mana yang lebih akurat.

### Algoritma

1. **Split data** — random assign setiap rekomendasi ke group A atau B
2. **Variant config** — version A pakai weights default, version B pakai weights modified
3. **Run in parallel** — catat outcome untuk masing-masing
4. **Statistical test**:
   - Hitung accuracy per group
   - Hitung avg return per group
   - z-test proporsi untuk signifikansi
   - Confidence interval 95%

### Output (`compare_versions()`)

```python
{
    "version_a": {"accuracy": 0.62, "count": 2400, "avg_return": 0.8},
    "version_b": {"accuracy": 0.67, "count": 2400, "avg_return": 1.5},
    "winner": "B",
    "p_value": 0.012,  # significant
    "lift_pct": 8.06
}
```

### Minimum Sample Size

Untuk signifikansi statistik: **≥ 1000 rekomendasi per group**.

---

## Learning Loop

### End-to-End Flow

```
1. User buka detail saham
   → _record_recommendation() insert ke signal_recommendations
   → recommendation = "BUY", strength = 75, price = 10000
   → created_at = now

2. 7 hari kemudian
   → /api/learning/evaluate dipanggil (auto/manual)
   → _evaluate_learning_batch() query rekomendasi > 7 hari
   → Fetch harga sekarang → future_price
   → return_pct = (future_price - price) / price * 100
   → outcome = "up"/"down"/"neutral" sesuai rules
   → is_correct = 1/0

3. Akurasi dihitung
   → accuracy = count(is_correct=1) / count(evaluated)
   → By signal type breakdown

4. (Optional) Update weights
   → A/B test results bisa update signal_weights table
   → Production rollback jika versi baru lebih buruk
```

### Auto-Evaluation Trigger

`/api/learning/evaluate` bisa dipanggil:
- Manual dari UI (tombol "Evaluasi")
- Otomatis via cron (jika di-setup, mis. Vercel cron daily)
- Background worker (planned)

### Why 7 Days?

- Timeframe trading retail Indonesia (swing trade)
- Cukup untuk signal memvalidasi (momentum, mean reversion)
- Tidak terlalu lama (lupa posisi)

---

## Risk Disclaimers

> ⚠️ **BUKAN SARAN INVESTASI**
>
> 1. Sinyal SahamApp adalah **probabilistic**, bukan deterministic. Akurasi historis tidak menjamin hasil masa depan.
>
> 2. **Loss bisa 100% modal.** Trading saham memiliki risiko kehilangan seluruh investasi. Jangan gunakan uang yang tidak siap hilang.
>
> 3. **Data delay.** Harga dari Yahoo Finance bisa delay 15 menit. Saat market volatile, harga bisa beda jauh dari real-time.
>
> 4. **Slippage & spread tidak dihitung.** Backtest ideal, real trading ada biaya transaksi, PPh, bid-ask spread.
>
> 5. **SahamApp tidak terafiliasi dengan broker manapun.** Portofolio adalah simulasi.
>
> 6. **Gunakan sebagai SECOND OPINION, bukan SATU-SATUNYA alat.** Selalu DYOR + konsultasi dengan profesional.
>
> 7. **Performa lalu tidak mencerminkan masa depan.** Market regime bisa berubah.
>
> 8. **Algoritma bisa salah.** Outlier detection tidak sempurna, model bisa miss edge cases (stock split, suspensions, dll).
>
> 9. **No guarantee of uptime.** Server bisa down, API bisa return error, data bisa stale. Selalu punya backup plan.
>
> 10. **Pengguna bertanggung jawab penuh** atas keputusan investasi. Dengan menggunakan SahamApp, Anda setuju dengan disclaimer ini.

---

## Appendix: Parameter Reference

| Parameter | Value | Lokasi |
|-----------|-------|--------|
| `VOLUME_THRESHOLD` | 500,000 | `services/db.py` |
| `MIN_PRICE` | 50 IDR | `stock_data.py` |
| `MIN_AVG_VALUE` | 1B IDR | `stock_data.py` |
| `LEARNING_WINDOW_DAYS` | 7 | `services/db.py` |
| `TRADE_HORIZON_DAYS` | 7 | `services/db.py` |
| `STOP_LOSS_PCT` | −5% | `services/db.py` |
| `TAKE_PROFIT_PCT` | +8% | `services/db.py` |
| `AUTH_TOKEN_TTL_SECONDS` | 30 hari | `services/db.py` |
| RSI period | 14 | `analysis.py` |
| MACD fast/slow/signal | 12/26/9 | `analysis.py` |
| Bollinger period | 20, std 2 | `analysis.py` |
| Stochastic K/D | 14/3 | `analysis.py` |
| ATR period | 14 (Wilder) | `analysis.py` |
| Rate limit | 200/min/IP | `app.py` |
| Max request body | 1 MB | `app.py` |

---

## Referensi

- Wilder, J. W. (1978). *New Concepts in Technical Trading Systems*
- Murphy, J. J. (1999). *Technical Analysis of the Financial Markets*
- Hutto, C. J. & Gilbert, E. E. (2014). *VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text*
- yfinance docs: https://github.com/ranaroussi/yfinance
- Bursa Efek Indonesia: https://www.idx.co.id

---

<p align="center">📊 Metodologi SahamApp © 2024-2026</p>
