/* DownerStuff service worker (items 317, 318, 329). The app opens without signal using the last copy on this phone.
   App files (versioned with ?v=) come from the cache first; data files come from the network first, falling back to the last good copy.
   A new upload changes the version, so the next visit fetches the new files and the page offers a one-tap update. */
const VERSION = 'ds-v35';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).catch(() => { })); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('message', e => { if (e.data === 'skip') self.skipWaiting(); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;                       // supabase, fonts, GitHub: straight to the network
  const isData = u.pathname.includes('/data/'), isPage = e.request.mode === 'navigate' || u.pathname.endsWith('/index.html') || u.pathname.endsWith('/');
  if (isData || isPage) {                                                                          // network first, last good copy when offline
    e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(VERSION).then(x => x.put(e.request, c)); } return r; })
      .catch(() => caches.match(e.request).then(r => r || caches.match('index.html'))));
    return;
  }
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(r => { if (r.ok && u.search.includes('v=')) { const c = r.clone(); caches.open(VERSION).then(x => x.put(e.request, c)); } return r; })));
});
