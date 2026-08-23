import { apiRequest } from '@/features/auth/api'

export type HealthState =
  'healthy' | 'degraded' | 'unavailable' | 'not_configured'

export interface ComponentHealth {
  key: string
  name: string
  category: string
  status: HealthState
  requirement: 'required' | 'recommended' | 'optional' | 'configured'
  configured: boolean
  message: string
  latency_ms: number | null
  details: Record<string, unknown>
}

export interface SystemHealth {
  status: HealthState
  score: number
  required_healthy: number
  required_total: number
  checked_at: string
  last_updated: string
  version: string
  environment: string
  uptime_seconds: number
  components: ComponentHealth[]
  queue: { pending: number; failed: number; delivered: number }
  warnings: string[]
  errors: string[]
  recommendations: string[]
}

export interface HealthHistoryPoint {
  score: number
  status: string
  checked_at: string
  incidents: number
}

export const systemHealthApi = {
  snapshot: () => apiRequest<SystemHealth>('/system-health', {}, true),
  history: () =>
    apiRequest<HealthHistoryPoint[]>(
      '/system-health/history?limit=96',
      {},
      true,
    ),
}
