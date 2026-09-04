self.addEventListener('push', (event) => {
  const payload = event.data ? event.data.json() : {}
  event.waitUntil(
    self.registration.showNotification(payload.title || 'MeetingHQ', {
      body: payload.body || 'You have a new update.',
      data: { actionUrl: payload.action_url || '/' },
      icon: '/favicon.ico',
      tag: payload.id,
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = new URL(event.notification.data?.actionUrl || '/', self.location.origin)
  if (target.origin !== self.location.origin) return
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      const existing = windows.find((client) => client.url.startsWith(self.location.origin))
      if (existing) return existing.focus().then(() => existing.navigate(target.href))
      return clients.openWindow(target.href)
    }),
  )
})
