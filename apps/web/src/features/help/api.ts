import { apiRequest } from '@/features/auth/api'

export interface HelpArticle {
  id: string
  slug: string
  title: string
  summary: string
  category: string
  content: string
  version: number
  position: number
  published: boolean
  workflow_status: 'draft' | 'review' | 'published' | 'archived'
  search_weight: number
  context_ids: string[]
  related_slugs: string[]
  video_metadata: Record<string, unknown> | null
  updated_at: string
}

export interface ProductTour {
  id: string
  context_id: string
  title: string
  description: string
  steps: Array<{
    title?: string
    body?: string
    selector?: string
  }>
  version: number
  enabled: boolean
  updated_at: string
}

export interface HelpContext {
  context_id: string
  article: HelpArticle | null
  tour: ProductTour | null
}

export interface SupportRequest {
  id: string
  reference: string
  request_type: 'help' | 'issue' | 'feature' | 'administration'
  priority: 'low' | 'normal' | 'high' | 'urgent'
  subject: string
  description: string
  status: string
  page_url: string | null
  module: string | null
  created_at: string
  updated_at: string
}

export const helpApi = {
  articles: (search = '') =>
    apiRequest<HelpArticle[]>(
      `/help/articles${search ? `?search=${encodeURIComponent(search)}` : ''}`,
      {},
      true,
    ),
  article: (slug: string) =>
    apiRequest<HelpArticle>(`/help/articles/${slug}`, {}, true),
  context: (contextId: string) =>
    apiRequest<HelpContext>(
      `/help/context/${encodeURIComponent(contextId)}`,
      {},
      true,
    ),
  favorites: () => apiRequest<HelpArticle[]>('/help/favorites', {}, true),
  recent: () => apiRequest<HelpArticle[]>('/help/recent', {}, true),
  toggleFavorite: (articleId: string) =>
    apiRequest<{ favorite: boolean }>(
      `/help/articles/${articleId}/favorite`,
      { method: 'POST' },
      true,
    ),
  supportRequests: () =>
    apiRequest<SupportRequest[]>('/help/support', {}, true),
  createSupportRequest: (body: {
    request_type: SupportRequest['request_type']
    priority: SupportRequest['priority']
    subject: string
    description: string
    page_url?: string
    module?: string
    diagnostics?: Record<string, unknown>
  }) =>
    apiRequest<SupportRequest>(
      '/help/support',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
}
