/* Public startup-shell cache only. Dynamic dashboard, health and workspace data stay network-only. */
const CACHE_NAME = "velacare-public-startup-v1";
const SCOPE_URL = new URL(self.registration.scope);
const SHELL_URLS = [
  "offline-shell.html",
  "pwa/startup.v1.css",
  "pwa/startup.v1.js",
  "pwa/icons/icon-192.png",
  "pwa/icons/icon-512.png",
].map((path) => new URL(path, SCOPE_URL).href);
const OFFLINE_SHELL_URL = new URL("offline-shell.html", SCOPE_URL).href;
const SCOPE_PATH = SCOPE_URL.pathname;

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.all(SHELL_URLS.map(async (url) => {
      const response = await fetch(url, { cache: "reload", credentials: "same-origin" });
      if (!response.ok) throw new Error(`Could not cache public startup asset: ${new URL(url).pathname}`);
      await cache.put(url, response);
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith("velacare-public-startup-") && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

async function publicAsset(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request.url);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && response.type === "basic") await cache.put(request.url, response.clone());
  return response;
}

async function offlineShell() {
  const cache = await caches.open(CACHE_NAME);
  return (await cache.match(OFFLINE_SHELL_URL)) || new Response(
    "<!doctype html><title>VelaCare unavailable</title><p>VelaCare is offline. Reconnect and retry.</p>",
    { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } },
  );
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(SCOPE_PATH)) return;
  if (SHELL_URLS.includes(url.href)) {
    event.respondWith(publicAsset(request));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).then((response) => {
      if (response.status >= 500) return offlineShell();
      return response;
    }).catch(offlineShell));
  }
});
