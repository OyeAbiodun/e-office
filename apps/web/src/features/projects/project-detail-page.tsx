import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { AlertTriangle, FileText, Plus } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'

import { type ProjectDetail, type ProjectReport, projectsApi } from './api'
import { Badge, Dialog, Field } from './projects-page'
import { useConfirmation } from '@/components/feedback/confirmation'
import { useAuth } from '@/features/auth/auth-store'
import { tasksApi } from '@/features/tasks/api'

const tabs = [
  'overview',
  'tasks',
  'milestones',
  'team',
  'activity',
  'updates',
  'risks',
  'issues',
  'meetings',
  'files',
  'reports',
] as const
type Tab = (typeof tabs)[number]
type Action =
  | 'task'
  | 'milestone'
  | 'member'
  | 'update'
  | 'risk'
  | 'issue'
  | 'file'
  | 'report'
  | null
const title = (value: string) =>
  value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

export function ProjectDetailPage() {
  const { projectId } = useParams({ strict: false }) as { projectId: string }
  const { user } = useAuth()
  const confirm = useConfirmation()
  const permissions = new Set(user?.permissions ?? [])
  const client = useQueryClient()
  const [tab, setTab] = useState<Tab>('overview')
  const [action, setAction] = useState<Action>(null)
  const [report, setReport] = useState<ProjectReport | null>(null)
  const detail = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId),
  })
  const projectTasks = useQuery({
    queryKey: ['tasks', 'project', projectId],
    queryFn: () => projectsApi.tasks(projectId),
    enabled: tab === 'tasks' || tab === 'overview',
  })
  const people = useQuery({
    queryKey: ['project-people'],
    queryFn: tasksApi.assignees,
  })
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['project', projectId] })
    void client.invalidateQueries({ queryKey: ['projects'] })
    void client.invalidateQueries({ queryKey: ['tasks'] })
  }
  const mutation = useMutation({
    mutationFn: ({
      type,
      body,
    }: {
      type: Exclude<Action, null>
      body: Record<string, unknown>
    }) => {
      if (type === 'task') return projectsApi.createTask(projectId, body)
      if (type === 'milestone') return projectsApi.addMilestone(projectId, body)
      if (type === 'member') return projectsApi.addMember(projectId, body)
      if (type === 'update') return projectsApi.addUpdate(projectId, body)
      if (type === 'risk') return projectsApi.addRisk(projectId, body)
      if (type === 'issue') return projectsApi.addIssue(projectId, body)
      throw new Error('Unsupported action')
    },
    onSuccess: () => {
      setAction(null)
      refresh()
    },
  })
  const status = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      projectsApi.update(projectId, body),
    onSuccess: refresh,
  })

  if (detail.isLoading)
    return (
      <div className="space-y-4 p-8" aria-label="Loading project">
        <div className="h-24 animate-pulse rounded-2xl bg-muted" />
        <div className="h-72 animate-pulse rounded-2xl bg-muted" />
      </div>
    )
  if (detail.isError || !detail.data)
    return (
      <div className="p-8" role="alert">
        <h1 className="text-xl font-semibold">Project unavailable</h1>
        <p className="mt-2 text-muted-foreground">
          It may not exist or you may not have access.
        </p>
        <Link
          className="mt-4 inline-block text-primary underline"
          to="/projects"
        >
          Return to Projects
        </Link>
      </div>
    )
  const data = detail.data
  const project = data.project
  const canManage =
    permissions.has('projects.edit') || project.project_manager_id === user?.id

  return (
    <main className="w-full space-y-6 p-4 sm:p-6 lg:p-8">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <Link to="/projects" className="hover:text-foreground">
          Projects
        </Link>
        <span className="mx-2">/</span>
        <span aria-current="page">{project.project_code}</span>
      </nav>
      <header className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge value={project.status} />
              <Badge value={project.health} />
              <span className="text-sm text-muted-foreground">
                {project.project_code}
              </span>
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">
              {project.name}
            </h1>
            <p className="mt-2 max-w-4xl text-muted-foreground">
              {project.description ||
                'No project description has been added yet.'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canManage && (
              <>
                <button
                  className="rounded-xl border px-4 py-2.5"
                  onClick={() => setAction('update')}
                >
                  Post update
                </button>
                <button
                  className="rounded-xl bg-primary px-4 py-2.5 font-semibold text-primary-foreground"
                  onClick={() => setAction('task')}
                >
                  <Plus className="mr-1 inline" size={17} /> Add task
                </button>
              </>
            )}
            <a
              className="rounded-xl border px-4 py-2.5"
              href={`/meetings/new?project_id=${project.id}`}
            >
              Schedule meeting
            </a>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Progress" value={`${project.progress}%`} />
          <Stat
            label="Project manager"
            value={project.manager_name ?? 'Unassigned'}
          />
          <Stat
            label="Target end"
            value={project.target_end_date ?? 'Not set'}
          />
          <Stat
            label="Open attention"
            value={`${project.open_risk_count} risks · ${project.open_issue_count} issues`}
          />
        </div>
      </header>

      <nav
        aria-label="Project sections"
        className="flex gap-1 overflow-x-auto rounded-xl border bg-card p-1"
      >
        {tabs.map((item) => (
          <button
            key={item}
            aria-current={tab === item ? 'page' : undefined}
            className={`min-h-10 whitespace-nowrap rounded-lg px-3 text-sm font-medium ${tab === item ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
            onClick={() => setTab(item)}
          >
            {title(item)}
          </button>
        ))}
      </nav>

      {tab === 'overview' && (
        <Overview
          project={project}
          tasks={projectTasks.data ?? []}
          milestones={data.milestones}
          updates={data.updates}
        />
      )}
      {tab === 'tasks' && (
        <TaskSection
          tasks={projectTasks.data ?? []}
          loading={projectTasks.isLoading}
          canManage={canManage}
          onAdd={() => setAction('task')}
        />
      )}
      {tab === 'milestones' && (
        <Collection
          title="Milestones"
          empty="No milestones yet"
          canAdd={canManage}
          onAdd={() => setAction('milestone')}
        >
          {data.milestones.map((item) => (
            <article key={item.id} className="rounded-xl border p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <strong>{item.name}</strong>
                  <p className="text-sm text-muted-foreground">
                    {item.owner_name ?? 'No owner'} · Target{' '}
                    {item.target_date ?? 'not set'}
                  </p>
                </div>
                <Badge value={item.status} />
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <span
                  className="block h-full bg-primary"
                  style={{ width: `${item.progress}%` }}
                />
              </div>
            </article>
          ))}
        </Collection>
      )}
      {tab === 'team' && (
        <Collection
          title="Project team"
          empty="No project members"
          canAdd={
            permissions.has('projects.manage_members') ||
            project.project_manager_id === user?.id
          }
          onAdd={() => setAction('member')}
        >
          {data.members.map((member) => (
            <article
              key={member.id}
              className="flex items-center justify-between rounded-xl border p-4"
            >
              <div>
                <strong>{member.display_name}</strong>
                <p className="text-sm text-muted-foreground">
                  {member.job_title || 'Employee'}
                </p>
              </div>
              <Badge value={member.role} />
            </article>
          ))}
        </Collection>
      )}
      {tab === 'activity' && (
        <Collection title="Project activity" empty="No project activity yet">
          {data.activity.map((item) => (
            <article
              key={item.id}
              className="flex items-start justify-between gap-4 rounded-xl border p-4"
            >
              <div>
                <strong>{title(item.event_type)}</strong>
                <p className="mt-1 text-sm text-muted-foreground">
                  {String(item.payload.name ?? project.name)}
                </p>
              </div>
              <time className="text-xs text-muted-foreground">
                {new Date(item.created_at).toLocaleString()}
              </time>
            </article>
          ))}
        </Collection>
      )}
      {tab === 'updates' && (
        <Collection
          title="Project updates"
          empty="No structured updates in this project"
          canAdd={canManage}
          onAdd={() => setAction('update')}
        >
          {data.updates.map((item) => (
            <article key={item.id} className="rounded-xl border p-4">
              <div className="flex justify-between gap-3">
                <strong>{item.reporting_date}</strong>
                <span className="text-sm text-muted-foreground">
                  {String(item.author_name ?? '')}
                </span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm">{item.summary}</p>
              {Boolean(item.blockers) && (
                <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">
                  <strong>Blockers:</strong> {String(item.blockers)}
                </p>
              )}
            </article>
          ))}
        </Collection>
      )}
      {tab === 'risks' && (
        <Collection
          title="Risks"
          empty="No risks recorded"
          canAdd={
            permissions.has('projects.manage_risks') ||
            project.project_manager_id === user?.id
          }
          onAdd={() => setAction('risk')}
        >
          {data.risks.map((item) => (
            <Attention key={item.id} kind="Risk" item={item} />
          ))}
        </Collection>
      )}
      {tab === 'issues' && (
        <Collection
          title="Issues"
          empty="No issues recorded"
          canAdd={
            permissions.has('projects.manage_issues') ||
            project.project_manager_id === user?.id
          }
          onAdd={() => setAction('issue')}
        >
          {data.issues.map((item) => (
            <Attention key={item.id} kind="Issue" item={item} />
          ))}
        </Collection>
      )}
      {tab === 'meetings' && (
        <Collection
          title="Linked meetings"
          empty="No meetings are linked to this project"
        >
          {data.meetings.map((meeting) => (
            <Link
              key={meeting.id}
              to="/meetings/$meetingId"
              params={{ meetingId: meeting.id }}
              className="flex items-center justify-between rounded-xl border p-4 hover:bg-muted"
            >
              <div>
                <strong>{meeting.title}</strong>
                <p className="text-sm text-muted-foreground">
                  {new Date(meeting.start_datetime).toLocaleString()}
                </p>
              </div>
              <Badge value={meeting.status} />
            </Link>
          ))}
        </Collection>
      )}
      {tab === 'files' && (
        <Files
          projectId={project.id}
          rows={data.attachments}
          canManage={
            permissions.has('projects.manage_files') ||
            project.project_manager_id === user?.id
          }
          refresh={refresh}
        />
      )}
      {tab === 'reports' && (
        <Reports
          report={report}
          canGenerate={
            permissions.has('projects.generate_reports') ||
            project.project_manager_id === user?.id
          }
          onGenerate={() => setAction('report')}
        />
      )}

      {action && (
        <ActionDialog
          action={action}
          milestones={data.milestones}
          people={people.data ?? []}
          pending={mutation.isPending}
          error={mutation.error}
          onClose={() => setAction(null)}
          onSubmit={(body) => mutation.mutate({ type: action, body })}
          onReport={async (startDate, endDate) => {
            const value = await projectsApi.report(
              project.id,
              startDate,
              endDate,
            )
            setReport(value)
            setAction(null)
            setTab('reports')
          }}
        />
      )}
      {canManage && (
        <section className="flex flex-wrap items-center gap-3 rounded-2xl border bg-card p-4">
          <span className="text-sm font-semibold">Lifecycle</span>
          {project.status === 'draft' && (
            <button onClick={() => status.mutate({ status: 'planned' })}>
              Plan project
            </button>
          )}
          {project.status === 'planned' && (
            <button onClick={() => status.mutate({ status: 'active' })}>
              Start project
            </button>
          )}
          {project.status === 'active' && (
            <>
              <button onClick={() => status.mutate({ status: 'on_hold' })}>
                Put on hold
              </button>
              <button
                onClick={async () => {
                  const approved = await confirm({
                    title: 'Complete project?',
                    description:
                      'Open tasks, critical issues, or milestones require an explicit completion decision. Project history will be preserved.',
                    confirmLabel: 'Complete project',
                  })
                  if (approved)
                    status.mutate({
                      status: 'completed',
                      completion_override: true,
                    })
                }}
              >
                Complete
              </button>
            </>
          )}
          {project.status === 'on_hold' && (
            <button onClick={() => status.mutate({ status: 'active' })}>
              Resume
            </button>
          )}
          {project.status === 'completed' && (
            <button
              onClick={async () => {
                const approved = await confirm({
                  title: 'Archive completed project?',
                  description:
                    'The project becomes read-only but remains reportable with all history and files intact.',
                  confirmLabel: 'Archive project',
                })
                if (approved) status.mutate({ status: 'archived' })
              }}
            >
              Archive
            </button>
          )}
          <select
            aria-label="Project health"
            value={project.health}
            onChange={(event) => status.mutate({ health: event.target.value })}
          >
            <option value="on_track">On Track</option>
            <option value="at_risk">At Risk</option>
            <option value="off_track">Off Track</option>
            <option value="completed" disabled={project.status !== 'completed'}>
              Completed
            </option>
          </select>
          {status.isPending && (
            <span className="text-sm text-muted-foreground">Updating…</span>
          )}
          {status.error && (
            <span className="text-sm text-destructive" role="alert">
              {status.error.message}
            </span>
          )}
        </section>
      )}
    </main>
  )
}

function Overview({
  project,
  tasks,
  milestones,
  updates,
}: {
  project: ProjectDetail['project']
  tasks: Awaited<ReturnType<typeof projectsApi.tasks>>
  milestones: ProjectDetail['milestones']
  updates: ProjectDetail['updates']
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[2fr_1fr]">
      <section className="rounded-2xl border bg-card p-5">
        <h2 className="text-lg font-semibold">Delivery snapshot</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Tasks" value={String(project.task_count)} />
          <Stat
            label="Completed"
            value={String(project.completed_task_count)}
          />
          <Stat label="Overdue" value={String(project.overdue_task_count)} />
          <Stat label="Milestones" value={String(project.milestone_count)} />
        </div>
        <h3 className="mt-6 font-semibold">Work requiring attention</h3>
        <div className="mt-3 space-y-2">
          {tasks
            .filter((task) => task.is_overdue || task.status === 'blocked')
            .slice(0, 5)
            .map((task) => (
              <div
                key={task.id}
                className="flex justify-between rounded-xl bg-muted/50 p-3"
              >
                <span>{task.title}</span>
                <Badge value={task.is_overdue ? 'overdue' : task.status} />
              </div>
            ))}
          {!tasks.some(
            (task) => task.is_overdue || task.status === 'blocked',
          ) && (
            <p className="text-sm text-muted-foreground">
              No overdue or blocked project tasks.
            </p>
          )}
        </div>
      </section>
      <aside className="rounded-2xl border bg-card p-5">
        <h2 className="text-lg font-semibold">Next milestones</h2>
        <div className="mt-3 space-y-3">
          {milestones
            .filter((item) => item.status !== 'completed')
            .slice(0, 4)
            .map((item) => (
              <div key={item.id}>
                <strong className="text-sm">{item.name}</strong>
                <p className="text-xs text-muted-foreground">
                  {item.target_date ?? 'No target date'} · {item.progress}%
                </p>
              </div>
            ))}
          {!milestones.length && (
            <p className="text-sm text-muted-foreground">No milestones yet.</p>
          )}
        </div>
        <h2 className="mt-6 text-lg font-semibold">Latest update</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {updates[0]?.summary ?? 'No update has been posted.'}
        </p>
      </aside>
    </div>
  )
}

function TaskSection({
  tasks,
  loading,
  canManage,
  onAdd,
}: {
  tasks: Awaited<ReturnType<typeof projectsApi.tasks>>
  loading: boolean
  canManage: boolean
  onAdd: () => void
}) {
  return (
    <Collection
      title="Project tasks"
      empty="No tasks linked to this project"
      canAdd={canManage}
      onAdd={onAdd}
    >
      {loading ? (
        <div className="h-32 animate-pulse rounded-xl bg-muted" />
      ) : (
        tasks.map((task) => (
          <article
            key={task.id}
            className="grid gap-2 rounded-xl border p-4 sm:grid-cols-[1fr_auto_auto] sm:items-center"
          >
            <div>
              <strong>{task.title}</strong>
              <p className="text-sm text-muted-foreground">
                {task.assignee_name ?? 'Unassigned'} · Due{' '}
                {task.due_date ?? 'not set'}
              </p>
            </div>
            <Badge value={task.priority} />
            <Badge value={task.status} />
          </article>
        ))
      )}
    </Collection>
  )
}

function Collection({
  title: sectionTitle,
  empty,
  canAdd = false,
  onAdd,
  children,
}: {
  title: string
  empty: string
  canAdd?: boolean
  onAdd?: () => void
  children: ReactNode
}) {
  const list = Array.isArray(children) ? children : [children]
  return (
    <section className="rounded-2xl border bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">{sectionTitle}</h2>
        {canAdd && (
          <button
            className="rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground"
            onClick={onAdd}
          >
            <Plus className="mr-1 inline" size={16} />
            Add
          </button>
        )}
      </div>
      <div className="grid gap-3">
        {list.length ? (
          children
        ) : (
          <p className="py-10 text-center text-muted-foreground">{empty}</p>
        )}
      </div>
    </section>
  )
}
function Attention({
  kind,
  item,
}: {
  kind: string
  item: ProjectDetail['risks'][number] | ProjectDetail['issues'][number]
}) {
  return (
    <article className="flex items-start justify-between gap-4 rounded-xl border p-4">
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 text-amber-600" size={18} />
        <div>
          <strong>{item.title}</strong>
          <p className="text-sm text-muted-foreground">
            {kind} · {title(item.severity)} severity
          </p>
        </div>
      </div>
      <Badge value={item.status} />
    </article>
  )
}
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-muted/50 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <strong className="mt-1 block">{value}</strong>
    </div>
  )
}

function Files({
  projectId,
  rows,
  canManage,
  refresh,
}: {
  projectId: string
  rows: ProjectDetail['attachments']
  canManage: boolean
  refresh: () => void
}) {
  const upload = useMutation({
    mutationFn: (file: File) => projectsApi.upload(projectId, file),
    onSuccess: refresh,
  })
  return (
    <Collection title="Project files" empty="No project documents uploaded">
      <>
        {canManage && (
          <label className="mb-2 inline-flex cursor-pointer items-center gap-2 rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground">
            <Plus size={16} />
            Upload file
            <input
              className="sr-only"
              type="file"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) upload.mutate(file)
              }}
            />
          </label>
        )}
        {rows.map((row) => (
          <article
            key={row.id}
            className="flex items-center justify-between rounded-xl border p-4"
          >
            <div className="flex items-center gap-3">
              <FileText size={18} />
              <div>
                <strong>{row.filename}</strong>
                <p className="text-xs text-muted-foreground">
                  {Math.ceil(row.size / 1024)} KB
                </p>
              </div>
            </div>
            <button
              className="text-sm font-semibold text-primary"
              onClick={() =>
                void projectsApi.download(projectId, row.id, row.filename)
              }
            >
              Download
            </button>
          </article>
        ))}
      </>
    </Collection>
  )
}

function Reports({
  report,
  canGenerate,
  onGenerate,
}: {
  report: ProjectReport | null
  canGenerate: boolean
  onGenerate: () => void
}) {
  if (!report)
    return (
      <Collection
        title="Project status report"
        empty="Choose a reporting period to generate a data-backed status report"
        canAdd={canGenerate}
        onAdd={onGenerate}
      >
        {[]}
      </Collection>
    )
  return (
    <section className="rounded-2xl border bg-card p-5 print:border-0">
      <div className="flex justify-between gap-3 print:hidden">
        <div>
          <h2 className="text-xl font-semibold">Project status report</h2>
          <p className="text-sm text-muted-foreground">
            {report.start_date} – {report.end_date}
          </p>
        </div>
        <button
          className="rounded-xl border px-3 py-2"
          onClick={() => window.print()}
        >
          Print / Save PDF
        </button>
      </div>
      <div className="mt-6 space-y-6">
        <ReportSection title="Executive summary">
          {report.executive_summary}
        </ReportSection>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Tasks in period" value={String(report.tasks_total)} />
          <Stat label="Completed" value={String(report.tasks_completed)} />
          <Stat label="Overdue" value={String(report.tasks_overdue)} />
        </div>
        <ReportSection title="Milestone status">
          {report.milestones
            .map(
              (item) =>
                `${item.name}: ${title(item.status)} (${item.progress}%)`,
            )
            .join('\n') || 'No milestones'}
        </ReportSection>
        <ReportSection title="Work completed during period">
          {report.updates
            .map((item) => String(item.accomplishments ?? item.summary))
            .join('\n\n') || 'No structured updates for this period.'}
        </ReportSection>
        <ReportSection title="Issues and risks">
          {[
            ...report.issues.map((item) => `Issue: ${item.title}`),
            ...report.risks.map((item) => `Risk: ${item.title}`),
          ].join('\n') || 'No open issues or risks.'}
        </ReportSection>
        <ReportSection title="Next actions">
          {report.updates
            .map((item) => String(item.next_steps ?? ''))
            .filter(Boolean)
            .join('\n') || 'No next actions recorded.'}
        </ReportSection>
      </div>
    </section>
  )
}
function ReportSection({
  title: sectionTitle,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section>
      <h3 className="font-semibold">{sectionTitle}</h3>
      <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
        {children}
      </p>
    </section>
  )
}

function ActionDialog({
  action,
  milestones,
  people,
  pending,
  error,
  onClose,
  onSubmit,
  onReport,
}: {
  action: Exclude<Action, null>
  milestones: ProjectDetail['milestones']
  people: Awaited<ReturnType<typeof tasksApi.assignees>>
  pending: boolean
  error: Error | null
  onClose: () => void
  onSubmit: (body: Record<string, unknown>) => void
  onReport: (start: string, end: string) => Promise<void>
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    if (action === 'report') {
      void onReport(
        String(data.get('start_date')),
        String(data.get('end_date')),
      )
      return
    }
    const body = Object.fromEntries(
      [...data.entries()].map(([key, value]) => [key, value || null]),
    )
    onSubmit(body)
  }
  const today = new Date().toISOString().slice(0, 10)
  return (
    <Dialog
      title={
        action === 'report' ? 'Generate project report' : `Add ${title(action)}`
      }
      onClose={onClose}
    >
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={submit}>
        {action === 'task' && (
          <>
            <Field label="Task title" wide>
              <input name="title" required />
            </Field>
            <Field label="Assignee">
              <select name="assignee_id" required>
                <option value="">Select employee</option>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.display_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Milestone">
              <select name="milestone_id">
                <option value="">No milestone</option>
                {milestones.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Due date">
              <input name="due_date" type="date" />
            </Field>
            <Field label="Priority">
              <select name="priority" defaultValue="normal">
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </Field>
            <Field label="Description" wide>
              <textarea name="description" rows={4} />
            </Field>
          </>
        )}
        {action === 'milestone' && (
          <>
            <Field label="Milestone name" wide>
              <input name="name" required />
            </Field>
            <Field label="Start date">
              <input name="start_date" type="date" />
            </Field>
            <Field label="Target date">
              <input name="target_date" type="date" />
            </Field>
            <Field label="Owner">
              <select name="owner_id">
                <option value="">No owner</option>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.display_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Description" wide>
              <textarea name="description" rows={4} />
            </Field>
          </>
        )}
        {action === 'member' && (
          <>
            <Field label="Employee">
              <select name="user_id" required>
                <option value="">Select employee</option>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.display_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Project role">
              <select name="role" defaultValue="member">
                <option value="project_lead">Project Lead</option>
                <option value="member">Member</option>
                <option value="viewer">Viewer</option>
              </select>
            </Field>
          </>
        )}
        {action === 'update' && (
          <>
            <Field label="Reporting date">
              <input
                name="reporting_date"
                type="date"
                defaultValue={today}
                required
              />
            </Field>
            <Field label="Summary" wide>
              <textarea name="summary" rows={3} required />
            </Field>
            <Field label="Accomplishments" wide>
              <textarea name="accomplishments" rows={3} />
            </Field>
            <Field label="Blockers">
              <textarea name="blockers" rows={3} />
            </Field>
            <Field label="Next steps">
              <textarea name="next_steps" rows={3} />
            </Field>
          </>
        )}
        {(action === 'risk' || action === 'issue') && (
          <>
            <Field label={`${title(action)} title`} wide>
              <input name="title" required />
            </Field>
            <Field label="Severity">
              <select name="severity" defaultValue="medium">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </Field>
            {action === 'risk' && (
              <>
                <Field label="Probability">
                  <select name="probability" defaultValue="medium">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </Field>
                <Field label="Impact">
                  <select name="impact" defaultValue="medium">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </Field>
                <Field label="Mitigation" wide>
                  <textarea name="mitigation" rows={3} />
                </Field>
              </>
            )}
            {action === 'issue' && (
              <Field label="Due date">
                <input name="due_date" type="date" />
              </Field>
            )}
            <Field label="Description" wide>
              <textarea name="description" rows={4} />
            </Field>
          </>
        )}
        {action === 'report' && (
          <>
            <Field label="Start date">
              <input name="start_date" type="date" required />
            </Field>
            <Field label="End date">
              <input
                name="end_date"
                type="date"
                defaultValue={today}
                required
              />
            </Field>
          </>
        )}
        {error && (
          <p className="text-sm text-destructive sm:col-span-2" role="alert">
            {error.message}
          </p>
        )}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <button
            type="button"
            className="rounded-xl border px-4 py-2.5"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            disabled={pending}
            className="rounded-xl bg-primary px-4 py-2.5 font-semibold text-primary-foreground"
          >
            {pending
              ? 'Saving…'
              : action === 'report'
                ? 'Generate report'
                : 'Save'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}
