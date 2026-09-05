import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Clock3, ListChecks, Plus, Sparkles } from 'lucide-react'
import { type FormEvent, type ReactNode, useMemo, useState } from 'react'

import { tasksApi, type Task, type TaskPriority, type TaskStatus } from './api'
import { useAuth } from '@/features/auth/auth-store'
import { userAdminApi } from '@/features/users/api'

const statuses: Array<[TaskStatus, string]> = [
  ['not_started', 'Not started'],
  ['in_progress', 'In progress'],
  ['blocked', 'Blocked'],
  ['awaiting_review', 'Awaiting review'],
  ['completed', 'Completed'],
  ['cancelled', 'Cancelled'],
]
const priorities: TaskPriority[] = ['low', 'normal', 'high', 'urgent']

export function TasksPage() {
  const client = useQueryClient()
  const { user } = useAuth()
  const permissions = new Set(user?.permissions ?? [])
  const [scope, setScope] = useState('mine')
  const [due, setDue] = useState<string | undefined>('today')
  const [status, setStatus] = useState<string | undefined>()
  const [priority, setPriority] = useState<string | undefined>()
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showActivity, setShowActivity] = useState(false)
  const [selected, setSelected] = useState<Task | null>(null)
  const [page, setPage] = useState(1)
  const todayDate = new Date().toISOString().slice(0, 10)
  const weekStart = new Date()
  weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7))
  const weekStartDate = weekStart.toISOString().slice(0, 10)
  const filters = useMemo(
    () => ({ scope, due, status, priority, search, page, page_size: 25 }),
    [due, page, priority, scope, search, status],
  )
  const tasks = useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => tasksApi.list(filters),
  })
  const people = useQuery({
    queryKey: ['task-assignees'],
    queryFn: () =>
      userAdminApi.employees({
        status: 'active',
        employment_status: 'active',
        page: 1,
        page_size: 100,
      }),
  })
  const dailySummary = useQuery({
    queryKey: ['task-daily-summary', todayDate],
    queryFn: () => tasksApi.dailySummary(todayDate),
  })
  const weeklySummary = useQuery({
    queryKey: ['task-weekly-summary', weekStartDate],
    queryFn: () => tasksApi.weeklySummary(weekStartDate),
  })
  const refresh = () => void client.invalidateQueries({ queryKey: ['tasks'] })
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      tasksApi.update(id, body),
    onSuccess: refresh,
  })
  const create = useMutation({
    mutationFn: tasksApi.create,
    onSuccess: () => {
      setShowCreate(false)
      refresh()
    },
  })
  const activity = useMutation({
    mutationFn: tasksApi.recordActivity,
    onSuccess: () => {
      setShowActivity(false)
      void client.invalidateQueries({ queryKey: ['task-activities'] })
      void client.invalidateQueries({ queryKey: ['task-daily-summary'] })
      void client.invalidateQueries({ queryKey: ['task-weekly-summary'] })
    },
  })
  const rows = tasks.data?.items ?? []
  const overdue = rows.filter((task) => task.is_overdue).length
  const today = rows.filter((task) => task.due_date === todayDate).length
  const scopeTabs = [
    ['mine', 'Today'],
    ['assigned', 'Assigned to me'],
    ['created', 'Created by me'],
    ...(permissions.has('tasks.view_team') || permissions.has('tasks.manage')
      ? [['team', 'My team']]
      : []),
    ...(permissions.has('tasks.view_department') ||
    permissions.has('tasks.manage')
      ? [['department', 'Department work']]
      : []),
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-5 sm:p-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-primary">Work management</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            My Work
          </h1>
          <p className="mt-2 text-muted-foreground">
            Focus on the work that needs attention, then capture the outcome.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold"
            onClick={() => setShowActivity(true)}
            type="button"
          >
            Log today
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
            onClick={() => setShowCreate(true)}
            type="button"
          >
            <Plus className="size-4" /> New task
          </button>
        </div>
      </header>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={Clock3} label="Due today" value={today} />
        <Metric
          icon={ListChecks}
          label="Open work"
          value={
            rows.filter(
              (task) => !['completed', 'cancelled'].includes(task.status),
            ).length
          }
        />
        <Metric
          icon={Sparkles}
          label="Overdue"
          value={overdue}
          tone={overdue ? 'danger' : undefined}
        />
        <Metric
          icon={CheckCircle2}
          label="Completed"
          value={rows.filter((task) => task.status === 'completed').length}
        />
      </section>
      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Today’s summary</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Live work, activity, and meeting signals.
              </p>
            </div>
            <Clock3 className="size-5 text-primary" />
          </div>
          {dailySummary.data ? (
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <SummaryStat
                label="Completed"
                value={dailySummary.data.completed_tasks}
              />
              <SummaryStat
                label="In progress"
                value={dailySummary.data.in_progress_tasks}
              />
              <SummaryStat
                label="Activities"
                value={dailySummary.data.activities.length}
              />
              <SummaryStat
                label="Meetings"
                value={dailySummary.data.meetings_attended}
              />
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">
              Summary unavailable.
            </p>
          )}
          {dailySummary.data?.blockers.length ? (
            <p className="mt-4 rounded-xl bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
              {dailySummary.data.blockers.length} blocker
              {dailySummary.data.blockers.length === 1 ? '' : 's'} recorded
              today.
            </p>
          ) : null}
        </article>
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold">This week</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                A concise view of your workload.
              </p>
            </div>
            <ListChecks className="size-5 text-primary" />
          </div>
          {weeklySummary.data ? (
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <SummaryStat
                label="Done"
                value={weeklySummary.data.completed_tasks}
              />
              <SummaryStat
                label="Open"
                value={weeklySummary.data.pending_tasks}
              />
              <SummaryStat
                label="Overdue"
                value={weeklySummary.data.overdue_tasks}
              />
              <SummaryStat
                label="Logged"
                value={`${weeklySummary.data.activity_minutes}m`}
              />
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">
              Weekly summary unavailable.
            </p>
          )}
        </article>
      </section>
      <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="flex flex-col gap-3 border-b p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2" aria-label="Task scope">
            {scopeTabs.map(([key, label]) => (
              <button
                className={`rounded-lg px-3 py-2 text-sm font-medium ${scope === key ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/70'}`}
                key={key}
                onClick={() => {
                  setScope(key)
                  setPage(1)
                }}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              aria-label="Search tasks"
              className="h-10 rounded-lg border bg-background px-3 text-sm"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search work"
              value={search}
            />
            <select
              aria-label="Filter task status"
              className="h-10 rounded-lg border bg-background px-2 text-sm"
              onChange={(event) => setStatus(event.target.value || undefined)}
              value={status ?? ''}
            >
              <option value="">All statuses</option>
              {statuses.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter task priority"
              className="h-10 rounded-lg border bg-background px-2 text-sm"
              onChange={(event) => setPriority(event.target.value || undefined)}
              value={priority ?? ''}
            >
              <option value="">All priorities</option>
              {priorities.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter due date"
              className="h-10 rounded-lg border bg-background px-2 text-sm"
              onChange={(event) => setDue(event.target.value || undefined)}
              value={due ?? ''}
            >
              <option value="">All dates</option>
              <option value="today">Today</option>
              <option value="week">This week</option>
              <option value="overdue">Overdue</option>
            </select>
          </div>
        </div>
        {tasks.isLoading ? (
          <div className="space-y-3 p-5" aria-label="Loading tasks">
            {[1, 2, 3].map((row) => (
              <div
                className="h-16 animate-pulse rounded-xl bg-muted"
                key={row}
              />
            ))}
          </div>
        ) : tasks.isError ? (
          <div className="p-10 text-center" role="alert">
            <p className="font-semibold">Your work could not be loaded.</p>
            <button
              className="mt-3 text-sm font-semibold text-primary"
              onClick={() => void tasks.refetch()}
              type="button"
            >
              Retry
            </button>
          </div>
        ) : rows.length ? (
          <div className="divide-y">
            {rows.map((task) => (
              <TaskRow
                key={task.id}
                onOpen={() => setSelected(task)}
                onStatus={(next) =>
                  update.mutate({ id: task.id, body: { status: next } })
                }
                task={task}
              />
            ))}
          </div>
        ) : (
          <div className="p-12 text-center">
            <Sparkles className="mx-auto size-8 text-primary" />
            <h2 className="mt-3 font-semibold">You’re all caught up</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              No work matches these filters.
            </p>
            <button
              className="mt-4 text-sm font-semibold text-primary"
              onClick={() => setShowCreate(true)}
              type="button"
            >
              Create a task
            </button>
          </div>
        )}
        {tasks.data && tasks.data.total_pages > 1 && (
          <div className="flex items-center justify-between border-t p-4 text-sm">
            <p className="text-muted-foreground">
              Page {tasks.data.page} of {tasks.data.total_pages} ·{' '}
              {tasks.data.total} tasks
            </p>
            <div className="flex gap-2">
              <button
                className="rounded-lg border px-3 py-1.5 font-semibold disabled:opacity-50"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                type="button"
              >
                Previous
              </button>
              <button
                className="rounded-lg border px-3 py-1.5 font-semibold disabled:opacity-50"
                disabled={page >= tasks.data.total_pages}
                onClick={() => setPage((current) => current + 1)}
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
      {showCreate && (
        <TaskForm
          people={people.data?.items ?? []}
          onClose={() => setShowCreate(false)}
          onSave={(body) => create.mutate(body)}
        />
      )}
      {showActivity && (
        <ActivityForm
          tasks={rows}
          onClose={() => setShowActivity(false)}
          onSave={(body) => activity.mutate(body)}
        />
      )}
      {selected && (
        <TaskDetail
          task={selected}
          onClose={() => setSelected(null)}
          onUpdate={(body) => update.mutate({ id: selected.id, body })}
        />
      )}
    </div>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Clock3
  label: string
  value: number
  tone?: 'danger'
}) {
  return (
    <article className="rounded-2xl border bg-card p-4 shadow-sm">
      <Icon className={`size-5 ${tone ? 'text-red-600' : 'text-primary'}`} />
      <p className="mt-4 text-2xl font-semibold">{value}</p>
      <p className="text-sm text-muted-foreground">{label}</p>
    </article>
  )
}

function SummaryStat({
  label,
  value,
}: {
  label: string
  value: number | string
}) {
  return (
    <div className="rounded-xl bg-muted/60 p-3">
      <p className="text-lg font-semibold">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  )
}

function TaskRow({
  task,
  onOpen,
  onStatus,
}: {
  task: Task
  onOpen: () => void
  onStatus: (status: TaskStatus) => void
}) {
  return (
    <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
      <button
        className="min-w-0 flex-1 text-left"
        onClick={onOpen}
        type="button"
      >
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-semibold">{task.title}</p>
          {task.is_overdue && (
            <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-700">
              {task.overdue_days}d overdue
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {task.assignee_name ?? 'Unassigned'} ·{' '}
          {task.due_date
            ? `Due ${new Date(task.due_date).toLocaleDateString()}`
            : 'No due date'}
          {task.meeting_title ? ` · ${task.meeting_title}` : ''}
        </p>
      </button>
      <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-semibold capitalize">
        {task.priority}
      </span>
      <select
        aria-label={`Update ${task.title} status`}
        className="h-9 rounded-lg border bg-background px-2 text-sm"
        onChange={(event) => onStatus(event.target.value as TaskStatus)}
        value={task.status}
      >
        {statuses.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </div>
  )
}
function TaskForm({
  people,
  onClose,
  onSave,
}: {
  people: Array<{ id: string; display_name: string; job_title: string | null }>
  onClose: () => void
  onSave: (body: Record<string, unknown>) => void
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    onSave({
      title: form.get('title'),
      description: form.get('description') || undefined,
      due_date: form.get('due_date') || undefined,
      priority: form.get('priority'),
      assignee_id: form.get('assignee_id') || undefined,
      reminder_at: form.get('reminder_at')
        ? new Date(String(form.get('reminder_at'))).toISOString()
        : undefined,
    })
  }
  return (
    <Dialog title="New task" onClose={onClose}>
      <form className="space-y-4" onSubmit={submit}>
        <label className="block text-sm font-medium">
          Title
          <input
            autoFocus
            className="mt-1 w-full rounded-lg border bg-background p-2"
            name="title"
            required
          />
        </label>
        <label className="block text-sm font-medium">
          Description
          <textarea
            className="mt-1 min-h-20 w-full rounded-lg border bg-background p-2"
            name="description"
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Due date
            <input
              className="mt-1 w-full rounded-lg border bg-background p-2"
              name="due_date"
              type="date"
            />
          </label>
          <label className="text-sm font-medium">
            Priority
            <select
              className="mt-1 w-full rounded-lg border bg-background p-2"
              defaultValue="normal"
              name="priority"
            >
              {priorities.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
        </div>
        <details>
          <summary className="cursor-pointer text-sm font-semibold text-primary">
            Assignment and reminder
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Assign to
              <select
                className="mt-1 w-full rounded-lg border bg-background p-2"
                name="assignee_id"
              >
                <option value="">Myself</option>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.display_name}
                    {person.job_title ? ` · ${person.job_title}` : ''}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Reminder
              <input
                className="mt-1 w-full rounded-lg border bg-background p-2"
                name="reminder_at"
                type="datetime-local"
              />
            </label>
          </div>
        </details>
        <DialogActions onClose={onClose} />
      </form>
    </Dialog>
  )
}
function ActivityForm({
  tasks,
  onClose,
  onSave,
}: {
  tasks: Task[]
  onClose: () => void
  onSave: (body: Record<string, unknown>) => void
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    onSave({
      activity_date: new Date().toISOString().slice(0, 10),
      summary: form.get('summary'),
      task_id: form.get('task_id') || undefined,
      duration_minutes: form.get('duration_minutes')
        ? Number(form.get('duration_minutes'))
        : undefined,
      blockers: form.get('blockers') || undefined,
      next_step: form.get('next_step') || undefined,
    })
  }
  return (
    <Dialog title="What did you work on today?" onClose={onClose}>
      <form className="space-y-4" onSubmit={submit}>
        <label className="block text-sm font-medium">
          Summary
          <textarea
            autoFocus
            className="mt-1 min-h-24 w-full rounded-lg border bg-background p-2"
            name="summary"
            required
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Related task
            <select
              className="mt-1 w-full rounded-lg border bg-background p-2"
              name="task_id"
            >
              <option value="">None</option>
              {tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Minutes spent
            <input
              className="mt-1 w-full rounded-lg border bg-background p-2"
              min="1"
              name="duration_minutes"
              type="number"
            />
          </label>
        </div>
        <label className="block text-sm font-medium">
          Blockers
          <textarea
            className="mt-1 min-h-16 w-full rounded-lg border bg-background p-2"
            name="blockers"
          />
        </label>
        <label className="block text-sm font-medium">
          Next step
          <input
            className="mt-1 w-full rounded-lg border bg-background p-2"
            name="next_step"
          />
        </label>
        <DialogActions onClose={onClose} />
      </form>
    </Dialog>
  )
}
function TaskDetail({
  task,
  onClose,
  onUpdate,
}: {
  task: Task
  onClose: () => void
  onUpdate: (body: Record<string, unknown>) => void
}) {
  const detail = useQuery({
    queryKey: ['task', task.id],
    queryFn: () => tasksApi.get(task.id),
  })
  const [comment, setComment] = useState('')
  const client = useQueryClient()
  const commentMutation = useMutation({
    mutationFn: () => tasksApi.comment(task.id, comment),
    onSuccess: () => {
      setComment('')
      void client.invalidateQueries({ queryKey: ['task', task.id] })
    },
  })
  return (
    <Dialog title={`Task #${task.sequence}`} onClose={onClose}>
      <div className="space-y-5">
        <div>
          <h2 className="text-xl font-semibold">{task.title}</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
            {task.description || 'No description provided.'}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Info label="Assignee" value={task.assignee_name ?? '—'} />
          <Info label="Due" value={task.due_date ?? '—'} />
          <Info label="Priority" value={task.priority} />
          <Info
            label="Progress"
            value={task.progress === null ? 'Not set' : `${task.progress}%`}
          />
        </div>
        <label className="block text-sm font-medium">
          Progress
          <input
            className="mt-1 w-full"
            max="100"
            min="0"
            onChange={(event) =>
              onUpdate({ progress: Number(event.target.value) })
            }
            type="range"
            value={task.progress ?? 0}
          />
        </label>
        <section>
          <h3 className="font-semibold">Activity</h3>
          <div className="mt-2 max-h-40 space-y-2 overflow-auto text-sm">
            {detail.data?.history.map((item) => (
              <p key={item.id}>
                <span className="font-medium">
                  {item.actor_name ?? 'System'}
                </span>{' '}
                {item.event_type.replaceAll('_', ' ')}{' '}
                <span className="text-muted-foreground">
                  · {new Date(item.created_at).toLocaleString()}
                </span>
              </p>
            ))}
          </div>
        </section>
        <section>
          <h3 className="font-semibold">Comments</h3>
          <div className="mt-2 space-y-2">
            {detail.data?.comments.map((item) => (
              <div className="rounded-lg bg-muted p-3 text-sm" key={item.id}>
                <span className="font-medium">{item.author_name}</span>
                <p className="mt-1">{item.body}</p>
              </div>
            ))}
          </div>
          <form
            className="mt-3 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              if (comment.trim()) commentMutation.mutate()
            }}
          >
            <input
              aria-label="Add task comment"
              className="min-w-0 flex-1 rounded-lg border bg-background p-2 text-sm"
              onChange={(event) => setComment(event.target.value)}
              placeholder="Add an update"
              value={comment}
            />
            <button
              className="rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground"
              type="submit"
            >
              Send
            </button>
          </form>
        </section>
      </div>
    </Dialog>
  )
}
function Dialog({
  title,
  children,
  onClose,
}: {
  title: string
  children: ReactNode
  onClose: () => void
}) {
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-end bg-black/40 p-0 sm:place-items-center sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="max-h-[92vh] w-full max-w-xl overflow-auto rounded-t-2xl bg-card p-5 shadow-2xl sm:rounded-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            aria-label="Close dialog"
            className="rounded-lg p-2 hover:bg-muted"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
function DialogActions({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex justify-end gap-2">
      <button
        className="rounded-lg px-4 py-2 text-sm font-semibold hover:bg-muted"
        onClick={onClose}
        type="button"
      >
        Cancel
      </button>
      <button
        className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
        type="submit"
      >
        Save
      </button>
    </div>
  )
}
function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-medium capitalize">{value}</p>
    </div>
  )
}
