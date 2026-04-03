// Service Worker for Web Push Notifications + PWA Caching (Sprint 6)

var CACHE_NAME = 'tsw-couple-v1';
var STATIC_ASSETS = [
  '/couple/login',
  '/couple/dashboard',
  '/manifest.json',
  '/favicon.svg',
  '/logo_all.png',
];

// ============================================================================
// INSTALL: Pre-cache critical assets
// ============================================================================

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('[SW] Pre-caching static assets');
        // Don't fail install if pre-caching fails (assets may not exist yet)
        return cache.addAll(STATIC_ASSETS).catch(function(err) {
          console.warn('[SW] Pre-cache partial failure (non-blocking):', err);
        });
      })
      .then(function() {
        return self.skipWaiting();
      })
  );
});

// ============================================================================
// ACTIVATE: Clean up old caches
// ============================================================================

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.filter(function(name) {
          return name.startsWith('tsw-couple-') && name !== CACHE_NAME;
        }).map(function(name) {
          console.log('[SW] Deleting old cache:', name);
          return caches.delete(name);
        })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// ============================================================================
// FETCH: Caching strategies
// ============================================================================

self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);

  // Skip non-GET requests (POST/PUT/DELETE always go to network)
  if (event.request.method !== 'GET') return;

  // Skip cross-origin requests
  if (url.origin !== self.location.origin) return;

  // API calls: Network-first with no cache fallback (data must be fresh)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/couple/portal/') || url.pathname.startsWith('/web-push/')) {
    return;
  }

  // Static Next.js assets (content-hashed): Cache-first
  if (url.pathname.startsWith('/_next/static/')) {
    event.respondWith(
      caches.match(event.request).then(function(cached) {
        if (cached) return cached;
        return fetch(event.request).then(function(response) {
          if (response.ok) {
            var clone = response.clone();
            caches.open(CACHE_NAME).then(function(cache) {
              cache.put(event.request, clone);
            });
          }
          return response;
        });
      })
    );
    return;
  }

  // Images and fonts: Stale-while-revalidate
  if (url.pathname.match(/\.(png|jpg|jpeg|svg|gif|ico|woff|woff2|ttf|eot)$/)) {
    event.respondWith(
      caches.match(event.request).then(function(cached) {
        var fetchPromise = fetch(event.request).then(function(response) {
          if (response.ok) {
            var clone = response.clone();
            caches.open(CACHE_NAME).then(function(cache) {
              cache.put(event.request, clone);
            });
          }
          return response;
        }).catch(function() {
          return cached;
        });
        return cached || fetchPromise;
      })
    );
    return;
  }

  // HTML pages (couple portal): Network-first with cache fallback
  if (url.pathname.startsWith('/couple/')) {
    event.respondWith(
      fetch(event.request).then(function(response) {
        if (response.ok) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      }).catch(function() {
        return caches.match(event.request).then(function(cached) {
          return cached || caches.match('/couple/dashboard');
        });
      })
    );
    return;
  }
});

// ============================================================================
// PUSH NOTIFICATIONS (unchanged from Sprint 3)
// ============================================================================

self.addEventListener('push', function(event) {
  if (!event.data) {
    console.log('Push event but no data');
    return;
  }

  try {
    const data = event.data.json();

    const options = {
      body: data.body || data.message || 'New notification',
      icon: data.icon || '/icon-192x192.png',
      badge: data.badge || '/badge-72x72.png',
      tag: data.tag || 'default',
      data: {
        url: data.url || data.click_url || '/',
        ...data
      },
      actions: data.actions || [],
      requireInteraction: data.requireInteraction || false,
      silent: data.silent || false,
      vibrate: [200, 100, 200]
    };

    event.waitUntil(
      self.registration.showNotification(data.title || 'Notification', options)
    );
  } catch (error) {
    console.error('Error parsing push data:', error);
    // Fallback for plain text
    event.waitUntil(
      self.registration.showNotification('Notification', {
        body: event.data.text(),
        icon: '/icon-192x192.png'
      })
    );
  }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  const url = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(function(clientList) {
        // If a window is already open, focus it
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.focus();
            if (url !== '/') {
              client.navigate(url);
            }
            return;
          }
        }
        // Otherwise open a new window
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
  );
});

self.addEventListener('notificationclose', function(event) {
  // Optional: Track notification dismissals
  console.log('Notification closed:', event.notification.tag);
});

// Handle subscription change (browser may refresh subscription)
self.addEventListener('pushsubscriptionchange', function(event) {
  event.waitUntil(
    self.registration.pushManager.subscribe({ userVisibleOnly: true })
      .then(function(subscription) {
        // Send new subscription to server
        return fetch('/api/web-push/subscription', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(subscription)
        });
      })
  );
});
