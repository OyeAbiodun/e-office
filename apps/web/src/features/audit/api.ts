import { apiRawRequest, apiRequest } from '@/features/auth/api'

export interface AuditRecord {
  id: string
  organization_id: string | null
  user_id: string | null
  user_name: string
  action: string
  category: string
  resource: string
  resource_id: string | null
  request_id: string | null
  ip_address: string | null
  browser: string | null
  device: string | null
  metadata: Record<string, unknown>
  created_at: string
}

export interface AuditPage {
  items: AuditRecord[]
  total: number
  next_cursor: string | null
  categories: string[]
  actions: string[]
}

export interface AuditFilters {
  search?: string
  category?: string
  action?: string
  from_date?: string
  to_date?: string
}

const params = (filters: AuditFilters) => {
  const search = new URLSearchParams()
  Object.entries(filters).forEach(
    ([key, value]) => value && search.set(key, value),
  )
  return search.toString()
}

export const auditApi = {
  list: (filters: AuditFilters) =>
    apiRequest<AuditPage>(`/audit?${params(filters)}`, {}, true),
  async export(filters: AuditFilters) {
    const response = await apiRawRequest(`/audit/export?${params(filters)}`)
    return response.blob()
  },
}
