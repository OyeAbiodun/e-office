import { apiRawRequest, apiRequest } from '@/features/auth/api'

export type ReportType =
  'employee' | 'team' | 'department' | 'project' | 'management'
export type PeriodType = 'daily' | 'weekly' | 'monthly' | 'custom'

export interface ReportPolicy {
  id: string
  organization_id: string
  daily_enabled: boolean
  weekly_enabled: boolean
  monthly_enabled: boolean
  review_before_send: boolean
  automatic_submit: boolean
  week_start: number
  week_end: number
  generation_time: string
  submission_deadline_hours: number
  manager_review_required: boolean
  reminder_hours_before: number
  timezone: string
  enabled_report_types: PeriodType[]
  updated_at: string
}

export interface GeneratedReport {
  id: string
  report_type: ReportType
  subject_type: ReportType
  subject_id: string | null
  subject_name: string
  owner_id: string | null
  manager_id: string | null
  period_type: PeriodType
  period_start: string
  period_end: string
  timezone: string
  status: string
  submission_mode: string | null
  version: number
  authoritative_snapshot: Record<string, unknown>
  narrative: Record<string, unknown>
  source_refs: Array<Record<string, unknown>>
  policy_snapshot: Record<string, unknown>
  reviewer_id: string | null
  review_comment: string | null
  return_reason: string | null
  generated_at: string
  submitted_at: string | null
  submission_reminder_sent_at: string | null
  reviewed_at: string | null
  finalized_at: string | null
}

export interface ReportDetail {
  report: GeneratedReport
  versions: Array<{
    id: string
    version: number
    snapshot: Record<string, unknown>
    narrative: Record<string, unknown>
    created_at: string
  }>
  history: Array<{
    id: string
    actor_id: string | null
    action: string
    note: string | null
    created_at: string
  }>
}

export interface ReportingDashboard {
  pending_my_review: number
  awaiting_manager_review: number
  returned: number
  finalized_this_period: number
  reporting_compliance_percent: number
  active_projects: number
  projects_at_risk: number
  open_tasks: number
  overdue_tasks: number
  unresolved_blockers: number
  department_activity: Array<{ department: string; activities: number }>
}

const query = (values: Record<string, string | number | undefined>) => {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return params.size ? `?${params}` : ''
}

export const reportsApi = {
  dashboard: () =>
    apiRequest<ReportingDashboard>('/reports/dashboard', {}, true),
  list: (filters: Record<string, string | number | undefined> = {}) =>
    apiRequest<{
      items: GeneratedReport[]
      total: number
      page: number
      page_size: number
      total_pages: number
    }>(`/reports${query(filters)}`, {}, true),
  detail: (id: string) => apiRequest<ReportDetail>(`/reports/${id}`, {}, true),
  preview: (startDate: string, endDate: string) =>
    apiRequest<{
      snapshot: Record<string, unknown>
      source_refs: Array<Record<string, unknown>>
    }>(
      `/reports/source-preview${query({ start_date: startDate, end_date: endDate })}`,
      {},
      true,
    ),
  generate: (body: {
    report_type: ReportType
    subject_id: string | null
    period_type: PeriodType
    period_start: string
    period_end: string
  }) =>
    apiRequest<GeneratedReport>(
      '/reports',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  edit: (id: string, body: Record<string, string>) =>
    apiRequest<GeneratedReport>(
      `/reports/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  submit: (id: string) =>
    apiRequest<GeneratedReport>(
      `/reports/${id}/submit`,
      { method: 'POST' },
      true,
    ),
  review: (id: string, action: 'accept' | 'return', comment?: string) =>
    apiRequest<GeneratedReport>(
      `/reports/${id}/review`,
      { method: 'POST', body: JSON.stringify({ action, comment }) },
      true,
    ),
  policy: () => apiRequest<ReportPolicy>('/reports/policy', {}, true),
  updatePolicy: (
    body: Omit<ReportPolicy, 'id' | 'organization_id' | 'updated_at'>,
  ) =>
    apiRequest<ReportPolicy>(
      '/reports/policy',
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  export: async (id: string, format: 'pdf' | 'csv' | 'xlsx') => {
    const response = await apiRawRequest(
      `/reports/${id}/export?format=${format}`,
      {},
    )
    if (!response.ok) throw new Error('Report export could not be prepared')
    return response.blob()
  },
}
