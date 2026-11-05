const CACHE_NAME = 'edupulse-shell-v1';
const SHELL_URL = '/';
const PRECACHE_URLS = [
  '/manifest.webmanifest',
  '/favicon-192.svg',
  '/logo.svg',
  '/logo-dark.svg',
  '/logo-monochrome.svg',
];
const PUBLIC_IMAGE_URLS = [
  '/images/edupulse-smt-logo.jpg',
  '/images/school-classroom.jpg',
  '/images/ghana-classroom.jpg',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    const response = await fetch(SHELL_URL, { cache: 'no-cache' });
    if (!response.ok) {
      throw new Error(`Unable to cache EduPulse app shell: ${response.status}`);
    }

    await cache.put(SHELL_URL, response.clone());
    const html = await response.text();
    const assetUrls = [...html.matchAll(/(?:src|href)=["']([^"']+)["']/g)]
      .map((match) => match[1])
      .filter((url) => url.startsWith('/assets/'));

    await Promise.all([
      ...PRECACHE_URLS.map((url) => cache.add(url)),
      ...assetUrls.map((url) => cache.add(url)),
    ]);
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter((cacheName) => cacheName.startsWith('edupulse-shell-') && cacheName !== CACHE_NAME)
        .map((cacheName) => caches.delete(cacheName)),
    );
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname === '/api' || url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.ok) {
          const cache = await caches.open(CACHE_NAME);
          await cache.put(SHELL_URL, response.clone());
        }
        return response;
      } catch {
        const cachedShell = await caches.match(SHELL_URL);
        if (cachedShell) return cachedShell;
        return new Response('EduPulse is unavailable offline. Connect to the internet and try again.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
      }
    })());
    return;
  }

  const isAppAsset = url.pathname.startsWith('/assets/')
    || PUBLIC_IMAGE_URLS.includes(url.pathname)
    || ['/favicon-192.svg', '/logo.svg', '/logo-dark.svg', '/logo-monochrome.svg', '/manifest.webmanifest']
      .includes(url.pathname);
  if (!isAppAsset) return;

  event.respondWith((async () => {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) return cachedResponse;

    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(request, response.clone());
    }
    return response;
  })());
});
