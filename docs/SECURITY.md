# 🔒 Security Policy

> SahamApp Security Disclosure & Best Practices

---

## 🛡️ Supported Versions

| Version | Supported          |
|---------|--------------------|
| 2.0.x   | ✅ Active          |
| 1.x.x   | ⚠️ End-of-life (April 2026) |
| < 1.0   | ❌ Tidak didukung  |

Kami rilis patch keamanan untuk versi aktif. Update minor gratis.

---

## 📣 Reporting a Vulnerability

**JANGAN** tulis issue publik untuk kerentanan keamanan.

Email: **security@saham-app.com** (PGP key di bawah)

Include:
- Deskripsi kerentanan
- Langkah reproduksi (proof-of-concept)
- Dampak potensial
- Saran perbaikan (jika ada)

Kami respon dalam **48 jam** dan patch dalam **7 hari** untuk severity tinggi.

---

## 🏆 Bug Bounty (planned)

Belum ada program resmi. Coming soon dengan tier:

| Severity | Bounty (IDR) |
|----------|-------------|
| Critical | 5.000.000 |
| High     | 2.000.000 |
| Medium   | 500.000 |
| Low      | 100.000 |

---

## 🔐 Security Measures

### Authentication
- **JWT** custom (HMAC-SHA256, 15min access + 30day refresh)
- **bcrypt** password hashing (12 rounds)
- **SHA256 legacy fallback** untuk migrasi dari versi lama
- **Constant-time compare** untuk signature verification (timing-attack safe)

### Rate Limiting
- **Login**: 5 percobaan/menit per IP (HTTP 429 setelah itu)
- **General API**: 200 requests/menit per IP
- Bypass untuk admin dengan env flag

### Headers (Security)
Semua response include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HTTPS only)
- `Content-Security-Policy: default-src 'self'; ...`

### CORS
- Whitelist via env `SAHAM_CORS_ORIGINS`
- Wildcard (`*`) **tidak pernah** di production
- Credentials mode strict

### Input Sanitization
- Semua error message di-HTML-escape (anti-XSS)
- SQL queries 100% parameterized (no f-strings)
- Pydantic validation di semua request body
- File upload: belum ada (planned)

### Data Protection
- **At rest**: Neon Postgres encryption by default
- **In transit**: TLS 1.3 (Vercel + Fly.io)
- **Passwords**: bcrypt hashed, never logged
- **Tokens**: stored client-side in `localStorage` (consider httpOnly cookies for v3)
- **PII**: minimal collection, anonymized analytics

### Dependency Security
- Dependabot enabled (GitHub)
- `npm audit` di CI
- `pip-audit` di CI
- Auto-merge untuk patch updates

### Secret Management
- `.env` di-gitignore
- Secrets di Vercel/Fly env vars (encrypted at rest)
- No secrets di logs
- No secrets di error messages

---

## 🚨 Known Limitations

1. **JWT di localStorage**: vulnerable to XSS. Mitigated by CSP, but httpOnly cookies better.
2. **No 2FA**: planned v3.
3. **No account lockout**: hanya rate limit per IP, bukan per user.
4. **SQLite dev DB**: file-based, no network encryption.
5. **yfinance**: third-party, no SLA.

---

## 🧪 Security Testing

### Automated
- 247+ backend tests (pytest)
- 71+ frontend tests (vitest)
- Trivy container scan (CI)
- Bandit Python security linter (planned)

### Manual (planned)
- Annual penetration test
- OWASP Top 10 audit per release
- Dependency audit quarterly

---

## 📋 Compliance

- ✅ **GDPR**: minimal PII, right to deletion (planned)
- ✅ **UU PDP (Indonesia)**: data minimization, consent
- ⚠️ **PCI DSS**: N/A (no payments)
- ⚠️ **SOC 2**: planned for enterprise tier

---

## 🗝️ PGP Key (untuk security reports)

```
-----BEGIN PGP PUBLIC KEY BLOCK-----
[Placeholder - generate sebelum production launch]
-----END PGP PUBLIC KEY BLOCK-----
```

Fingerprint: `XXXX XXXX XXXX XXXX XXXX XXXX XXXX XXXX XXXX XXXX`

---

## 📞 Kontak

- Security issues: security@saham-app.com
- Privacy/data deletion: privacy@saham-app.com
- General: hello@saham-app.com

Response time: 48 jam (weekday), 72 jam (weekend)

---

## 📜 Changelog Security

### 2.0.0 (2026-06-11)
- ✅ bcrypt password hashing
- ✅ JWT refresh tokens
- ✅ Rate limit (5 login/min/IP)
- ✅ Security headers (HSTS, X-Frame, dll)
- ✅ CORS whitelist
- ✅ html.escape error messages
- ✅ Constant-time JWT compare
- ✅ parameterized SQL

### 1.0.0 (2025-12-01)
- Basic JWT auth
- SHA256 password hashing
- HTTPS only

---

_Last updated: 2026-06-11_
