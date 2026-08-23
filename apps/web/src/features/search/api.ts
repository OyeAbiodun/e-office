import { apiRequest } from '@/features/auth/api'

export type SearchResultType =
  | 'navigation'
  | 'meeting'
  | 'user'
  | 'team'
  | 'role'
  | 'mail'
  | 'notification'
  | 'help'
  | 'audit'
  | 'integration'

export interface SearchResult {
  id: string
  type: SearchResultType
  title: string
  subtitle: string
  url: string
  icon: string
  score: number
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  total: number
}

export const searchApi = {
  search: (query: string) =>
    apiRequest<SearchResponse>(
      `/search?q=${encodeURIComponent(query)}&limit=30`,
      {},
      true,
    ),
}
