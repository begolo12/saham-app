# 📱 Panduan Pengguna SahamApp

Selamat datang di **SahamApp** — aplikasi analisis saham Indonesia yang membantu Anda membuat keputusan investasi lebih cerdas. Panduan ini akan menjelaskan semua fitur aplikasi dalam **Bahasa Indonesia**.

---

## Daftar Isi

1. [Mengenal Antarmuka](#mengenal-antarmuka)
2. [Login & Akun](#login--akun)
3. [Sinyal BELI / JUAL / TAHAN](#sinyal-beli--jual--tahan)
4. [Membaca Stop Loss & Take Profit](#membaca-stop-loss--take-profit)
5. [Watchlist (Saham Favorit)](#watchlist-saham-favorit)
6. [Portofolio Virtual](#portofolio-virtual)
7. [News (Berita & Sentimen)](#news-berita--sentimen)
8. [Learning (Evaluasi Akurasi)](#learning-evaluasi-akurasi)
9. [Signal Dashboard](#signal-dashboard)
10. [Daily Report](#daily-report)
11. [FAQ](#faq)
12. [Disclaimer](#disclaimer)

---

## Mengenal Antarmuka

SahamApp menggunakan desain **iOS 18** dengan bottom navigation. Buka aplikasinya, Anda akan melihat 5 tab utama di bagian bawah:

```
┌─────────────────────────────────────────────┐
│                                             │
│           [Konten Halaman Aktif]            │
│                                             │
│                                             │
├─────────────────────────────────────────────┤
│  🏠      📊      📰      💼      📚        │
│ Market  Sinyal   Berita  Porto  Belajar    │
└─────────────────────────────────────────────┘
```

- **🏠 Market** — Halaman utama dengan ringkasan IHSG + daftar saham top
- **📊 Sinyal** — Semua sinyal BUY/SELL aktif, diurutkan berdasarkan kekuatan
- **📰 Berita** — News + sentimen analisa untuk saham pilihan
- **💼 Portofolio** — Portofolio virtual, P/L, win rate
- **📚 Belajar** — Evaluasi akurasi sinyal 7-hari

**Header atas:**
- ⬅️ Tombol kembali (di halaman tertentu)
- 🌓 Toggle dark/light mode
- 👤 Username + tombol Logout

**Gesture:**
- **Pull-to-refresh** — Tarik layar ke bawah untuk refresh data
- **Swipe** di beberapa list
- **Tap** kartu saham untuk lihat detail

---

## Login & Akun

### Pertama Kali

Saat pertama buka aplikasi, Anda akan diminta **login**. Gunakan akun default:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin123` |

> ⚠️ **PENTING:** Segera ubah password default setelah login pertama, terutama di environment production.

### Cara Kerja Autentikasi

1. Masukkan username + password
2. Server memverifikasi kredensial
3. Server mengembalikan **access token** (berlaku 30 hari) + **refresh token**
4. Token disimpan di `localStorage` browser
5. Setiap request ke API menyertakan `Authorization: Bearer <token>`

### Multi-User

SahamApp mendukung banyak user. Admin (role `superadmin`) bisa membuat user baru di tab **Portofolio → Kelola User**.

**Role yang tersedia:**
- `user` — Akses standar, bisa kelola portofolio sendiri
- `superadmin` — Bisa kelola semua user + akses admin panel

---

## Sinyal BELI / JUAL / TAHAN

Ini adalah fitur utama SahamApp. Setiap saham punya **sinyal** yang menunjukkan apakah layak dibeli, dijual, atau ditahan.

### Apa Arti Masing-Masing?

| Sinyal | Label UI | Arti | Rekomendasi |
|--------|----------|------|-------------|
| **BUY** | 🟢 **BELI** | Sinyal teknikal + fundamental + sentimen cukup kuat untuk entry | Pertimbangkan beli, tetap pakai stop loss |
| **NEUTRAL** | 🟡 **TAHAN** | Tidak ada edge jelas, pasar masih ragu-ragu | Tunggu konfirmasi, jangan FOMO |
| **SELL** | 🔴 **JUAL** | Tekanan jual dominan, risiko turun lebih besar | Hindari entry / kurangi posisi |

### Kekuatan Sinyal (0–100)

SahamApp juga menampilkan **signal strength** — skor numerik 1 sampai 100. Makin tinggi, makin kuat sinyalnya.

```
Score: 1 ─────────── 50 ─────────── 100
       SELL Kuat   Netral       BUY Kuat
```

**Threshold:**
- Score ≥ 65 → sinyal **BUY**
- Score 36–64 → sinyal **NEUTRAL / TAHAN**
- Score ≤ 35 → sinyal **SELL**

**Contoh badge di UI:**
- `BUY 78` → sinyal beli dengan kekuatan 78/100 (cukup kuat)
- `HOLD 52` → netral, tidak ada dominasi
- `SELL 28` → sinyal jual, kekuatan 28/100 (lemah, pasar bisa berbalik)

### Bagaimana Sinyal Dihitung?

Sinyal adalah **weighted ensemble** dari 5 komponen:

1. **Teknikal (30%)** — RSI, MACD, SMA 20/50, Bollinger, Stochastic
2. **Fundamental (30%)** — PER, PBV, dividend yield, market cap, EPS
3. **Sentimen Berita (20%)** — Analisa NLP dari Google News
4. **Volume (10%)** — Konfirmasi volume (apakah ada akumulasi/distribusi?)
5. **Market Regime (10%)** — trending/ranging/volatile detection

Detail metodologi lengkap: **[METHODOLOGY.md](METHODOLOGY.md)**.

### Kenapa Sinyal Bisa Berubah?

Sinyal di-recalculate tiap kali Anda refresh halaman (default 60 detik). Faktor-faktor yang bisa memicu perubahan:

- Pergerakan harga menembus SMA 20 atau SMA 50
- RSI crossing ke zona oversold/overbought
- Volume spike di atas 150% rata-rata
- Berita baru dengan sentimen kuat
- Pergerakan IHSG yang mengubah market regime

---

## Membaca Stop Loss & Take Profit

Setiap rekomendasi BUY otomatis disertai **Stop Loss (SL)** dan **Take Profit (TP)**.

### Stop Loss (SL)

Harga di mana Anda harus **cut loss** untuk membatasi kerugian. Dihitung berbasis **ATR (Average True Range)**.

**Contoh:**
```
Entry:    Rp 10,250
SL:       Rp 9,850
Risk:     -3.9% (rugi maksimal jika SL kena)
```

**Aturan umum:**
- Mode `trending_up` → SL = entry − 1.5×ATR
- Mode `ranging` → SL = entry − 1.0×ATR
- Mode `volatile` → SL = entry − 2.0×ATR

### Take Profit (TP)

Harga target untuk **take profit**. SL/TP dirancang untuk **risk:reward ratio minimal 1:2**.

**Contoh:**
```
Entry:    Rp 10,250
TP:       Rp 11,050
Reward:   +7.8%

SL:       Rp 9,850
Risk:     -3.9%

RRR = 7.8 / 3.9 = 2.0  ✓
```

### Horizon

Default horizon trading: **7 hari**. Ini artinya:
- Evaluasi keputusan dilakukan 7 hari setelah sinyal muncul
- TP dan SL dirancang untuk pergerakan dalam horizon tersebut
- SahamApp akan otomatis merekam apakah prediksi benar atau salah

### Cara Baca Trade Plan di UI

Pada halaman detail saham, scroll ke bagian **"Trade Plan"**:

```
┌──────────────────────────────────────┐
│  🛡️ Stop Loss    Rp 9.850            │
│  🎯 Take Profit  Rp 11.050           │
│  ⚖️ Risk/Reward  1 : 2.0             │
│  📅 Horizon      7 hari              │
└──────────────────────────────────────┘
```

**Aturan pakai:**
1. Beli di harga pasar (atau pakai limit di harga yang lebih baik)
2. Pasang SL di harga SL — **JANGAN geser ke bawah**
3. Pasang TP di harga TP
4. Evaluasi di hari ke-7, atau lebih cepat jika target tercapai

---

## Watchlist (Saham Favorit)

Watchlist adalah daftar saham yang Anda pantau. Tersimpan **offline** di `localStorage` browser, tidak perlu login untuk disimpan.

### Cara Tambah ke Watchlist

1. Buka halaman **Market** atau **Sinyal**
2. Tap ikon ⭐ di pojok kanan atas kartu saham
3. Bintang akan berubah menjadi ⭐ terisi
4. Saham masuk watchlist

### Cara Lihat Watchlist

1. Tap ikon **Watchlist** (ikon bookmark) di header, atau
2. Buka menu filter, pilih "Watchlist"

### Cara Hapus dari Watchlist

Tap ikon ⭐ lagi — bintang akan kembali kosong, saham keluar watchlist.

### Sinkronisasi

Watchlist **tidak sinkron** antar device. Jika Anda login di HP lain, watchlist mulai kosong. (Roadmap: sinkronisasi via API.)

---

## Portofolio Virtual

Fitur ini memungkinkan Anda **simulasi trading** tanpa uang sungguhan. Cocok untuk:
- Belajar tracking P/L
- Menguji strategi
- Latihan disiplin SL/TP

> ⚠️ Portofolio SahamApp adalah **SIMULASI**, bukan transaksi real. Tidak ada hubungannya dengan broker mana pun.

### Cara Tambah Posisi

1. Buka tab **Portofolio** (💼)
2. Tap tombol **"+ Tambah Posisi"**
3. Isi form:
   - **Simbol**: kode saham (mis. `BBCA`)
   - **Quantity (qty)**: jumlah lembar
   - **Harga Rata-rata (avg_price)**: harga beli
   - **Target Price** (opsional): harga target jual
   - **Stop Loss** (opsional): harga cut loss
   - **Catatan** (opsional): alasan entry
4. Tap **Simpan**

### Lihat Ringkasan

Halaman Portofolio menampilkan:
- **Total Cost** — total modal keluar
- **Total Value** — nilai saat ini (mark-to-market)
- **Total P/L** — untung/rugi absolut
- **Total P/L %** — untung/rugi persen
- **Win Rate** — % posisi yang profit
- **Lose Rate** — % posisi yang loss

### Update Posisi

Tap posisi yang ingin diedit → ubah field → Simpan. Sistem otomatis recalculate P/L.

### Hapus Posisi

Tap ikon 🗑️ di samping posisi. Posisi hilang dari portofolio (tidak di-undo).

### Multi-User Isolation

Setiap user punya portofolio sendiri. User A tidak bisa lihat portofolio user B.

---

## News (Berita & Sentimen)

Tab **📰 Berita** menampilkan berita terkini dari Google News + analisa sentimen.

### Pilih Saham

1. Buka tab **Berita**
2. Tap dropdown **"Pilih Saham"**
3. Pilih dari daftar (BBCA, BBRI, dll) atau lihat default top 5

### Baca Sentimen

Setiap berita punya label sentimen:

| Label | Icon | Arti |
|-------|------|------|
| **POSITIF** | 😊 | Berita bernada positif — bisa menjadi katalis naik |
| **NETRAL** | 😐 | Berita informasional, tidak ada bias kuat |
| **NEGATIF** | 😟 | Berita bernada negatif — waspadai tekanan jual |

### Skor Sentimen

Selain label, ada **sentiment score** dari -10 sampai +10:
- `+10` = sangat positif
- `0` = netral
- `-10` = sangat negatif

### Metode Analisa

SahamApp pakai **hybrid NLP**:
- **VADER** (Valence Aware Dictionary and sEntiment Reasoner) untuk teks Inggris/campuran
- **Indonesian Lexicon** (kamus kata positif/negatif) untuk teks Indonesia
- **Confidence score** menunjukkan keyakinan model (0–1)

### Dampak ke Sinyal

Sentimen memberi **bias** ke sinyal keseluruhan:
- Sentimen positif kuat → sinyal BUY sedikit di-boost
- Sentimen negatif kuat → sinyal BUY/SELL bisa diturunkan

---

## Learning (Evaluasi Akurasi)

Tab **📚 Belajar** adalah **"mesin evaluasi"** SahamApp — menunjukkan seberapa akurat sinyal historis.

### Bagaimana Cara Kerjanya?

1. Setiap kali saham muncul di detail, **rekomendasi dicatat** ke database
2. Setelah **7 hari**, sistem otomatis mengevaluasi: apakah prediksi benar?
3. Hasil: `correct` / `wrong` + `return_pct`
4. Akurasi agregat ditampilkan di tab ini

### Aturan Evaluasi

| Sinyal Awal | Benar Jika |
|-------------|-----------|
| **BUY** | return 7 hari > 0% |
| **SELL** | return 7 hari < 0% |
| **HOLD** | return 7 hari di antara -5% dan +5% |

### Baca Statistik

- **Total Records** — jumlah rekomendasi yang pernah dicatat
- **Pending Evaluation** — yang belum 7 hari (menunggu)
- **Evaluated** — yang sudah selesai dievaluasi
- **Accuracy** — % yang benar (overall)
- **By Signal** — breakdown per tipe sinyal (BUY, SELL, HOLD)

### Trigger Evaluasi Manual

Tap tombol **"Evaluasi Sekarang"** untuk trigger batch evaluasi. Normalnya sistem auto-evaluate, tapi tombol ini berguna untuk testing atau setelah import data.

### Confidence & Trust

Gunakan tab ini untuk memutuskan:
- Berapa persen akurasi BUY dalam 3 bulan terakhir?
- Apakah SELL lebih akurat dari BUY untuk saham tertentu?
- Apakah model makin baik seiring waktu (cek accuracy over time)?

> Akurasi > 60% dianggap **bagus** untuk sinyal saham. Target SahamApp: **≥ 65%** di berbagai market regime.

---

## Signal Dashboard

Akses via tap tombol **"Akurasi"** di header atau navigasi ke `/accuracy`. Dashboard ini lebih visual dari tab Learning, cocok untuk cek performa keseluruhan.

### Komponen Dashboard

1. **Win Rate per Signal** — pie/bar chart
2. **Accuracy Over Time** — line chart 6–12 bulan
3. **Confusion Matrix** — heatmap (BUY/SELL vs actual outcome)
4. **Performance Metrics** — avg return, max drawdown, Sharpe ratio
5. **A/B Test** — perbandingan dua versi model

### Sharpe Ratio

Ukuran risk-adjusted return:
- `> 1.0` = bagus
- `> 2.0` = sangat bagus
- `< 0` = rugi

### Max Drawdown

Persentase kerugian terbesar dari puncak. Makin kecil (mendekati 0), makin aman modelnya.

---

## Daily Report

Tab **📋 Laporan** (jika diaktifkan oleh admin) menampilkan ringkasan harian:

- **Top 5 BUY** — 5 saham dengan sinyal beli terkuat hari ini
- **Top 5 SELL** — 5 saham dengan sinyal jual/sell terkuat
- **Portfolio Summary** — performa portofolio Anda

Aturan pakai:
- Cek tiap pagi sebelum jam buka bursa (09:00 WIB)
- Sinyal BUY punya target TP/SL 7 hari
- Sinyal dievaluasi 7 hari kemudian (lihat tab Learning)

---

## FAQ

### 1. Apakah SahamApp menjamin profit?

**TIDAK.** Tidak ada aplikasi, broker, atau analis yang bisa menjamin profit. Sinyal SahamApp adalah **alat bantu**, bukan nasihat investasi. Selalu DYOR (Do Your Own Research).

### 2. Kenapa data saham tertunda 15 menit?

Data harga bersumber dari Yahoo Finance (yfinance). Untuk pasar US & beberapa pasar lain, real-time mungkin tersedia. Untuk IDX, biasanya delay 15 menit sesuai regulasi Bursa Efek Indonesia.

### 3. Berapa akurat sinyalnya?

Lihat tab **Learning** untuk data akurasi historis. Target kami ≥ 65%. Performa bisa bervariasi tergantung market regime.

### 4. Bisa dipakai untuk trading saham US / crypto / forex?

**Tidak.** SahamApp khusus untuk **IDX** (Bursa Efek Indonesia) — 140+ emiten. Untuk pasar lain, gunakan tool yang sesuai.

### 5. Apakah data saya aman?

- Multi-user: setiap user punya data terisolasi
- Auth: HMAC-signed token, 30 hari TTL
- Rate limit: 200 req/menit per IP
- Security headers: X-Frame-Options, X-Content-Type-Options, dll
- HTTPS wajib di production

Lihat **[SECURITY.md](SECURITY.md)** untuk detail.

### 6. Kenapa login gagal padahal password benar?

Cek:
- Username di-lowercase oleh sistem — coba `Admin` → `admin`
- Caps lock off
- Token expired (30 hari) → login ulang
- Coba clear localStorage browser

### 7. Kenapa sinyal sama dengan kemarin?

Sinyal tidak berubah drastic setiap hari. Pergerakan harga kecil tidak cukup untuk flip BUY → SELL. Refresh pagi (09:00) dan siang (12:00) biasanya cukup.

### 8. Bisa tambah saham custom?

Tidak via UI. Saham yang muncul terbatas pada **universe 140+ saham IDX** yang sudah dikurasi. Lihat `backend/stock_data.py` untuk list lengkap.

### 9. Bagaimana cara hapus akun?

Akun hanya bisa dibuat/dihapus oleh **superadmin** via API. Hubungi admin aplikasi Anda.

### 10. Apakah ada API untuk developer?

Ya! Lihat **[backend/docs/API.md](backend/docs/API.md)** untuk dokumentasi lengkap. Endpoint public (tidak perlu auth) sudah cukup untuk eksperimen.

### 11. Kenapa beberapa saham tidak muncul di hasil search?

Kemungkinan:
- Saham tidak dalam universe tracking (cek `INDONESIAN_STOCKS` di `stock_data.py`)
- yfinance tidak punya data (mis. saham delisted/suspended)
- Saham tidak likuid (avg volume < 500,000)

### 12. Bisa pakai di HP dan desktop bersamaan?

Bisa. Login di device manapun. Watchlist **tidak** sinkron (masih per-browser). Portofolio & learning **sinkron** via server (per akun).

### 13. Bagaimana cara kontribusi / request fitur?

Buka **issue** di GitHub repo. Untuk kontribusi kode, lihat **[CONTRIBUTING.md](CONTRIBUTING.md)**.

### 14. Aplikasi ini gratis?

Ya, **open source** (MIT License). Anda bisa self-host atau kontribusi.

---

## Disclaimer

> ⚠️ **PENTING — BACA SEBELUM MENGGUNAKAN**
>
> 1. SahamApp adalah **alat bantu analisis**, BUKAN saran investasi.
> 2. Sinyal yang dihasilkan oleh model machine learning TIDAK menjamin profit di masa depan.
> 3. Performa di masa lalu TIDAK mencerminkan hasil masa depan.
> 4. Keputusan investasi 100% menjadi tanggung jawab pengguna.
> 5. Selalu **DYOR (Do Your Own Research)** dan konsultasikan dengan **penasihat keuangan profesional** untuk keputusan besar.
> 6. Data harga bersumber dari Yahoo Finance — mungkin tertunda atau tidak akurat.
> 7. Fitur portofolio adalah **SIMULASI** — tidak ada transaksi real, tidak ada uang sungguhan.
> 8. Developer tidak bertanggung jawab atas kerugian finansial yang timbul dari penggunaan aplikasi ini.
>
> **Dengan menggunakan SahamApp, Anda menyetujui disclaimer ini.**

---

## Butuh Bantuan Lebih?

- 📖 API docs: [backend/docs/API.md](backend/docs/API.md)
- 🔬 Metodologi: [METHODOLOGY.md](METHODOLOGY.md)
- 🏗️ Arsitektur: [ARCHITECTURE.md](ARCHITECTURE.md)
- 🐛 Issue / bug: GitHub Issues
- 🔒 Security issue: [SECURITY.md](SECURITY.md)

---

<p align="center">Selamat berinvestasi dengan cerdas! 📈</p>
<p align="center">— Tim SahamApp</p>
