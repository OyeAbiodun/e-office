import { apiRequest } from '@/features/auth/api'

export interface Notification {
  id: string
  meeting_id: string | null
  notification_type: string
  category: string
  priority: string
  title: string
  body: string
  action_url: string | null
  delivered_at: string
  read_at: string | null
  archived_at: string | null
  notification_metadata: Record<string, unknown>
}

export interface NotificationSummary {
  unread: number
  mentions: number
  meetings: number
  approvals: number
  tasks: number
  total: number
  page: number
  page_size: number
  total_pages: number
  next_cursor: string | null
  notifications: Notification[]
}

export interface NotificationPreferences {
  in_app_enabled: boolean
  email_enabled: boolean
  browser_enabled: boolean
  quiet_hours_enabled: boolean
  quiet_hours_start: string | null
  quiet_hours_end: string | null
  timezone: string
  category_rules: Record<string, unknown>
  delivery_rules: Record<string, unknown>
  updated_at: string
}

export interface PushSubscriptionRecord {
  id: string
  endpoint: string
  enabled: boolean
  created_at: string
  last_used_at: string | null
}

export const notificationApi = {
  list: () => apiRequest<NotificationSummary>('/notifications', {}, true),
  listFiltered: (query: string) =>
    apiRequest<NotificationSummary>(
      `/notifications${query ? `?${query}` : ''}`,
      {},
      true,
    ),
  markRead: (id: string) =>
    apiRequest<Notification>(
      `/notifications/${id}/read`,
      { method: 'POST' },
      true,
    ),
  markAllRead: () =>
    apiRequest<{ updated: number }>(
      '/notifications/read-all',
      { method: 'POST' },
      true,
    ),
  bulk: (notification_ids: string[], action: 'read' | 'archive') =>
    apiRequest<{ updated: number }>(
      '/notifications/actions/bulk',
      {
        method: 'POST',
        body: JSON.stringify({ notification_ids, action }),
      },
      true,
    ),
  archive: (id: string) =>
    apiRequest<Notification>(
      `/notifications/${id}/archive`,
      { method: 'POST' },
      true,
    ),
  preferences: () =>
    apiRequest<NotificationPreferences>(
      '/notifications/preferences/me',
      {},
      true,
    ),
  updatePreferences: (body: Partial<NotificationPreferences>) =>
    apiRequest<NotificationPreferences>(
      '/notifications/preferences/me',
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  pushSubscriptions: () =>
    apiRequest<PushSubscriptionRecord[]>(
      '/notifications/push-subscriptions',
      {},
      true,
    ),
  savePushSubscription: (body: {
    endpoint: string
    p256dh: string
    auth: string
    user_agent?: string
  }) =>
    apiRequest<PushSubscriptionRecord>(
      '/notifications/push-subscriptions',
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  revokePushSubscription: (id: string) =>
    apiRequest<void>(
      `/notifications/push-subscriptions/${id}`,
      { method: 'DELETE' },
      true,
    ),
}
