const isElectronLocal = window.location.protocol === 'file:'
  || (window.location.hostname === '127.0.0.1' && window.location.port === '4179');
const BASE_URL = isElectronLocal ? 'http://127.0.0.1:8774/api' : '/api';

// Active request controllers — used to abort all pending requests on tab change
const pendingControllers = new Set();

let _refreshing = null; // singleton refresh promise

export function abortAllRequests() {
  for (const c of pendingControllers) {
    c.abort();
  }
  pendingControllers.clear();
}

function authHeaders(extra = {}) {
  const token = localStorage.getItem('saham_auth_token');
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function refreshAuthToken() {
  const refreshToken = localStorage.getItem('saham_refresh_token');
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      localStorage.removeItem('saham_auth_token');
      localStorage.removeItem('saham_refresh_token');
      return false;
    }
    const data = await res.json();
    localStorage.setItem('saham_auth_token', data.token || data.access_token);
    return true;
  } catch {
    localStorage.removeItem('saham_auth_token');
    localStorage.removeItem('saham_refresh_token');
    return false;
  }
}

async function fetchJson(url, options = {}, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // Combine external signal from options with internal timeout signal.
  // AbortSignal.any() requires Chrome 116+/FF 124+/Safari 17.4+; on older
  // mobile WebViews it is undefined and would throw. Fall back to whichever
  // signal is provided (best effort — internal timeout will still fire via
  // the AbortController if the external signal is absent).
  const signal = options.signal
    ? (typeof AbortSignal.any === 'function'
        ? AbortSignal.any([controller.signal, options.signal])
        : options.signal)
    : controller.signal;

  // Extract signal from options so fetch doesn't get two signals
  // eslint-disable-next-line no-unused-vars
  const { signal: _, ...fetchOptions } = options;

  pendingControllers.add(controller);
  try {
    const res = await fetch(url, { ...fetchOptions, signal });
    if (res.status === 401 && !url.includes('/auth/login') && !url.includes('/auth/refresh')) {
      // Auto-refresh on 401
      if (!_refreshing) {
        _refreshing = refreshAuthToken().finally(() => { _refreshing = null; });
      }
      const refreshed = await _refreshing;
      if (refreshed) {
        // Retry with new token
        const newOpts = { ...fetchOptions, headers: authHeaders(fetchOptions.headers || {}) };
        const res2 = await fetch(url, { ...newOpts, signal });
        if (!res2.ok) {
          const text = await res2.text();
          throw new Error(`HTTP ${res2.status}: ${text}`);
        }
        return res2.json();
      }
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
  } finally {
    clearTimeout(timer);
    pendingControllers.delete(controller);
  }
}

// ============================================================
// Cache layer — TTL per key, request deduplication, stale-while-revalidate
// ============================================================
const TTL = {
  stock: 15_000,      // 15s — data saham (perubahan harga sering)
  market: 30_000,     // 30s — ringkasan pasar / live
  portfolio: 60_000,  // 60s — portofolio
  report: 60_000,     // 60s — laporan harian
  news: 300_000,      // 300s — berita
  search: 5_000,      // 5s — pencarian singkat
  learning: 30_000,   // 30s — ringkasan pembelajaran
  accuracy: 60_000,  // 60s — akurasi sinyal & backtest
};

class ApiCache {
  constructor() {
    // key -> { data, timestamp, promise }
    this._store = new Map();
  }

  /**
   * Ambil data dari cache atau fetch. Mendukung:
   *  - TTL per key
   *  - Request deduplication (in-flight promise dishare ke semua caller)
   *  - Stale-while-revalidate (data basi dikembalikan dulu, refresh di background)
   */
  async getOrFetch(key, fetchFn, ttl = TTL.stock) {
    const now = Date.now();
    const entry = this._store.get(key);

    // 1) Cache valid — kembalikan langsung
    if (entry && entry.data != null && (now - entry.timestamp) < ttl) {
      return entry.data;
    }

    // 2) Fetch sedang berjalan — dedup, tunggu promise yang sama
    if (entry && entry.promise) {
      return entry.promise;
    }

    // 3) Data basi ada — serve stale, refresh di background (SWR)
    if (entry && entry.data != null) {
      const stale = entry.data;
      const bgPromise = Promise.resolve()
        .then(() => fetchFn())
        .then((data) => {
          this._store.set(key, { data, timestamp: Date.now(), promise: null });
          return data;
        })
        .catch((err) => {
          // Background gagal — pertahankan data basi, bersihkan promise
          const cur = this._store.get(key);
          if (cur) this._store.set(key, { ...cur, promise: null });
          console.warn(`[ApiCache] background refresh gagal untuk ${key}:`, err?.message || err);
        });
      this._store.set(key, { ...entry, promise: bgPromise });
      return stale;
    }

    // 4) Belum ada data — fresh fetch
    const promise = Promise.resolve()
      .then(() => fetchFn())
      .then((data) => {
        this._store.set(key, { data, timestamp: Date.now(), promise: null });
        return data;
      })
      .catch((err) => {
        // Gagal total — hapus entry supaya caller berikutnya bisa coba lagi
        this._store.delete(key);
        throw err;
      });
    this._store.set(key, { data: null, timestamp: 0, promise });
    return promise;
  }

  invalidate(key) {
    this._store.delete(key);
  }

  // Invalidasi semua cache yang berawalan prefix (untuk operasi tulis)
  invalidatePrefix(prefix) {
    for (const k of this._store.keys()) {
      if (k.startsWith(prefix)) this._store.delete(k);
    }
  }

  clear() {
    this._store.clear();
  }
}

const apiCache = new ApiCache();

// Helper: bangun cache key yang aman dan ter-baca
const k = (...parts) => parts.filter(Boolean).join(':');

// ============================================================
// Auth (tidak di-cache, mutasi / state sensitif)
// ============================================================
export async function login(username, password, signal) {
  const data = await fetchJson(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    signal,
  }, 8000);
  // Store tokens
  if (data.token) localStorage.setItem('saham_auth_token', data.token);
  if (data.refresh_token) localStorage.setItem('saham_refresh_token', data.refresh_token);
  return data;
}

export async function fetchMe(signal) {
  return fetchJson(`${BASE_URL}/auth/me`, { headers: authHeaders(), signal }, 8000);
}

export async function fetchUsers(signal) {
  return fetchJson(`${BASE_URL}/admin/users`, { headers: authHeaders(), signal }, 8000);
}

export async function createUser(user, signal) {
  return fetchJson(`${BASE_URL}/admin/users`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(user),
    signal,
  }, 8000);
}

// ============================================================
// Stocks — TTL 15s
// ============================================================
export function fetchStocks(all = false, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  const key = k('stocks', all ? 'all' : 'top');
  return apiCache.getOrFetch(key, () => {
    const params = all ? '?all=true' : '';
    return fetchJson(`${BASE_URL}/stocks${params}`, {}, all ? 12000 : 6500);
  }, TTL.stock);
}

export function fetchTopStocks(signal) {
  return fetchStocks(false, signal);
}

export function fetchAllStocks(signal) {
  return fetchStocks(true, signal);
}

export function searchStocks(q, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  const query = (q || '').trim();
  if (!query) return Promise.resolve({ data: [] });
  const key = k('search', query.toLowerCase());
  return apiCache.getOrFetch(key, () =>
    fetchJson(`${BASE_URL}/stocks/search?q=${encodeURIComponent(query)}`, {}, 12000),
  TTL.search);
}

export function fetchBatchStocks(symbols, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  const list = (symbols || []).slice().sort().join(',');
  const key = k('batch', list);
  return apiCache.getOrFetch(key, () => {
    const params = list ? `?symbols=${encodeURIComponent(list)}` : '';
    return fetchJson(`${BASE_URL}/stocks/batch${params}`, {}, 12000);
  }, TTL.stock);
}

export function fetchStockDetail(symbol, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  const key = k('detail', symbol);
  return apiCache.getOrFetch(key, () =>
    fetchJson(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}`, {}, 15000),
  TTL.stock);
}

export function fetchStockHistory(symbol, period = '1M', signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  const key = k('history', symbol, period);
  return apiCache.getOrFetch(key, () =>
    fetchJson(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}/history?period=${encodeURIComponent(period)}`, {}, 12000),
  TTL.stock);
}

export function fetchStockRecommendationHistory(symbol, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  const key = k('reco', symbol);
  return apiCache.getOrFetch(key, () =>
    fetchJson(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}/recommendation-history`, {}, 12000),
  TTL.stock);
}

// ============================================================
// Market — TTL 30s
// ============================================================
export function fetchMarketSummary(signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return apiCache.getOrFetch('market-summary', () =>
    fetchJson(`${BASE_URL}/market-summary`, {}, 5000),
  TTL.market);
}

export function fetchLiveSummary(signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return apiCache.getOrFetch('live-summary', () =>
    fetchJson(`${BASE_URL}/live/summary`, {}, 8000),
  TTL.market);
}

// ============================================================
// Learning — TTL 30s untuk summary, tanpa cache untuk evaluate
// ============================================================
export function fetchLearningSummary(signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return apiCache.getOrFetch('learning-summary', () =>
    fetchJson(`${BASE_URL}/learning/summary`, {}, 8000),
  TTL.learning);
}

export async function evaluateLearning(limit = 50, signal) {
  // Mutasi — bypass cache
  return fetchJson(`${BASE_URL}/learning/evaluate?limit=${encodeURIComponent(limit)}`, {
    method: 'POST',
    signal,
  }, 20000);
}

// ============================================================
// Accuracy / Backtest — TTL 60s
// ============================================================
export function fetchAccuracy(signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return apiCache.getOrFetch('accuracy', () =>
    fetchJson(`${BASE_URL}/accuracy`, { headers: authHeaders() }, 12000),
  TTL.accuracy);
}

export function fetchAccuracySummary(signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return apiCache.getOrFetch('accuracy-summary', () =>
    fetchJson(`${BASE_URL}/accuracy/summary`, { headers: authHeaders() }, 12000),
  TTL.accuracy);
}

// ============================================================
// Portfolio — TTL 60s, invalidasi saat ada perubahan
// ============================================================
export function fetchPortfolio(signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return apiCache.getOrFetch('portfolio', () =>
    fetchJson(`${BASE_URL}/portfolio`, { headers: authHeaders() }, 12000),
  TTL.portfolio);
}

export async function savePortfolioPosition(position, signal) {
  const res = await fetchJson(`${BASE_URL}/portfolio`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(position),
    signal,
  }, 12000);
  apiCache.invalidate('portfolio');
  return res;
}

export async function deletePortfolioPosition(symbol, signal) {
  const res = await fetchJson(`${BASE_URL}/portfolio/${encodeURIComponent(symbol)}`, {
    method: 'DELETE',
    headers: authHeaders(),
    signal,
  }, 12000);
  apiCache.invalidate('portfolio');
  return res;
}

// ============================================================
// Report — TTL 60s
// ============================================================
export function fetchDailyReport(signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return apiCache.getOrFetch('daily-report', () =>
    fetchJson(`${BASE_URL}/report/daily`, { headers: authHeaders() }, 18000),
  TTL.report);
}

// ============================================================
// News — TTL 300s
// ============================================================
export function fetchNews(symbol = '', limit = 8, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  const key = k('news', symbol || 'all', limit);
  return apiCache.getOrFetch(key, () => {
    const params = symbol
      ? `?symbol=${encodeURIComponent(symbol)}&limit=${encodeURIComponent(limit)}`
      : `?limit=${encodeURIComponent(limit)}`;
    return fetchJson(`${BASE_URL}/news${params}`, {}, 15000);
  }, TTL.news);
}

export function fetchStockNews(symbol, limit = 8, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  const key = k('stock-news', symbol, limit);
  return apiCache.getOrFetch(key, () =>
    fetchJson(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}/news?limit=${encodeURIComponent(limit)}`, {}, 15000),
  TTL.news);
}

// Expose cache helpers untuk kebutuhan debugging / invalidasi manual
export { apiCache };
