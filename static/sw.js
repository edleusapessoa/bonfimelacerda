self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('push', (event) => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch (error) { payload = { body: event.data ? event.data.text() : '' }; }
  const title = payload.title || 'Bomfim & Lacerda Advocacia';
  const options = {
    body: payload.body || 'Você tem uma nova notificação.',
    icon: payload.icon || '/static/img/icon-192.png',
    badge: payload.badge || '/static/img/icon-192.png',
    tag: payload.tag || 'bomfim-lacerda',
    data: { url: payload.url || '/admin' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = event.notification.data && event.notification.data.url ? event.notification.data.url : '/admin';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    })
  );
});
