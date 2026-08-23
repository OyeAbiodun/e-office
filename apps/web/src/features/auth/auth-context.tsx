import { type PropsWithChildren, useEffect, useMemo, useState } from 'react'

import { authApi, type AuthUser } from '@/features/auth/api'
import { AuthContext, type AuthContextValue } from '@/features/auth/auth-store'

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const onSessionExpired = (event: Event) => {
      const reason =
        event instanceof CustomEvent && typeof event.detail?.reason === 'string'
          ? event.detail.reason
          : 'refresh_failed'
      if (import.meta.env.DEV)
        console.info('[MeetingHQ auth] logout_reason', { reason })
      if (active) {
        setUser(null)
        setLoading(false)
      }
    }
    window.addEventListener('meetinghq:session-expired', onSessionExpired)
    authApi
      .restoreSession()
      .then((currentUser) => {
        if (active) setUser(currentUser)
      })
      .catch((error: unknown) => {
        if (import.meta.env.DEV)
          console.info('[MeetingHQ auth] startup_session_unavailable', {
            reason: error instanceof Error ? error.message : 'unknown',
          })
        if (active) setUser(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
      window.removeEventListener('meetinghq:session-expired', onSessionExpired)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login: async (values) => {
        const authenticated = (await authApi.login(values)).user
        setUser(authenticated)
        return authenticated
      },
      register: async (values) =>
        setUser((await authApi.register(values)).user),
      refreshUser: async () => {
        const current = await authApi.me()
        setUser(current)
        return current
      },
      logout: async () => {
        await authApi.logout()
        setUser(null)
      },
    }),
    [loading, user],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
