# Contributing to SahamApp

Thank you for your interest in contributing to SahamApp! This guide outlines the contribution workflow.

## Code of Conduct

Be respectful, constructive, and inclusive. Harassment, trolling, and personal attacks will not be tolerated.

## How to Contribute

### 1. Reporting Bugs

Open a GitHub issue with:
- Clear title + description
- Steps to reproduce
- Expected vs actual behavior
- Browser/Node/Python versions
- Console errors (if any)

### 2. Suggesting Features

Open a GitHub issue tagged `enhancement`. Describe:
- The problem you're solving
- Proposed solution
- Alternative approaches considered

### 3. Pull Requests

**Process:**
1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make changes
4. Run tests / verify manually
5. Commit with clear messages (conventional commits preferred)
6. Push and open a PR against `main`
7. Keep PRs focused — one feature/fix per PR

**Before submitting:**
- Backend: `pip install -r requirements.txt` still works
- Frontend: `cd frontend && npm install && npm run build` passes
- No new warnings in console
- Existing behavior unchanged unless intentional

### 4. Development Setup

See [README.md](README.md#quick-start) for detailed setup instructions.

Quick recap:

```bash
# Backend
cd backend
pip install -r requirements.txt
python run.py        # starts on :8767

# Frontend (separate terminal)
cd frontend
npm install
npm run dev          # starts on :5180, proxies /api → :8767
```

**Electron:** `npm run electron` (requires backend running on port 8774, or set `VITE_DEV_SERVER_URL`)

**Database:** Default SQLite (`backend/signals.db`). For PostgreSQL, set `POSTGRES_URL` env var and run `setup_neon.sql` to create tables.

### 5. Code Style

**Python:**
- Follow PEP 8
- Type hints required for public functions
- Logging, not print statements
- Keep endpoint handlers thin — business logic in dedicated functions

**JavaScript/React:**
- ES modules (import/export)
- Functional components with hooks
- CSS in `index.css` (no CSS modules or Tailwind for now)
- Keep API calls in `api.js`

### 6. Testing

Manual testing for now:
- Verify `/api/stocks` returns 200 with stock data
- Verify detail page loads for symbols like BBCA, BBRI
- Check that login/portfolio flow works end-to-end
- Run `npm run lint` before committing frontend changes

Automated tests are not yet in place — contributions adding test infrastructure are very welcome.

### 7. Project Structure

```
backend/main.py        — All FastAPI routes, auth, DB logic
backend/stock_data.py  — yfinance scanner, cache, stock universe
backend/analysis.py    — Technical + fundamental signal generators
frontend/src/App.jsx   — Main app with all panels
frontend/src/api.js    — API client wrapper
api/index.py           — Vercel entry (Mangum wrapper)
```

### 8. Adding a New Stock to the Scanner

Add the symbol (with `.JK` suffix) to the `INDONESIAN_STOCKS` list in `backend/stock_data.py`. Add its sector mapping to `SECTOR_MAP` in the same file.

---

**Questions?** Open a discussion or issue. We're happy to help.
