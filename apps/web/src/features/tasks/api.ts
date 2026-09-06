import { apiRequest } from '@/features/auth/api'

export type TaskStatus =
  | 'not_started'
  | 'in_progress'
  | 'blocked'
  | 'awaiting_review'
  | 'completed'
  | 'cancelled'
export type TaskPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface Task {
  id: string
  sequence: number
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  progress: number | null
  assignee_id: string
  created_by_id: string
  assigned_by_id: string | null
  department_id: string | null
  team_id: string | null
  meeting_id: string | null
  meeting_action_item_id: string | null
  start_date: string | null
  due_date: string | null
  completed_at: string | null
  reminder_at: string | null
  follow_up_at: string | null
  tags: string[]
  created_at: string
  updated_at: string
  is_overdue: boolean
  overdue_days: number
  assignee_name: string | null
  department_name: string | null
  meeting_title: string | null
}

export interface TaskPage {
  items: Task[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface TaskAssignee {
  id: string
  display_name: string
  job_title: string | null
  department_id: string | null
  department_name: string | null
}

export interface TaskDetail {
  task: Task
  comments: Array<{
    id: string
    author_id: string
    author_name: string | null
    body: string
    created_at: string
  }>
  history: Array<{
    id: string
    event_type: string
    actor_name: string | null
    payload: Record<string, unknown>
    created_at: string
  }>
  attachments: Array<{
    id: string
    filename: string
    content_type: string
    size: number
    url: string
    uploaded_by_id: string
    created_at: string
  }>
  checklist: TaskChecklistItem[]
}

export interface TaskChecklistItem {
  id: string
  title: string
  position: number
  completed_at: string | null
  completed_by_id: string | null
  created_at: string
  updated_at: string
}

export interface DailyActivity {
  id: string
  activity_date: string
  summary: string
  task_id: string | null
  meeting_id: string | null
  duration_minutes: number | null
  outcome: string | null
  blockers: string | null
  next_step: string | null
  visibility: string
  user_name: string | null
}

export interface DailySummary {
  date: string
  completed_tasks: number
  in_progress_tasks: number
  overdue_tasks: number
  activities: DailyActivity[]
  blockers: string[]
  meetings_attended: number
  upcoming_due: number
}

export interface WeeklySummary {
  start_date: string
  end_date: string
  completed_tasks: number
  pending_tasks: number
  overdue_tasks: number
  activity_count: number
  activity_minutes: number
  meetings_attended: number
  upcoming_due: number
  workload: Array<{
    user_id: string
    display_name: string
    open_tasks: number
    overdue_tasks: number
    blocked_tasks: number
    completed_this_week: number
    activity_count: number
  }>
}

function query(values: Record<string, string | number | undefined>) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values))
    if (value !== undefined && value !== '') params.set(key, String(value))
  return params.toString() ? `?${params.toString()}` : ''
}

export const tasksApi = {
  list: (filters: Record<string, string | number | undefined> = {}) =>
    apiRequest<TaskPage>(`/tasks${query(filters)}`, {}, true),
  get: (id: string) => apiRequest<TaskDetail>(`/tasks/${id}`, {}, true),
  assignees: () => apiRequest<TaskAssignee[]>('/tasks/assignees', {}, true),
  create: (body: Record<string, unknown>) =>
    apiRequest<Task>(
      '/tasks',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  update: (id: string, body: Record<string, unknown>) =>
    apiRequest<Task>(
      `/tasks/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  archive: (id: string) =>
    apiRequest(`/tasks/${id}`, { method: 'DELETE' }, true),
  comment: (id: string, body: string) =>
    apiRequest(
      `/tasks/${id}/comments`,
      {
        method: 'POST',
        body: JSON.stringify({ body }),
      },
      true,
    ),
  uploadAttachment: async (id: string, file: File) => {
    const data = new FormData()
    data.append('file', file)
    return apiRequest(
      `/tasks/${id}/attachments`,
      { method: 'POST', body: data },
      true,
    )
  },
  deleteAttachment: (id: string, attachmentId: string) =>
    apiRequest(
      `/tasks/${id}/attachments/${attachmentId}`,
      { method: 'DELETE' },
      true,
    ),
  addChecklist: (id: string, title: string) =>
    apiRequest<TaskChecklistItem>(
      `/tasks/${id}/checklist`,
      { method: 'POST', body: JSON.stringify({ title }) },
      true,
    ),
  updateChecklist: (
    id: string,
    itemId: string,
    body: Record<string, unknown>,
  ) =>
    apiRequest<TaskChecklistItem>(
      `/tasks/${id}/checklist/${itemId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  deleteChecklist: (id: string, itemId: string) =>
    apiRequest(`/tasks/${id}/checklist/${itemId}`, { method: 'DELETE' }, true),
  createFromAction: (actionId: string) =>
    apiRequest<Task>(
      `/tasks/from-meeting-action/${actionId}`,
      { method: 'POST' },
      true,
    ),
  activities: () => apiRequest<DailyActivity[]>('/tasks/activities', {}, true),
  dailySummary: (summaryDate: string) =>
    apiRequest<DailySummary>(
      `/tasks/summary/daily${query({ summary_date: summaryDate })}`,
      {},
      true,
    ),
  weeklySummary: (startDate: string) =>
    apiRequest<WeeklySummary>(
      `/tasks/summary/weekly${query({ start_date: startDate })}`,
      {},
      true,
    ),
  recordActivity: (body: Record<string, unknown>) =>
    apiRequest<DailyActivity>(
      '/tasks/activities',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
}
