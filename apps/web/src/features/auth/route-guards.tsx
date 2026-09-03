import { Navigate, Outlet, useRouterState } from '@tanstack/react-router'
import { LoaderCircle } from 'lucide-react'

import { useAuth } from '@/features/auth/auth-store'
import { allowsAuthenticatedPublicAccess } from '@/features/auth/public-route-policy'

function LoadingIdentity() {
  return (
    <div className="grid min-h-screen place-items-center">
      <LoaderCircle
        className="size-7 animate-spin text-primary"
        aria-label="Loading identity"
      />
    </div>
  )
}

export function ProtectedRoute() {
  const { user, loading } = useAuth()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  if (loading) return <LoadingIdentity />
  if (!user) {
    if (import.meta.env.DEV)
      console.info('[MeetingHQ auth] route_guard_redirect', {
        from: pathname,
        to: '/login',
        reason: 'no_authenticated_user_after_refresh',
      })
    return <Navigate to="/login" />
  }
  if (user.force_password_change && pathname !== '/change-password')
    return <Navigate to="/change-password" />
  return <Outlet />
}

export function PublicRoute() {
  const { user, loading } = useAuth()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  if (loading) return <LoadingIdentity />
  if (user && !allowsAuthenticatedPublicAccess(pathname)) {
    if (import.meta.env.DEV)
      console.info('[MeetingHQ auth] route_guard_redirect', {
        to: user.force_password_change ? '/change-password' : '/',
        reason: 'authenticated_user_opened_public_route',
      })
    return (
      <Navigate to={user.force_password_change ? '/change-password' : '/'} />
    )
  }
  return <Outlet />
}
