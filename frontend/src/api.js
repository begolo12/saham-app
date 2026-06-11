const isElectronLocal = window.location.protocol === 'file:'
  || (window.location.hostname === '127.0.0.1' && window.location.port === '4179');
const BASE_URL = isElectronLocal ? 'http://127.0.0.1:8774/api' : '/api';

function authHeaders(extra = {}) {
  const token = localStorage.getItem('saham_auth_token');
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function fetchJson(url, options = {}, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function login(username, password) {
  return fetchJson(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  }, 8000);
}

export async function fetchMe() {
  return fetchJson(`${BASE_URL}/auth/me`, { headers: authHeaders() }, 8000);
}

export async function fetchUsers() {
  return fetchJson(`${BASE_URL}/admin/users`, { headers: authHeaders() }, 8000);
}

export async function createUser(user) {
  return fetchJson(`${BASE_URL}/admin/users`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(user),
  }, 8000);
}

export async function fetchStocks(all = false) {
  const params = all ? '?all=true' : '';
  return fetchJson(`${BASE_URL}/stocks${params}`, {}, all ? 12000 : 6500);
}

export async function fetchTopStocks() {
  return fetchJson(`${BASE_URL}/stocks`, {}, 6500);
}

export async function fetchAllStocks() {
  return fetchJson(`${BASE_URL}/stocks?all=true`, {}, 12000);
}

export async function searchStocks(q) {
  return fetchJson(`${BASE_URL}/stocks/search?q=${encodeURIComponent(q)}`, {}, 12000);
}

export async function fetchBatchStocks(symbols) {
  const params = symbols ? `?symbols=${encodeURIComponent(symbols.join(','))}` : '';
  return fetchJson(`${BASE_URL}/stocks/batch${params}`, {}, 12000);
}

export async function fetchStockDetail(symbol) {
  return fetchJson(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}`, {}, 15000);
}

export async function fetchStockHistory(symbol, period = '1M') {
  return fetchJson(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}/history?period=${encodeURIComponent(period)}`, {}, 12000);
}

export async function fetchStockRecommendationHistory(symbol) {
  return fetchJson(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}/recommendation-history`, {}, 12000);
}

export async function fetchMarketSummary() {
  return fetchJson(`${BASE_URL}/market-summary`, {}, 5000);
}

export async function fetchLiveSummary() {
  return fetchJson(`${BASE_URL}/live/summary`, {}, 8000);
}

export async function fetchLearningSummary() {
  return fetchJson(`${BASE_URL}/learning/summary`, {}, 8000);
}

export async function evaluateLearning(limit = 50) {
  return fetchJson(`${BASE_URL}/learning/evaluate?limit=${encodeURIComponent(limit)}`, {}, 20000);
}

export async function fetchPortfolio() {
  return fetchJson(`${BASE_URL}/portfolio`, { headers: authHeaders() }, 12000);
}

export async function savePortfolioPosition(position) {
  return fetchJson(`${BASE_URL}/portfolio`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(position),
  }, 12000);
}

export async function deletePortfolioPosition(symbol) {
  return fetchJson(`${BASE_URL}/portfolio/${encodeURIComponent(symbol)}`, { method: 'DELETE', headers: authHeaders() }, 12000);
}

export async function fetchDailyReport() {
  return fetchJson(`${BASE_URL}/report/daily`, { headers: authHeaders() }, 18000);
}
