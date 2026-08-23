import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Monitor, Smartphone } from 'lucide-react'

import { authApi } from '@/features/auth/api'

export function SessionsPage() {
  const queryClient = useQueryClient()
  const sessions = useQuery({
    queryKey: ['auth', 'sessions'],
    queryFn: authApi.sessions,
  })
  const revoke = async (id: string) => {
    await authApi.revokeSession(id)
    await queryClient.invalidateQueries({ queryKey: ['auth', 'sessions'] })
  }
  return (
    <div className="mx-auto max-w-4xl p-5 sm:p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Active sessions</h1>
      <p className="mt-2 text-muted-foreground">
        Review devices signed in to your account.
      </p>
      <div className="mt-8 space-y-3">
        {sessions.isLoading && (
          <div className="rounded-2xl border p-5 text-sm text-muted-foreground">
            Loading sessions…
          </div>
        )}
        {sessions.isError && (
          <div
            role="alert"
            className="rounded-2xl border border-red-500/30 p-5 text-sm text-red-500"
          >
            Sessions could not be loaded.
          </div>
        )}
        {sessions.data?.length === 0 && (
          <div className="rounded-2xl border p-8 text-center text-muted-foreground">
            No active sessions.
          </div>
        )}
        {sessions.data?.map((session) => (
          <article
            className="flex items-center gap-4 rounded-2xl border bg-card p-5"
            key={session.id}
          >
            <div className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
              {session.device?.toLowerCase().includes('mobile') ? (
                <Smartphone />
              ) : (
                <Monitor />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-medium">
                {session.device ?? 'Unknown device'}{' '}
                {session.current && (
                  <span className="ml-2 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-600">
                    Current
                  </span>
                )}
              </p>
              <p className="truncate text-sm text-muted-foreground">
                {session.browser ?? 'Unknown browser'} ·{' '}
                {session.ip_address ?? 'Unknown IP'}
              </p>
            </div>
            <button
              className="rounded-lg border px-3 py-2 text-sm font-medium hover:bg-muted"
              onClick={() => void revoke(session.id)}
              type="button"
            >
              Revoke
            </button>
          </article>
        ))}
      </div>
      <button
        className="mt-6 rounded-xl border border-red-500/30 px-4 py-2 text-sm font-medium text-red-500"
        onClick={() => void authApi.logoutAll()}
        type="button"
      >
        Sign out everywhere
      </button>
    </div>
  )
}
