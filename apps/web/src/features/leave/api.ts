import { apiRawRequest, apiRequest } from '@/features/auth/api'

export type LeaveStatus =
  'draft' | 'submitted' | 'approved' | 'rejected' | 'withdrawn' | 'cancelled'

export interface LeaveType {
  id: string
  name: string
  code: string
  description: string | null
  is_active: boolean
  is_paid: boolean
  default_entitlement: number
  accrual_enabled: boolean
  accrual_frequency: 'monthly' | 'quarterly' | 'yearly' | null
  carryover_enabled: boolean
  carryover_limit: number | null
  carryover_expiry_months: number | null
  minimum_notice_days: number
  maximum_consecutive_days: number | null
  attachment_required: boolean
  half_day_supported: boolean
  eligible_employment_types: string | null
  probation_eligible: boolean
  color: string | null
}

export interface LeavePeriod {
  id: string
  name: string
  start_date: string
  end_date: string
  status: 'open' | 'closed'
}

export interface LeaveBalance {
  entitlement_id: string
  employee_id: string
  leave_type_id: string
  leave_period_id: string
  entitled: number
  accrued: number
  carried_forward: number
  adjustments: number
  used: number
  pending: number
  expired: number
  available: number
  available_after_pending: number
}

export interface LeaveBalanceRow extends LeaveBalance {
  employee_number: string | null
  employee_name: string
  department_id: string | null
  department_name: string | null
  leave_type_name: string
  leave_type_code: string
  period_name: string
}

export interface LeaveRequest {
  id: string
  employee_id: string
  employee_number: string | null
  employee_name: string | null
  department_id: string | null
  department_name: string | null
  leave_type_id: string
  leave_type_name: string | null
  leave_type_code: string | null
  leave_period_id: string
  leave_period_name: string | null
  start_date: string
  end_date: string
  duration_days: number
  half_day: boolean
  reason: string | null
  status: LeaveStatus
  reviewed_by_id: string | null
  reviewed_at: string | null
  review_comment: string | null
  calendar_event_id: string | null
  created_at: string
  updated_at: string
}

export interface LeaveAttachment {
  id: string
  filename: string
  content_type: string
  size: number
  uploaded_by_id: string
  created_at: string
}

export interface LeaveRequestDetail extends LeaveRequest {
  employee_name: string
  manager_id: string | null
  manager_name: string | null
  leave_type_name: string
  leave_type_code: string
  leave_period_name: string
  reviewer_name: string | null
  balance_effect: number
  attachments: LeaveAttachment[]
  history: Array<{
    id: string
    actor_id: string | null
    event_type: string
    comment: string | null
    created_at: string
  }>
}

export interface LeavePage<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface WorkingDayPreview {
  calendar_span: number
  excluded_non_working_days: number
  excluded_holidays: number
  chargeable_days: number
}

export interface LeaveSummary {
  balances: LeaveBalance[]
  pending_requests: LeaveRequest[]
  upcoming_approved: LeaveRequest[]
  recent_history: LeaveRequest[]
}

export interface AwayPerson {
  employee_id: string
  employee_name: string
  start_date: string
  end_date: string
  status: 'away'
}

export interface ManagerSummary {
  pending_count: number
  pending: LeaveRequest[]
  away_today: AwayPerson[]
  upcoming: AwayPerson[]
  recently_reviewed: LeaveRequest[]
}

export interface LedgerEntry {
  id: string
  employee_id: string
  leave_type_id: string
  leave_period_id: string
  entry_type: string
  amount: number
  effective_date: string
  reason: string | null
  reference_id: string | null
  actor_id: string | null
  actor_name: string | null
  created_at: string
}

export interface AdjustmentResult {
  previous_balance: LeaveBalance
  adjustment: LedgerEntry
  resulting_balance: LeaveBalance
}

export interface LeaveReportRow {
  key: string
  label: string
  request_count: number
  total_days: number
}

export interface LeaveStatusSummary {
  status: string
  request_count: number
  total_days: number
}

export interface WorkingWeek {
  weekdays: number[]
  exclude_holidays: boolean
}

type QueryValue = string | number | boolean | null | undefined

function query(values: Record<string, QueryValue>) {
  const parameters = new URLSearchParams()
  for (const [key, value] of Object.entries(values))
    if (value !== undefined && value !== null && value !== '')
      parameters.set(key, String(value))
  return parameters.size ? `?${parameters}` : ''
}

async function download(path: string, fallbackName: string) {
  const response = await apiRawRequest(path)
  const blob = await response.blob()
  const disposition = response.headers.get('content-disposition')
  const filename =
    disposition?.match(/filename="?([^";]+)"?/i)?.[1] ?? fallbackName
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export const leaveApi = {
  types: (filters: { search?: string; active?: boolean } = {}) =>
    apiRequest<LeaveType[]>(`/leave/types${query(filters)}`, {}, true),
  createType: (body: Record<string, unknown>) =>
    apiRequest<LeaveType>(
      '/leave/types',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateType: (id: string, body: Record<string, unknown>) =>
    apiRequest<LeaveType>(
      `/leave/types/${id}`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  setTypeActive: (id: string, active: boolean) =>
    apiRequest<LeaveType>(
      `/leave/types/${id}/active${query({ active })}`,
      { method: 'PATCH' },
      true,
    ),
  periods: () => apiRequest<LeavePeriod[]>('/leave/periods', {}, true),
  createPeriod: (body: Record<string, unknown>) =>
    apiRequest<LeavePeriod>(
      '/leave/periods',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  setPeriodStatus: (id: string, status: 'open' | 'closed') =>
    apiRequest<LeavePeriod>(
      `/leave/periods/${id}/status`,
      { method: 'PATCH', body: JSON.stringify({ status }) },
      true,
    ),
  mySummary: () => apiRequest<LeaveSummary>('/leave/my/summary', {}, true),
  requests: (filters: Record<string, QueryValue>) =>
    apiRequest<LeavePage<LeaveRequest>>(
      `/leave/requests${query(filters)}`,
      {},
      true,
    ),
  request: (id: string) =>
    apiRequest<LeaveRequestDetail>(`/leave/requests/${id}`, {}, true),
  preview: (body: {
    start_date: string
    end_date: string
    half_day: boolean
  }) =>
    apiRequest<WorkingDayPreview>(
      '/leave/working-days',
      { method: 'POST', body: JSON.stringify(body) },
      true,
      false,
    ),
  createRequest: (body: Record<string, unknown>) =>
    apiRequest<LeaveRequest>(
      '/leave/requests',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  submit: (id: string) =>
    apiRequest<LeaveRequest>(
      `/leave/requests/${id}/submit`,
      { method: 'POST' },
      true,
    ),
  approve: (id: string, comment?: string) =>
    apiRequest<LeaveRequest>(
      `/leave/requests/${id}/approve`,
      { method: 'POST', body: JSON.stringify({ comment: comment || null }) },
      true,
    ),
  reject: (id: string, comment: string) =>
    apiRequest<LeaveRequest>(
      `/leave/requests/${id}/reject`,
      { method: 'POST', body: JSON.stringify({ comment }) },
      true,
    ),
  withdraw: (id: string) =>
    apiRequest<LeaveRequest>(
      `/leave/requests/${id}/withdraw`,
      { method: 'POST' },
      true,
    ),
  cancel: (id: string, comment?: string) =>
    apiRequest<LeaveRequest>(
      `/leave/requests/${id}/cancel`,
      { method: 'POST', body: JSON.stringify({ comment: comment || null }) },
      true,
    ),
  uploadAttachment: (requestId: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return apiRequest<LeaveAttachment>(
      `/leave/requests/${requestId}/attachments`,
      { method: 'POST', body },
      true,
    )
  },
  removeAttachment: (requestId: string, attachmentId: string) =>
    apiRequest(
      `/leave/requests/${requestId}/attachments/${attachmentId}`,
      { method: 'DELETE' },
      true,
    ),
  downloadAttachment: (requestId: string, attachment: LeaveAttachment) =>
    download(
      `/leave/requests/${requestId}/attachments/${attachment.id}/download`,
      attachment.filename,
    ),
  managerSummary: () =>
    apiRequest<ManagerSummary>('/leave/team/summary', {}, true),
  availability: (startDate: string, endDate: string) =>
    apiRequest<AwayPerson[]>(
      `/leave/team/availability${query({ start_date: startDate, end_date: endDate })}`,
      {},
      true,
    ),
  balances: (filters: Record<string, QueryValue>) =>
    apiRequest<LeavePage<LeaveBalanceRow>>(
      `/leave/balances${query(filters)}`,
      {},
      true,
    ),
  ledger: (filters: Record<string, QueryValue>) =>
    apiRequest<LeavePage<LedgerEntry>>(
      `/leave/ledger${query(filters)}`,
      {},
      true,
    ),
  adjust: (body: Record<string, unknown>) =>
    apiRequest<AdjustmentResult>(
      '/leave/adjustments',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  workingWeek: () =>
    apiRequest<WorkingWeek>('/leave/policy/working-week', {}, true),
  updateWorkingWeek: (body: WorkingWeek) =>
    apiRequest<WorkingWeek>(
      '/leave/policy/working-week',
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  usageReport: (groupBy: 'department' | 'leave_type') =>
    apiRequest<LeaveReportRow[]>(
      `/leave/reports/usage${query({ group_by: groupBy })}`,
      {},
      true,
    ),
  statusReport: (category: 'pending' | 'current' | 'upcoming' | 'all') =>
    apiRequest<LeaveStatusSummary[]>(
      `/leave/reports/status${query({ category })}`,
      {},
      true,
    ),
  exportRequests: (filters: Record<string, QueryValue> = {}) =>
    download(
      `/leave/exports/requests.csv${query(filters)}`,
      'leave-requests.csv',
    ),
  exportBalances: (filters: Record<string, QueryValue> = {}) =>
    download(
      `/leave/exports/balances.csv${query(filters)}`,
      'leave-balances.csv',
    ),
  exportUsage: (groupBy: 'department' | 'leave_type') =>
    download(
      `/leave/exports/usage.csv${query({ group_by: groupBy })}`,
      `leave-usage-${groupBy}.csv`,
    ),
}
