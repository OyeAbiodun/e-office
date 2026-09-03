import {
  confirmDestructiveAction,
  notify,
  operation,
} from '@/components/feedback/events'

const configuredApiUrl = import.meta.env.VITE_API_URL?.trim()

export const apiBaseUrl = (
  configuredApiUrl || `${window.location.origin}/api/v1`
).replace(/\/$/, '')

export interface AuthUser {
  id: string
  organization_id: string
  email: string
  username: string
  first_name: string
  last_name: string
  display_name: string
  avatar_url: string | null
  email_verified: boolean
  force_password_change: boolean
  roles: string[]
  permissions: string[]
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  refresh_token: string
  csrf_token: string
  user: AuthUser
}

export interface Session {
  id: string
  device: string | null
  browser: string | null
  os: string | null
  ip_address: string | null
  last_activity: string
  expires_at: string
  current: boolean
}

let accessToken: string | null = null
let activeCsrfToken: string | null = null
let refreshPromise: Promise<AuthResponse> | null = null
let restorePromise: Promise<AuthUser> | null = null

export const currentAccessToken = () => accessToken

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
  }
}

function authLog(event: string, detail: Record<string, unknown> = {}) {
  if (import.meta.env.DEV)
    console.info(`[MeetingHQ auth] ${event}`, {
      at: new Date().toISOString(),
      ...detail,
    })
}

function cookieCsrfToken(): string | undefined {
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith('meetinghq_csrf='))
    ?.split('=')[1]
}

function csrfToken(): string | undefined {
  const cookie = cookieCsrfToken()
  return activeCsrfToken ?? (cookie ? decodeURIComponent(cookie) : undefined)
}

function validationMessage(details: unknown): string | null {
  if (!details || typeof details !== 'object') return null
  const entries = (details as { detail?: unknown }).detail
  if (!Array.isArray(entries) || entries.length === 0) return null
  const first = entries[0]
  if (!first || typeof first !== 'object') return null
  const issue = first as { loc?: unknown; msg?: unknown }
  const location = Array.isArray(issue.loc)
    ? issue.loc.filter((part) => part !== 'body').join(' ')
    : ''
  const message = typeof issue.msg === 'string' ? issue.msg : null
  if (!message) return null
  return location ? `${location}: ${message}` : message
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { message?: string; details?: unknown }
    } | null
    const genericMessage = 'The request could not be completed.'
    const apiError = payload?.error
    const message = apiError?.message
    throw new ApiError(
      message === genericMessage
        ? (validationMessage(apiError?.details) ?? message)
        : (message ?? 'Request failed'),
      response.status,
    )
  }
  const payload = (await response.json()) as T | { success: boolean; data: T }
  if (
    payload &&
    typeof payload === 'object' &&
    'success' in payload &&
    'data' in payload
  )
    return payload.data
  return payload as T
}

async function fetchApi<T>(
  path: string,
  options: RequestInit,
  token: string | null,
): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData))
    headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const csrf = csrfToken()
  if (csrf) headers.set('X-CSRF-Token', csrf)
  return parseResponse<T>(
    await fetch(`${apiBaseUrl}${path}`, {
      ...options,
      headers,
      credentials: 'include',
    }),
  )
}

async function refreshSession(): Promise<AuthResponse> {
  if (refreshPromise) {
    authLog('refresh_joined_existing_request')
    return refreshPromise
  }
  authLog('refresh_started', { csrfAvailable: Boolean(csrfToken()) })
  refreshPromise = fetchApi<AuthResponse>(
    '/auth/refresh',
    { method: 'POST', body: JSON.stringify({}) },
    null,
  )
    .then((result) => {
      accessToken = result.access_token
      activeCsrfToken = result.csrf_token
      authLog('refresh_succeeded', {
        userId: result.user.id,
        organizationId: result.user.organization_id,
      })
      return result
    })
    .catch((error: unknown) => {
      accessToken = null
      activeCsrfToken = null
      const reason = error instanceof Error ? error.message : 'unknown'
      authLog('refresh_failed', {
        reason,
        status: error instanceof ApiError ? error.status : undefined,
      })
      window.dispatchEvent(
        new CustomEvent('meetinghq:session-expired', {
          detail: { reason: `refresh_failed: ${reason}` },
        }),
      )
      throw error
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  authenticated = false,
  feedback = true,
): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const mutation =
    method !== 'GET' &&
    !path.startsWith('/auth/refresh') &&
    !path.startsWith('/auth/login')
  const destructive =
    method === 'DELETE' ||
    (method === 'POST' &&
      (path.toLowerCase().includes('archive') ||
        path.toLowerCase().includes('disable')))
  if (destructive) {
    const approved = await confirmDestructiveAction(path)
    if (!approved) throw new ApiError('Action cancelled', 0)
  }
  if (mutation) operation(true)
  try {
    if (authenticated && !accessToken) await refreshSession()
    const result = await fetchApi<T>(
      path,
      options,
      authenticated ? accessToken : null,
    )
    if (mutation && feedback)
      notify({
        tone: 'success',
        title:
          method === 'DELETE'
            ? 'Deleted successfully'
            : method === 'POST'
              ? 'Completed successfully'
              : 'Changes saved',
        description: 'Your change has been applied.',
      })
    return result
  } catch (error) {
    if (
      authenticated &&
      error instanceof ApiError &&
      error.status === 401 &&
      path !== '/auth/refresh'
    ) {
      authLog('access_token_rejected', { path, action: 'refresh_and_retry' })
      await refreshSession()
      const result = await fetchApi<T>(path, options, accessToken)
      if (mutation && feedback)
        notify({
          tone: 'success',
          title: 'Completed successfully',
          description: 'Your change has been applied.',
        })
      return result
    }
    if (authenticated && error instanceof ApiError && error.status === 403) {
      authLog('permission_denied', { path, action: 'show_access_denied' })
      if (window.location.pathname !== '/forbidden')
        window.location.assign('/forbidden')
    }
    if (mutation && feedback)
      notify({
        tone: 'error',
        title: 'Action could not be completed',
        description:
          error instanceof Error ? error.message : 'Please try again.',
      })
    throw error
  } finally {
    if (mutation) operation(false)
  }
}

export async function apiRawRequest(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  if (!accessToken) await refreshSession()
  const headers = new Headers(options.headers)
  headers.set('Authorization', `Bearer ${accessToken}`)
  const csrf = csrfToken()
  if (csrf) headers.set('X-CSRF-Token', csrf)
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { message?: string }
    } | null
    throw new ApiError(
      payload?.error?.message ?? 'Request failed',
      response.status,
    )
  }
  return response
}

export async function authenticatedAsset(assetUrl: string): Promise<Blob> {
  const base = new URL(apiBaseUrl, window.location.origin)
  const asset = new URL(
    assetUrl,
    assetUrl.startsWith('/') ? base.origin : window.location.origin,
  )
  if (asset.origin !== base.origin || !asset.pathname.startsWith(base.pathname))
    throw new ApiError('Unsupported protected asset URL', 400)
  const relativePath = `${asset.pathname.slice(base.pathname.length)}${asset.search}`
  return (await apiRawRequest(relativePath)).blob()
}

async function restoreSession(): Promise<AuthUser> {
  if (restorePromise) {
    authLog('session_restore_joined_existing_request')
    return restorePromise
  }
  restorePromise = refreshSession()
    .then((session) => {
      const user = session.user
      authLog('current_user_succeeded', {
        userId: user.id,
        organizationId: user.organization_id,
      })
      return user
    })
    .finally(() => {
      restorePromise = null
    })
  return restorePromise
}

export const authApi = {
  async login(values: object): Promise<AuthResponse> {
    const result = await fetchApi<AuthResponse>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify(values) },
      null,
    )
    accessToken = result.access_token
    activeCsrfToken = result.csrf_token
    authLog('login_succeeded', {
      userId: result.user.id,
      organizationId: result.user.organization_id,
    })
    return result
  },
  async register(values: object): Promise<AuthResponse> {
    const result = await fetchApi<AuthResponse>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify(values) },
      null,
    )
    accessToken = result.access_token
    activeCsrfToken = result.csrf_token
    return result
  },
  refresh: refreshSession,
  restoreSession,
  async me() {
    const user = await apiRequest<AuthUser>('/auth/me', {}, true)
    authLog('current_user_succeeded', {
      userId: user.id,
      organizationId: user.organization_id,
    })
    return user
  },
  async logout(): Promise<void> {
    authLog('logout_started', { reason: 'user_requested' })
    await apiRequest('/auth/logout', { method: 'POST' }, true)
    accessToken = null
    activeCsrfToken = null
    authLog('logout_completed', { reason: 'user_requested' })
  },
  forgotPassword: (values: object) =>
    apiRequest<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify(values),
    }),
  resetPassword: (values: object) =>
    apiRequest<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(values),
    }),
  changePassword: (values: object) =>
    apiRequest<{ message: string }>(
      '/auth/change-password',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  verifyEmail: (token: string) =>
    apiRequest<{ message: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  sessions: () => apiRequest<Session[]>('/auth/sessions', {}, true),
  revokeSession: (id: string) =>
    apiRequest(`/auth/sessions/${id}`, { method: 'DELETE' }, true),
  logoutAll: () => apiRequest('/auth/sessions', { method: 'DELETE' }, true),
}
