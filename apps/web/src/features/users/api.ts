import { apiRequest } from '@/features/auth/api'

export interface Permission {
  id: string
  name: string
  resource: string
  action: string
  description: string | null
}

export interface Role {
  id: string
  organization_id: string
  name: string
  description: string | null
  system_role: boolean
  permissions: Permission[]
}

export interface ManagedUser {
  id: string
  organization_id: string
  email: string
  username: string
  first_name: string
  last_name: string
  display_name: string
  avatar_url: string | null
  phone: string | null
  job_title: string | null
  department: string | null
  location: string | null
  workspace_id: string | null
  team_id: string | null
  status: 'active' | 'invited' | 'suspended'
  email_verified: boolean
  force_password_change: boolean
  last_login: string | null
  timezone: string
  language: string
  roles: Role[]
  notification_preferences?: Record<string, unknown>
}

export interface ProfileCenter {
  id: string
  organization_id: string
  user_id: string
  cover_image_url: string | null
  presence: 'available' | 'busy' | 'do_not_disturb' | 'away' | 'offline'
  status_message: string | null
  manager_id: string | null
  emergency_contact: Record<string, unknown>
  email_aliases: string[]
  signature: string | null
  working_hours: Record<string, unknown>
  preferences: Record<string, Record<string, unknown> | boolean>
  connected_accounts: Array<Record<string, unknown>>
  mfa_enabled: boolean
  storage_used_bytes: number
  license_name: string
  updated_at: string
}

export interface ApiToken {
  id: string
  name: string
  token_prefix: string
  scopes: string[]
  last_used_at: string | null
  expires_at: string | null
  revoked_at: string | null
  created_at: string
  token?: string
}

export interface MfaSetup {
  secret: string
  provisioning_uri: string
  qr_code_data_url: string
}

export interface MfaRecoveryCodes {
  recovery_codes: string[]
}

export interface SecurityEvent {
  action: string
  created_at: string
  ip_address: string | null
  metadata: Record<string, unknown>
}

export interface UserInput {
  first_name: string
  last_name: string
  email: string
  phone?: string | null
  job_title?: string | null
  department?: string | null
  location?: string | null
  workspace_id?: string | null
  team_id?: string | null
  role_ids: string[]
  temporary_password?: string
  send_welcome_email?: boolean
}

function params(filters: Record<string, string | boolean | undefined>) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters))
    if (value !== undefined && value !== '') query.set(key, String(value))
  const encoded = query.toString()
  return encoded ? `?${encoded}` : ''
}

export const userAdminApi = {
  list: (filters: {
    search?: string
    status?: string
    role_id?: string
    department?: string
    include_removed?: boolean
  }) => apiRequest<ManagedUser[]>(`/users${params(filters)}`, {}, true),
  create: (values: UserInput) =>
    apiRequest<ManagedUser>(
      '/users',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  update: (id: string, values: Partial<UserInput>) =>
    apiRequest<ManagedUser>(
      `/users/${id}`,
      { method: 'PATCH', body: JSON.stringify(values) },
      true,
    ),
  activate: (id: string) =>
    apiRequest<ManagedUser>(`/users/${id}/activate`, { method: 'POST' }, true),
  disable: (id: string) =>
    apiRequest<ManagedUser>(`/users/${id}/suspend`, { method: 'POST' }, true),
  remove: (id: string) =>
    apiRequest(`/users/${id}`, { method: 'DELETE' }, true),
  restore: (id: string) =>
    apiRequest<ManagedUser>(`/users/${id}/restore`, { method: 'POST' }, true),
  resetPassword: (id: string) =>
    apiRequest<{ temporary_password: string; force_password_change: boolean }>(
      `/users/${id}/reset-password`,
      { method: 'POST' },
      true,
    ),
  bulk: (user_ids: string[], action: string) =>
    apiRequest(
      '/users/actions/bulk',
      { method: 'POST', body: JSON.stringify({ user_ids, action }) },
      true,
    ),
  roles: () => apiRequest<Role[]>('/roles', {}, true),
  permissions: () => apiRequest<Permission[]>('/permissions', {}, true),
  createRole: (values: {
    name: string
    description?: string
    permission_ids: string[]
  }) =>
    apiRequest<Role>(
      '/roles',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  updateRole: (
    id: string,
    values: { name?: string; description?: string; permission_ids?: string[] },
  ) =>
    apiRequest<Role>(
      `/roles/${id}`,
      { method: 'PATCH', body: JSON.stringify(values) },
      true,
    ),
}

export const profileApi = {
  profile: () => apiRequest<ManagedUser>('/profile', {}, true),
  updateProfile: (values: Record<string, unknown>) =>
    apiRequest<ManagedUser>(
      '/profile',
      { method: 'PATCH', body: JSON.stringify(values) },
      true,
    ),
  uploadAvatar: (avatar: File) => {
    const body = new FormData()
    body.append('avatar', avatar)
    return apiRequest<ManagedUser>(
      '/profile/avatar',
      { method: 'POST', body },
      true,
    )
  },
  removeAvatar: () =>
    apiRequest<ManagedUser>('/profile/avatar', { method: 'DELETE' }, true),
  center: () => apiRequest<ProfileCenter>('/profile/center', {}, true),
  securityHistory: () =>
    apiRequest<SecurityEvent[]>('/profile/security-history', {}, true),
  updateCenter: (values: Record<string, unknown>) =>
    apiRequest<ProfileCenter>(
      '/profile/center',
      { method: 'PATCH', body: JSON.stringify(values) },
      true,
    ),
  tokens: () => apiRequest<ApiToken[]>('/profile/api-tokens', {}, true),
  createToken: (values: {
    name: string
    scopes?: string[]
    expires_at?: string
  }) =>
    apiRequest<ApiToken>(
      '/profile/api-tokens',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  revokeToken: (id: string) =>
    apiRequest(`/profile/api-tokens/${id}`, { method: 'DELETE' }, true),
  setupMfa: () =>
    apiRequest<MfaSetup>('/profile/mfa/setup', { method: 'POST' }, true),
  verifyMfa: (code: string) =>
    apiRequest<MfaRecoveryCodes>(
      '/profile/mfa/verify',
      { method: 'POST', body: JSON.stringify({ code }) },
      true,
    ),
  disableMfa: (values: { current_password: string; code?: string }) =>
    apiRequest(
      '/profile/mfa/disable',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  regenerateRecoveryCodes: (values: {
    current_password: string
    code: string
  }) =>
    apiRequest<MfaRecoveryCodes>(
      '/profile/mfa/recovery-codes',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
}
