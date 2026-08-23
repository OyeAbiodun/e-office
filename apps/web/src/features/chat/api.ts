import { apiRequest, currentAccessToken } from '@/features/auth/api'

export interface Conversation {
  id: string
  organization_id: string
  workspace_id: string
  team_id: string | null
  type: string
  name: string | null
  description: string | null
  visibility: string
  channel_kind: 'standard' | 'private' | 'shared'
  created_by: string
  created_at: string
  updated_at: string
  archived_at: string | null
  unread_count: number
  member_count: number
  last_message: ChatMessage | null
}

export interface ChatMessage {
  id: string
  conversation_id: string
  sender_id: string
  sender_name: string
  parent_message_id: string | null
  message_type: string
  body: string
  edited: boolean
  edited_at: string | null
  deleted_at: string | null
  created_at: string
  reactions: Array<{ id: string; emoji: string; user_id: string }>
  attachments: Array<Record<string, unknown>>
  thread: { id: string; reply_count: number } | null
  delivery_status: string
}

export interface ChatDashboard {
  unread_messages: number
  recent_conversations: Conversation[]
  active_channels: number
  online_members: number
}

export interface ChannelTab {
  id: string
  conversation_id: string
  name: string
  tab_type: string
  configuration: string
  sort_order: number
}

export interface MessageDraft {
  id: string
  body: string
  updated_at: string
}

export const chatApi = {
  dashboard: () => apiRequest<ChatDashboard>('/chat/dashboard', {}, true),
  conversations: (archived = false) =>
    apiRequest<Conversation[]>(`/conversations?archived=${archived}`, {}, true),
  create: (body: object) =>
    apiRequest<Conversation>(
      '/conversations',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  get: (id: string) =>
    apiRequest<Conversation>(`/conversations/${id}`, {}, true),
  messages: (id: string, parent?: string, cursor?: string) =>
    apiRequest<{
      items: ChatMessage[]
      next_cursor: string | null
      has_more: boolean
    }>(
      `/conversations/${id}/messages?${new URLSearchParams({
        ...(parent ? { parent_message_id: parent } : {}),
        ...(cursor ? { cursor } : {}),
      })}`,
      {},
      true,
    ),
  send: (id: string, body: object) =>
    apiRequest<ChatMessage>(
      `/conversations/${id}/messages`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  edit: (id: string, body: string) =>
    apiRequest<ChatMessage>(
      `/messages/${id}`,
      { method: 'PATCH', body: JSON.stringify({ body }) },
      true,
    ),
  remove: (id: string) =>
    apiRequest(`/messages/${id}`, { method: 'DELETE' }, true),
  react: (id: string, emoji: string) =>
    apiRequest(
      `/messages/${id}/reactions`,
      { method: 'POST', body: JSON.stringify({ emoji }) },
      true,
    ),
  pin: (id: string) =>
    apiRequest(`/messages/${id}/pin`, { method: 'POST' }, true),
  pins: (id: string) =>
    apiRequest<Array<Record<string, unknown>>>(
      `/conversations/${id}/pins`,
      {},
      true,
    ),
  tabs: (id: string) =>
    apiRequest<ChannelTab[]>(`/conversations/${id}/tabs`, {}, true),
  draft: (id: string) =>
    apiRequest<MessageDraft | null>(`/conversations/${id}/draft`, {}, true),
  saveDraft: (id: string, body: string) =>
    apiRequest<MessageDraft>(
      `/conversations/${id}/draft`,
      { method: 'PUT', body: JSON.stringify({ body }) },
      true,
    ),
  saveMessage: (id: string, note?: string) =>
    apiRequest(
      `/messages/${id}/save`,
      { method: 'POST', body: JSON.stringify({ note: note ?? null }) },
      true,
    ),
  savedMessages: () =>
    apiRequest<Array<Record<string, unknown>>>('/saved-messages', {}, true),
  read: (id: string, messageId: string) =>
    apiRequest(
      `/conversations/${id}/read`,
      { method: 'PUT', body: JSON.stringify({ message_id: messageId }) },
      true,
    ),
  presence: () =>
    apiRequest<Array<Record<string, unknown>>>('/presence', {}, true),
  setPresence: (status: string) =>
    apiRequest(
      '/presence',
      { method: 'PUT', body: JSON.stringify({ status }) },
      true,
    ),
  socket: (conversationId: string) => {
    const token = currentAccessToken()
    if (!token) return null
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return new WebSocket(
      `${protocol}//${window.location.hostname}:8000/api/v1/chat/ws/${conversationId}?token=${encodeURIComponent(token)}`,
    )
  },
}
