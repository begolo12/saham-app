/* Service worker — Saham ID PWA
 *
 * Strategies:
 *   /api/market-summary, /api/stocks (top 10) → stale-while-revalidate (instant)
 *   /api/* (other)                              → network-first (fresh)
 *   navigations, HTML                           → network-first (offline fallback)
 *   static assets                               → cache-first (long-lived)
 *   everything else                             → network-first
 */

const CACHE = 'saham-id-v4';
const STATIC_CACHE = 'saham-id-static-v4';
const CORE = ['/', '/manifest.json'];

// Endpoints where stale-while-revalidate gives the biggest perceived-speed win
const SWR_ENDPOINTS = new Set([
  '/api/market-summary',
  '/api/stocks',
]);

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(CORE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE && k !== STATIC_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never cache mutations
  const url = new URL(req.url);

  // Stale-while-revalidate for hot read-only endpoints
  if (url.pathname === '/api/market-summary' || url.pathname === '/api/stocks') {
    event.respondWith(staleWhileRevalidate(req, CACHE));
    return;
  }

  // Other API calls — network-first with cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(req, CACHE));
    return;
  }

  // Navigation & HTML — network-first with offline fallback
  if (req.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, clone));
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('/')))
    );
    return;
  }

  // Static assets — cache-first
  if (
    url.pathname.match(/\.(js|css|mjs|json|woff2?|ttf|otf|svg|png|jpg|jpeg|gif|webp|ico)$/i) ||
    url.pathname.startsWith('/assets/')
  ) {
    event.respondWith(cacheFirst(req, STATIC_CACHE));
    return;
  }

  event.respondWith(networkFirst(req, CACHE));
});

/* Cache-first: serve from cache, fall back to network */
async function cacheFirst(req, cacheName) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res.ok) {
      const clone = res.clone();
      caches.open(cacheName).then((cache) => cache.put(req, clone));
    }
    return res;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}

/* Network-first: try network, fall back to cache */
async function networkFirst(req, cacheName) {
  try {
    const res = await fetch(req);
    if (res.ok) {
      const clone = res.clone();
      caches.open(cacheName).then((cache) => cache.put(req, clone));
    }
    return res;
  } catch {
    const cached = await caches.match(req);
    if (cached) return cached;
    if (req.url.includes('/api/')) {
      return new Response(JSON.stringify({ error: 'offline' }), {
        headers: { 'Content-Type': 'application/json' },
        status: 503,
      });
    }
    return caches.match('/');
  }
}

/* Stale-while-revalidate: serve cached instantly, refresh in background */
async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);

  const networkFetch = fetch(req)
    .then((res) => {
      if (res && res.ok) {
        const clone = res.clone();
        cache.put(req, clone).catch(() => {});
      }
      return res;
    })
    .catch(() => null);

  // Return cached immediately if we have it; otherwise wait for network
  return cached || (await networkFetch) || new Response(
    JSON.stringify({ error: 'offline' }),
    { headers: { 'Content-Type': 'application/json' }, status: 503 }
  );
}
