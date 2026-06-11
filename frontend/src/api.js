const BASE_URL = '/api';

async function handleResponse(res) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export async function fetchStocks(all = false) {
  const params = all ? '?all=true' : '';
  const res = await fetch(`${BASE_URL}/stocks${params}`);
  return handleResponse(res);
}

export async function fetchTopStocks() {
  const res = await fetch(`${BASE_URL}/stocks`);
  return handleResponse(res);
}

export async function fetchAllStocks() {
  const res = await fetch(`${BASE_URL}/stocks?all=true`);
  return handleResponse(res);
}

export async function searchStocks(q) {
  const res = await fetch(`${BASE_URL}/stocks/search?q=${encodeURIComponent(q)}`);
  return handleResponse(res);
}

export async function fetchBatchStocks(symbols) {
  const params = symbols ? `?symbols=${encodeURIComponent(symbols.join(','))}` : '';
  const res = await fetch(`${BASE_URL}/stocks/batch${params}`);
  return handleResponse(res);
}

export async function fetchStockDetail(symbol) {
  const res = await fetch(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}`);
  return handleResponse(res);
}

export async function fetchStockHistory(symbol, period = '1M') {
  const res = await fetch(
    `${BASE_URL}/stocks/${encodeURIComponent(symbol)}/history?period=${encodeURIComponent(period)}`
  );
  return handleResponse(res);
}

export async function fetchStockRecommendationHistory(symbol) {
  const res = await fetch(`${BASE_URL}/stocks/${encodeURIComponent(symbol)}/recommendation-history`);
  return handleResponse(res);
}

export async function fetchMarketSummary() {
  const res = await fetch(`${BASE_URL}/market-summary`);
  return handleResponse(res);
}

export async function fetchLiveSummary() {
  const res = await fetch(`${BASE_URL}/live/summary`);
  return handleResponse(res);
}

export async function fetchLearningSummary() {
  const res = await fetch(`${BASE_URL}/learning/summary`);
  return handleResponse(res);
}

export async function evaluateLearning(limit = 50) {
  const res = await fetch(`${BASE_URL}/learning/evaluate?limit=${encodeURIComponent(limit)}`);
  return handleResponse(res);
}

export async function fetchPortfolio() {
  const res = await fetch(`${BASE_URL}/portfolio`);
  return handleResponse(res);
}

export async function savePortfolioPosition(position) {
  const res = await fetch(`${BASE_URL}/portfolio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(position),
  });
  return handleResponse(res);
}

export async function deletePortfolioPosition(symbol) {
  const res = await fetch(`${BASE_URL}/portfolio/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
  return handleResponse(res);
}

export async function fetchDailyReport() {
  const res = await fetch(`${BASE_URL}/report/daily`);
  return handleResponse(res);
}
