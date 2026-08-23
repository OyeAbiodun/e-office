import { apiRequest } from '@/features/auth/api'

export interface DashboardData {
  organization_name: string
  widgets: Array<{ id: string; label: string; value: number | string }>
  recent_activity: Array<{
    id: string
    event_type: string
    subject_type: string
    occurred_at: string
    payload: Record<string, unknown>
  }>
  quick_actions: string[]
}

export const getDashboard = () =>
  apiRequest<DashboardData>('/dashboard', {}, true)
