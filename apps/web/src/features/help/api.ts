import { apiRequest } from '@/features/auth/api'

export interface HelpArticle {
  id: string
  slug: string
  title: string
  summary: string
  category: string
  required_permission: string | null
  content: string
  version: number
  position: number
  published: boolean
  workflow_status: 'draft' | 'review' | 'published' | 'archived'
  search_weight: number
  context_ids: string[]
  keywords: string[]
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

export interface HelpAnalytics {
  total_articles: number
  published_articles: number
  total_views: number
  unique_readers: number
  favorite_count: number
  popular_articles: Array<{ slug: string; title: string; views: number }>
}

export interface HelpAttachment {
  id: string
  filename: string
  content_type: string
  size: number
  url: string
  created_at: string
}

export interface HelpArticleDraft {
  slug: string
  title: string
  summary: string
  category: string
  required_permission: string | null
  content: string
  workflow_status: HelpArticle['workflow_status']
  search_weight: number
  context_ids: string[]
  keywords: string[]
  related_slugs: string[]
  video_metadata: Record<string, unknown> | null
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
  articles: (search = '', includeUnpublished = false) =>
    apiRequest<HelpArticle[]>(
      `/help/articles?${new URLSearchParams({
        ...(search ? { search } : {}),
        ...(includeUnpublished ? { include_unpublished: 'true' } : {}),
      })}`,
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
  analytics: () => apiRequest<HelpAnalytics>('/help/analytics', {}, true),
  versions: (slug: string) =>
    apiRequest<HelpArticle[]>(
      `/help/articles/${encodeURIComponent(slug)}/versions`,
      {},
      true,
    ),
  createArticle: (body: HelpArticleDraft) =>
    apiRequest<HelpArticle>(
      '/help/articles',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  reviseArticle: (slug: string, body: Omit<HelpArticleDraft, 'slug'>) =>
    apiRequest<HelpArticle>(
      `/help/articles/${encodeURIComponent(slug)}/revisions`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  attachments: (articleId: string) =>
    apiRequest<HelpAttachment[]>(
      `/help/articles/${articleId}/attachments`,
      {},
      true,
    ),
  uploadAttachment: (articleId: string, file: File) => {
    const body = new FormData()
    body.append('upload', file)
    return apiRequest<HelpAttachment>(
      `/help/articles/${articleId}/attachments`,
      { method: 'POST', body },
      true,
    )
  },
}
