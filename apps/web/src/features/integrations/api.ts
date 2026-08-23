import { apiRequest } from '@/features/auth/api'

export type IntegrationHealth = 'healthy' | 'attention' | 'disabled'

export interface IntegrationProvider {
  key: string
  name: string
  category: string
  description: string
  auth_type: string
  enabled: boolean
  configured: boolean
  validated: boolean
  health: IntegrationHealth
  updated_at: string | null
  last_tested_at: string | null
}

export interface IntegrationTestResult {
  key: string
  status: 'healthy' | 'attention'
  message: string
  latency_ms: number
  checked_at: string
}

export interface IntegrationAudit {
  action: string
  status: string
  created_at: string
  actor_id: string | null
}

export const integrationApi = {
  list: () => apiRequest<IntegrationProvider[]>('/integrations', {}, true),
  configure: (key: string, values: Record<string, unknown>) =>
    apiRequest<IntegrationProvider>(
      `/integrations/${key}`,
      { method: 'PUT', body: JSON.stringify({ values }) },
      true,
    ),
  disconnect: (key: string) =>
    apiRequest<{ key: string; configured: boolean; message: string }>(
      `/integrations/${key}`,
      { method: 'DELETE' },
      true,
    ),
  test: (key: string) =>
    apiRequest<IntegrationTestResult>(
      `/integrations/${key}/test`,
      { method: 'POST' },
      true,
    ),
  synchronize: (key: string) =>
    apiRequest<{ key: string; configured: boolean; message: string }>(
      `/integrations/${key}/synchronize`,
      { method: 'POST' },
      true,
    ),
  audit: (key: string) =>
    apiRequest<IntegrationAudit[]>(`/integrations/${key}/audit`, {}, true),
}
