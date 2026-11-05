/* Нейростат: Service Worker — Web Push («Слово дня»).
   Отдаётся с корня домена как /sw.js (scope '/'), см. views.service_worker_js:
   из /static/ Service Worker не может управлять всем сайтом. */

self.addEventListener('install', function () {
    self.skipWaiting();
});

self.addEventListener('activate', function (event) {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function (event) {
    var data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = { title: 'Нейростат', body: event.data.text() };
        }
    }
    var title = data.title || 'Нейростат';
    var options = {
        body: data.body || '',
        icon: data.icon || '/static/images/pwa/icon-192.png',
        badge: data.badge || '/static/images/pwa/badge-72.png',
        tag: data.tag || 'neurostat',
        lang: 'ru',
        data: { url: data.url || '/' }
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var url = (event.notification.data && event.notification.data.url) || '/';
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(function (list) {
                for (var i = 0; i < list.length; i++) {
                    if ('navigate' in list[i]) {
                        return list[i].navigate(url).then(function (c) {
                            return c.focus();
                        });
                    }
                }
                return self.clients.openWindow(url);
            })
    );
});
