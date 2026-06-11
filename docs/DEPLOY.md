# 🚀 Deployment Guide

> Deploy SahamApp ke Vercel (frontend) + Railway/Fly (backend) + Neon (Postgres) + Upstash (Redis)

---

## 📋 Prerequisites

- Akun [Vercel](https://vercel.com)
- Akun [Neon](https://neon.tech) (Postgres)
- Akun [Upstash](https://upstash.com) (Redis)
- Akun [GitHub](https://github.com)
- Node 18+, Python 3.11+
- Repo sudah di-push ke GitHub

---

## 🎯 Arsitektur Production

```
┌──────────────────┐
│  Vercel CDN      │
│  (Frontend SPA)  │  https://saham-app.com
└────────┬─────────┘
         │
         │ HTTPS
         ▼
┌──────────────────┐
│  Backend (Fly)   │  https://api.saham-app.com
└────┬──────┬──────┘
     │      │
     │      └──────────┐
     ▼                 ▼
┌─────────┐       ┌──────────┐
│  Neon   │       │ Upstash  │
│ Postgres│       │  Redis   │
└─────────┘       └──────────┘
```

---

## 1️⃣ Setup Neon Postgres

1. Buka https://console.neon.tech
2. **Create project** → pilih region Singapore (dekat ID)
3. Copy **Connection string** → `postgresql://user:pass@ep-xxx.neon.tech/saham?sslmode=require`
4. Save sebagai `DATABASE_URL` di Vercel/Fly

**Schema migration** (auto di app startup):
- Tables: `app_users`, `signal_recommendations`, `portfolio_positions`, dll.
- Lihat `backend/services/migration.py` untuk detail

---

## 2️⃣ Setup Upstash Redis

1. Buka https://console.upstash.com
2. **Create database** → region Singapore
3. Copy **Redis URL** → `rediss://default:xxx@apn1-xxx.upstash.io:6379`
4. Save sebagai `REDIS_URL`

**Free tier**: 10K commands/day, 256MB. Cukup untuk 100 user.

---

## 3️⃣ Deploy Backend ke Fly.io

### Setup Awal

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth signup  # atau fly auth login
```

### Persiapan Repo

Pastikan `backend/Dockerfile` ada:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8774

CMD ["python", "main.py"]
```

### Deploy

```bash
cd backend

# Init (pertama kali)
fly launch --name saham-api --region sin

# Set env
fly secrets set \
  DATABASE_URL="postgresql://..." \
  REDIS_URL="rediss://..." \
  SAHAM_AUTH_SECRET="$(openssl rand -hex 32)" \
  SAHAM_CORS_ORIGINS="https://saham-app.com,https://www.saham-app.com" \
  SENTRY_DSN="https://...@sentry.io/..." \
  ENVIRONMENT=production

# Deploy
fly deploy

# Cek status
fly status
fly logs
```

### Custom Domain (optional)

```bash
fly certs create api.saham-app.com
# Tambah CNAME di DNS provider:
# api.saham-app.com → saham-api.fly.dev
```

---

## 4️⃣ Deploy Frontend ke Vercel

### Setup Awal

1. Buka https://vercel.com/new
2. **Import Git Repository** → pilih repo
3. **Configure**:
   - Framework Preset: **Vite**
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`

### Environment Variables

Tambah di Vercel dashboard:

```
VITE_API_URL=https://api.saham-app.com
VITE_SENTRY_DSN=https://...@sentry.io/...
VITE_APP_VERSION=2.0.0
```

### Deploy

```bash
cd frontend

# Install Vercel CLI (optional)
npm i -g vercel

# Login
vercel login

# Deploy preview
vercel

# Deploy production
vercel --prod
```

### Custom Domain

Di Vercel dashboard:
1. Settings → Domains
2. Add `saham-app.com` + `www.saham-app.com`
3. Ikuti instruksi DNS

---

## 5️⃣ DNS Setup

Di DNS provider (Cloudflare / Namecheap / dll):

```
Type   Name    Value                       TTL
A      @       76.76.21.21                 Auto  (Vercel)
CNAME  www     cname.vercel-dns.com         Auto
CNAME  api     saham-api.fly.dev            Auto
```

---

## 6️⃣ Post-Deployment Checklist

- [ ] Test `https://api.saham-app.com/api/health` → 200 OK
- [ ] Test `https://saham-app.com` → load tanpa error
- [ ] Login admin → `https://saham-app.com/login`
- [ ] Cek 3-5 saham muncul di list
- [ ] Klik saham → detail + chart muncul
- [ ] Tambah portfolio position
- [ ] Lihat news
- [ ] Lihat accuracy dashboard
- [ ] Cek Lighthouse di Chrome DevTools
- [ ] Cek console browser tidak ada error
- [ ] Test dari mobile (responsive)

---

## 7️⃣ Monitoring

### Sentry (recommended)

Frontend + backend sudah punya Sentry init (gated on `SENTRY_DSN` env).

1. Buat project di https://sentry.io
2. Copy DSN → set sebagai `SENTRY_DSN` (backend) dan `VITE_SENTRY_DSN` (frontend)
3. Auto-capture unhandled errors + slow queries

### Fly.io Logs

```bash
fly logs
# atau real-time:
fly logs -f
```

### Vercel Analytics

Vercel dashboard → Analytics tab:
- Page views
- Web Vitals (LCP, FID, CLS)
- Top pages
- Errors

---

## 8️⃣ CI/CD

### Backend (Fly.io)

Auto-deploy on push ke `main`:
```bash
# .github/workflows/backend.yml
name: Deploy Backend
on:
  push:
    branches: [main]
    paths: ['backend/**']
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

### Frontend (Vercel)

Auto-deploy on push ke `main` (Vercel Git integration).

Preview deployments untuk setiap PR.

---

## 9️⃣ Backup & Recovery

### Neon Postgres

Auto-backup: 7 days retention (free tier). 
Manual backup:
```bash
# Install pg_dump (PostgreSQL client)
# Dump
pg_dump $DATABASE_URL > backup_$(date +%F).sql

# Restore
psql $DATABASE_URL < backup_2026-06-11.sql
```

### Upstash Redis

Redis optional cache. Jika hilang, app tetap jalan (fallback ke fakeredis in-memory).

---

## 🔟 Scaling

### Horizontal (multiple instances)

Backend: `fly scale count 3` (3 instances)
- Background worker harus disable di 2 dari 3 (pakai env `RUN_WORKER=false` di 2 instances)
- Atau pakai dedicated worker machine

### Vertical (bigger machine)

```bash
fly scale vm shared-cpu-2x
fly scale memory 1024
```

### Database

Neon auto-scales compute based on load. Bisa set max via dashboard.

---

## 🆘 Troubleshooting

### Backend tidak start

```bash
fly logs --error
# Cek env vars
fly secrets list
```

### Frontend blank screen

1. Buka DevTools → Console
2. Cek error
3. Biasanya CORS issue → cek `SAHAM_CORS_ORIGINS` di backend

### yfinance rate-limited

Tambah delay:
```python
# backend/stock_data.py
import time
time.sleep(0.5)  # antar request
```

Atau switch ke paid provider (Polygon, Alpha Vantage).

### DB connection error

Cek `DATABASE_URL`:
- Neon: harus include `?sslmode=require`
- Format: `postgresql://user:pass@host/db?sslmode=require`

---

## 📊 Cost Estimation (1000 users)

| Service | Tier | Cost |
|---------|------|------|
| Vercel | Hobby | $0 |
| Fly.io | Free → $5/mo | $5 |
| Neon | Free → Launch ($19/mo) | $0-19 |
| Upstash | Free (10K cmd/day) | $0 |
| Sentry | Free (5K events/mo) | $0 |
| Domain | Annual | $12/year |
| **Total** | | **~$25/mo** |

---

_Last updated: 2026-06-11_
