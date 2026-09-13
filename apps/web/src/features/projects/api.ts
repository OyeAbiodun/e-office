import { apiRawRequest, apiRequest } from '@/features/auth/api'
import type { Task } from '@/features/tasks/api'

export interface ProjectSummary {
  id: string
  project_code: string
  name: string
  description: string | null
  project_manager_id: string
  department_id: string | null
  start_date: string | null
  target_end_date: string | null
  actual_end_date: string | null
  status: string
  priority: string
  health: string
  progress: number
  visibility: string
  archived_at: string | null
  created_at: string
  manager_name: string | null
  department_name: string | null
  member_count: number
  task_count: number
  completed_task_count: number
  overdue_task_count: number
  milestone_count: number
  open_risk_count: number
  open_issue_count: number
}

export interface ProjectMember {
  id: string
  user_id: string
  role: string
  display_name: string | null
  job_title: string | null
  avatar_url: string | null
}

export interface Milestone {
  id: string
  name: string
  description: string | null
  start_date: string | null
  target_date: string | null
  completion_date: string | null
  status: string
  owner_id: string | null
  owner_name: string | null
  progress: number
  sequence: number
}

export interface ProjectDetail {
  project: ProjectSummary
  members: ProjectMember[]
  milestones: Milestone[]
  updates: Array<
    Record<string, unknown> & {
      id: string
      reporting_date: string
      summary: string
    }
  >
  risks: Array<
    Record<string, unknown> & {
      id: string
      title: string
      status: string
      severity: string
    }
  >
  issues: Array<
    Record<string, unknown> & {
      id: string
      title: string
      status: string
      severity: string
    }
  >
  attachments: Array<{
    id: string
    filename: string
    content_type: string
    size: number
    created_at: string
  }>
  meetings: Array<{
    id: string
    title: string
    start_datetime: string
    status: string
  }>
  activity: Array<{
    id: string
    event_type: string
    created_at: string
    payload: Record<string, unknown>
  }>
}

export interface ProjectReport {
  project: ProjectSummary
  start_date: string
  end_date: string
  executive_summary: string
  milestones: Milestone[]
  tasks_total: number
  tasks_completed: number
  tasks_overdue: number
  activities: Array<Record<string, unknown>>
  updates: ProjectDetail['updates']
  risks: ProjectDetail['risks']
  issues: ProjectDetail['issues']
  meetings: ProjectDetail['meetings']
  upcoming_deadlines: Array<Record<string, unknown>>
  generated_at: string
}

function query(values: Record<string, string | number | boolean | undefined>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return params.size ? `?${params}` : ''
}

export const projectsApi = {
  list: (filters: Record<string, string | number | boolean | undefined> = {}) =>
    apiRequest<{
      items: ProjectSummary[]
      total: number
      page: number
      page_size: number
      total_pages: number
    }>(`/projects${query(filters)}`, {}, true),
  get: (id: string) => apiRequest<ProjectDetail>(`/projects/${id}`, {}, true),
  create: (body: Record<string, unknown>) =>
    apiRequest<ProjectSummary>(
      '/projects',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  update: (id: string, body: Record<string, unknown>) =>
    apiRequest<ProjectSummary>(
      `/projects/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  addMember: (id: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/members`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateMember: (id: string, memberId: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/members/${memberId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  removeMember: (id: string, memberId: string) =>
    apiRequest(
      `/projects/${id}/members/${memberId}`,
      { method: 'DELETE' },
      true,
    ),
  addMilestone: (id: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/milestones`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateMilestone: (
    id: string,
    milestoneId: string,
    body: Record<string, unknown>,
  ) =>
    apiRequest(
      `/projects/${id}/milestones/${milestoneId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  removeMilestone: (id: string, milestoneId: string) =>
    apiRequest(
      `/projects/${id}/milestones/${milestoneId}`,
      { method: 'DELETE' },
      true,
    ),
  createTask: (id: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/tasks`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  tasks: (id: string) => apiRequest<Task[]>(`/projects/${id}/tasks`, {}, true),
  addUpdate: (id: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/updates`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  addRisk: (id: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/risks`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateRisk: (id: string, riskId: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/risks/${riskId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  addIssue: (id: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/issues`,
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateIssue: (id: string, issueId: string, body: Record<string, unknown>) =>
    apiRequest(
      `/projects/${id}/issues/${issueId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  report: (id: string, startDate: string, endDate: string) =>
    apiRequest<ProjectReport>(
      `/projects/${id}/report${query({ start_date: startDate, end_date: endDate })}`,
      {},
      true,
    ),
  upload: async (id: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return apiRequest(
      `/projects/${id}/attachments`,
      { method: 'POST', body },
      true,
    )
  },
  download: async (id: string, attachmentId: string, filename: string) => {
    const response = await apiRawRequest(
      `/projects/${id}/attachments/${attachmentId}/download`,
    )
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  },
  removeAttachment: (id: string, attachmentId: string) =>
    apiRequest(
      `/projects/${id}/attachments/${attachmentId}`,
      { method: 'DELETE' },
      true,
    ),
}
