const CACHE = 'saham-id-v3';
const STATIC_CACHE = 'saham-id-static-v3';
const CORE = ['/', '/manifest.json'];

// Install: cache core assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(CORE))
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE && k !== STATIC_CACHE).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Determine strategy based on request type
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // API calls — network-first with fallback
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

  // Static assets (JS, CSS, images, fonts) — cache-first
  if (
    url.pathname.match(/\.(js|css|mjs|json|woff2?|ttf|otf|svg|png|jpg|jpeg|gif|webp|ico)$/i) ||
    url.pathname.startsWith('/assets/')
  ) {
    event.respondWith(cacheFirst(req, STATIC_CACHE));
    return;
  }

  // Everything else — network-first with cache fallback
  event.respondWith(networkFirst(req, CACHE));
});

// Cache-first strategy: serve from cache, fall back to network
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

// Network-first strategy: try network, fall back to cache
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
    // API offline response
    if (req.url.includes('/api/')) {
      return new Response(JSON.stringify({ error: 'offline' }), {
        headers: { 'Content-Type': 'application/json' },
        status: 503,
      });
    }
    return caches.match('/');
  }
}
