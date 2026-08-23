import { apiRequest } from '@/features/auth/api'

export interface Team {
  id: string
  organization_id: string
  workspace_id: string
  name: string
  slug: string
  description: string | null
  avatar_url: string | null
  banner_url: string | null
  color: string
  icon: string | null
  classification: string
  owner_id: string | null
  settings: Record<string, unknown>
  visibility: 'public' | 'private'
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface TeamOverview {
  team: Team
  owner_count: number
  administrator_count: number
  member_count: number
  guest_count: number
  channel_count: number
  meeting_count: number
  upcoming_meeting_count: number
  calendar_count: number
  file_count: number
  storage_bytes: number
  wiki_count: number
  note_count: number
  app_count: number
  active_member_count: number
  open_action_count: number
  announcement_count: number
  health_score: number
  recent_activity: Array<{
    id: string
    event_type: string
    occurred_at: string
  }>
  recent_conversations: Array<{
    id: string
    name: string
    channel_kind: string
    updated_at: string
  }>
  upcoming_meetings: Array<{
    id: string
    title: string
    start_datetime: string
    status: string
  }>
}

export interface TeamMember {
  id: string
  user_id: string
  email: string
  display_name: string
  role: 'owner' | 'manager' | 'member'
  joined_at: string
}

export interface TeamChannel {
  id: string
  name: string
  description: string | null
  channel_kind: string
  visibility: string
  moderation_enabled: boolean
  read_only: boolean
  favorite: boolean
  pinned: boolean
  archived_at: string | null
  message_count: number
  member_count: number
  last_activity: string | null
}

export interface TeamDocument {
  id: string
  document_type: 'wiki' | 'note'
  title: string
  content: string
  created_at: string
  updated_at: string
}

export interface TeamIntegration {
  id: string
  provider: string
  display_name: string
  enabled: boolean
  configuration: Record<string, unknown>
  created_at: string
}

export const teamsApi = {
  list: (filters?: {
    workspace_id?: string
    search?: string
    archived?: boolean
    visibility?: string
  }) => {
    const query = new URLSearchParams()
    Object.entries(filters ?? {}).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value))
    })
    return apiRequest<Team[]>(
      `/teams${query.size ? `?${query}` : ''}`,
      {},
      true,
    )
  },
  create: (body: object) =>
    apiRequest<Team>(
      '/teams',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  get: (id: string) => apiRequest<Team>(`/teams/${id}`, {}, true),
  overview: (id: string) =>
    apiRequest<TeamOverview>(`/teams/${id}/overview`, {}, true),
  update: (id: string, body: object) =>
    apiRequest<Team>(
      `/teams/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  archive: (id: string) =>
    apiRequest<Team>(`/teams/${id}/archive`, { method: 'POST' }, true),
  restore: (id: string) =>
    apiRequest<Team>(`/teams/${id}/restore`, { method: 'POST' }, true),
  members: (id: string) =>
    apiRequest<TeamMember[]>(`/teams/${id}/members`, {}, true),
  setMemberRole: (id: string, userId: string, role: string) =>
    apiRequest(
      `/teams/${id}/members/${userId}`,
      { method: 'PATCH', body: JSON.stringify({ role }) },
      true,
    ),
  bulkMembers: (id: string, userIds: string[], action: string) =>
    apiRequest<{ updated_ids: string[]; skipped_ids: string[] }>(
      `/teams/${id}/members/bulk`,
      {
        method: 'POST',
        body: JSON.stringify({ user_ids: userIds, action }),
      },
      true,
    ),
  channels: (
    id: string,
    filters?: { search?: string; archived?: boolean; channel_kind?: string },
  ) => {
    const query = new URLSearchParams()
    Object.entries(filters ?? {}).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value))
    })
    return apiRequest<TeamChannel[]>(
      `/teams/${id}/channels${query.size ? `?${query}` : ''}`,
      {},
      true,
    )
  },
  createChannel: (id: string, body: object) =>
    apiRequest<TeamChannel>(
      `/teams/${id}/channels`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateChannel: (id: string, channelId: string, body: object) =>
    apiRequest<TeamChannel>(
      `/teams/${id}/channels/${channelId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  channelLifecycle: (
    id: string,
    channelId: string,
    action: 'archive' | 'restore',
  ) =>
    apiRequest(
      `/teams/${id}/channels/${channelId}/${action}`,
      { method: 'POST' },
      true,
    ),
  channelPreference: (id: string, channelId: string, body: object) =>
    apiRequest(
      `/teams/${id}/channels/${channelId}/preference`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  documents: (id: string, documentType: 'wiki' | 'note') =>
    apiRequest<TeamDocument[]>(
      `/teams/${id}/documents?document_type=${documentType}`,
      {},
      true,
    ),
  createDocument: (id: string, body: object) =>
    apiRequest<TeamDocument>(
      `/teams/${id}/documents`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  integrations: (id: string) =>
    apiRequest<TeamIntegration[]>(`/teams/${id}/integrations`, {}, true),
  updateIntegration: (id: string, body: object) =>
    apiRequest<TeamIntegration>(
      `/teams/${id}/integrations`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
}
