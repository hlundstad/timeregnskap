/* Timeregnskap – service worker
   1) tar imot filer som deles til appen fra telefonens delingsmeny
   2) lar appen virke uten nett                                     */

const CACHE = 'timeregnskap-v8';
const SKALL = ['./', './index.html', './manifest.webmanifest', './icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SKALL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(n => Promise.all(n.filter(k => k !== CACHE && k !== 'deling').map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Fil delt fra en annen app
  if (e.request.method === 'POST' && url.pathname.endsWith('/share')) {
    e.respondWith((async () => {
      let tekst = '';
      try {
        const data = await e.request.formData();
        const fil = data.get('file');
        tekst = fil && fil.text ? await fil.text() : String(data.get('text') || '');
      } catch (err) {}
      const c = await caches.open('deling');
      await c.put('delt-fil', new Response(tekst, { headers: { 'content-type': 'text/plain' } }));
      return Response.redirect(new URL('./?delt=1', self.registration.scope).href, 303);
    })());
    return;
  }

  if (e.request.method !== 'GET') return;

  // Nett først, med hurtiglageret som reserve
  e.respondWith(
    fetch(e.request)
      .then(svar => {
        const kopi = svar.clone();
        caches.open(CACHE).then(c => c.put(e.request, kopi)).catch(() => {});
        return svar;
      })
      .catch(() => caches.match(e.request).then(t => t || caches.match('./index.html')))
  );
});
