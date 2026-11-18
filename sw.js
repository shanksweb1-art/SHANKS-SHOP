const CACHE_NAME = 'shanks-pos-v2';
const RUNTIME_CACHE = 'shanks-runtime-v2';
const CORE_ASSETS = [
  '/',
  '/login.html',
  '/index.html',
  '/dashboard.html',
  '/sales.html',
  '/inventory.html',
  '/customers.html',
  '/suppliers.html',
  '/reports.html',
  '/expenses.html',
  '/payments.html',
  '/receiving.html',
  '/invoices.html',
  '/receipt.html',
  '/config.html',
  '/employees.html',
  '/shifts.html',
  '/platform.html',
  '/tenants.html',
  '/admin.html',
  '/admin-setup.html',
  '/api.js',
  '/common.js',
  '/common.css',
  '/offline.js',
  '/brand-logo.png',
  '/apple-touch-icon.png',
  '/favicon.png',
  '/favicon.ico',
  '/manifest.webmanifest'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS.map((u) => new Request(u, { cache: 'reload' }))).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME && k !== RUNTIME_CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

function isApiRequest(url) {
  return url.pathname.startsWith('/api/');
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) {
    // Cache cross-origin assets (fonts/icons CDN) with stale-while-revalidate
    event.respondWith(
      caches.open(RUNTIME_CACHE).then((cache) =>
        cache.match(req).then((cached) => {
          const fetchPromise = fetch(req).then((res) => {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          }).catch(() => cached);
          return cached || fetchPromise;
        })
      )
    );
    return;
  }

  if (isApiRequest(url)) {
    event.respondWith(
      fetch(req).then((res) => {
        const clone = res.clone();
        caches.open(RUNTIME_CACHE).then((cache) => cache.put(req, clone)).catch(() => {});
        return res;
      }).catch(() =>
        caches.match(req).then((cached) => cached || new Response(JSON.stringify({ error: 'Offline: no cached data available', offline: true }), { status: 503, headers: { 'Content-Type': 'application/json' } }))
      )
    );
    return;
  }

  // Navigation: network first, fallback to cache, then login
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).then((res) => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, clone)).catch(() => {});
        return res;
      }).catch(() =>
        caches.match(req).then((cached) => cached || caches.match('/login.html') || caches.match('/index.html'))
      )
    );
    return;
  }

  // Static assets: cache first, then network
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) {
        fetch(req).then((res) => { if (res && res.ok) caches.open(CACHE_NAME).then((c) => c.put(req, res)); }).catch(() => {});
        return cached;
      }
      return fetch(req).then((res) => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone)).catch(() => {});
        }
        return res;
      }).catch(() => new Response('', { status: 503 }));
    })
  );
});
