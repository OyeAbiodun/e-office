import { CheckCircle2, LoaderCircle, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearch } from '@tanstack/react-router'

import { authApi } from '@/features/auth/api'

export function VerifyEmailPage() {
  const search = useSearch({ strict: false }) as { token?: string }
  const [state, setState] = useState<'loading' | 'success' | 'error'>('loading')
  useEffect(() => {
    if (!search.token) return setState('error')
    authApi
      .verifyEmail(search.token)
      .then(() => setState('success'))
      .catch(() => setState('error'))
  }, [search.token])
  const Icon =
    state === 'loading'
      ? LoaderCircle
      : state === 'success'
        ? CheckCircle2
        : XCircle
  return (
    <section className="text-center">
      <Icon
        className={`mx-auto size-12 ${state === 'loading' ? 'animate-spin text-primary' : state === 'success' ? 'text-emerald-500' : 'text-red-500'}`}
      />
      <h2 className="mt-5 text-3xl font-semibold tracking-tight">
        {state === 'loading'
          ? 'Verifying your email'
          : state === 'success'
            ? 'Email verified'
            : 'Verification failed'}
      </h2>
      <p className="mt-3 text-muted-foreground">
        {state === 'success'
          ? 'Your email address is now verified.'
          : state === 'error'
            ? 'This link is invalid or has expired.'
            : 'This will only take a moment.'}
      </p>
      {state !== 'loading' && (
        <Link
          className="mt-7 inline-block font-medium text-primary"
          to={state === 'success' ? '/' : '/login'}
        >
          {state === 'success' ? 'Open MeetingHQ' : 'Return to sign in'}
        </Link>
      )}
    </section>
  )
}
