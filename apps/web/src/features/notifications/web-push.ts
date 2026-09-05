import { notificationApi } from '@/features/notifications/api'

function urlBase64ToBytes(value: string) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padding = '='.repeat((4 - (normalized.length % 4)) % 4)
  const binary = window.atob(normalized + padding)
  return Uint8Array.from(binary, (character) => character.charCodeAt(0))
}

export function browserPushSupported() {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

export function browserPushConfigured() {
  return Boolean(import.meta.env.VITE_WEB_PUSH_PUBLIC_KEY?.trim())
}

export async function enableBrowserPush() {
  if (!browserPushSupported())
    throw new Error('Browser notifications are not supported here.')
  const publicKey = import.meta.env.VITE_WEB_PUSH_PUBLIC_KEY?.trim()
  if (!publicKey)
    throw new Error(
      'Browser push has not been configured by your administrator.',
    )
  const permission = await Notification.requestPermission()
  if (permission !== 'granted')
    throw new Error(
      'Browser notifications are blocked. Update browser permissions to enable them.',
    )
  const registration = await navigator.serviceWorker.register(
    '/meetinghq-push-worker.js',
  )
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToBytes(publicKey),
  })
  const keys = subscription.toJSON().keys
  if (!keys?.p256dh || !keys.auth)
    throw new Error('The browser did not return push encryption keys.')
  await notificationApi.savePushSubscription({
    endpoint: subscription.endpoint,
    p256dh: keys.p256dh,
    auth: keys.auth,
    user_agent: navigator.userAgent.slice(0, 512),
  })
}
