import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  apiBaseUrl,
  currentAccessToken,
  type AuthUser,
} from '@/features/auth/api'

export function useNotificationRealtime(user: AuthUser | null) {
  const client = useQueryClient()
  useEffect(() => {
    if (!user) return
    let socket: WebSocket | null = null
    let retryTimer: number | undefined
    let attempts = 0
    let stopped = false
    const connect = () => {
      const token = currentAccessToken()
      if (!token || stopped) return
      const base = apiBaseUrl.replace(/^http/, 'ws')
      socket = new WebSocket(
        `${base}/notifications/ws?token=${encodeURIComponent(token)}`,
      )
      socket.onopen = () => {
        attempts = 0
      }
      socket.onmessage = (event) => {
        const packet = JSON.parse(event.data as string) as { type?: string }
        if (packet.type === 'notifications.unread_changed')
          void client.invalidateQueries({ queryKey: ['notifications'] })
      }
      socket.onclose = () => {
        if (stopped) return
        attempts += 1
        retryTimer = window.setTimeout(
          connect,
          Math.min(30_000, 1_000 * 2 ** Math.min(attempts, 5)),
        )
      }
    }
    connect()
    const reconnect = () => {
      if (!document.hidden && socket?.readyState !== WebSocket.OPEN) connect()
    }
    window.addEventListener('online', reconnect)
    document.addEventListener('visibilitychange', reconnect)
    return () => {
      stopped = true
      if (retryTimer) window.clearTimeout(retryTimer)
      window.removeEventListener('online', reconnect)
      document.removeEventListener('visibilitychange', reconnect)
      socket?.close()
    }
  }, [client, user])
}
