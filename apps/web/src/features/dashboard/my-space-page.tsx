import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileText,
  FolderKanban,
  ListChecks,
  Plus,
  ReceiptText,
  TriangleAlert,
  Video,
  WalletCards,
} from 'lucide-react'

import {
  EmptyState,
  MetricLink,
  Page,
  PageHeader,
  Surface,
} from '@/components/page'
import { useAuth } from '@/features/auth/auth-store'
import { leaveApi } from '@/features/leave/api'
import { meetingApi } from '@/features/meetings/api'
import { payrollApi } from '@/features/payroll/api'
import { projectsApi } from '@/features/projects/api'
import { reportsApi } from '@/features/reports/api'
import { tasksApi } from '@/features/tasks/api'

export function MySpacePage() {
  const { user } = useAuth()
  const permissions = new Set(user?.permissions ?? [])
  const canTasks = permissions.has('tasks.view_own')
  const canProjects = permissions.has('projects.view')
  const canMeetings =
    permissions.has('meetings.read') || permissions.has('meetings.view')
  const canLeave = permissions.has('leave.view_own')
  const canPayroll = permissions.has('payroll.view_own')
  const canReports = permissions.has('reports.view_own')

  const tasks = useQuery({
    queryKey: ['my-space', 'tasks'],
    queryFn: () => tasksApi.list({ scope: 'mine', page: 1, page_size: 8 }),
    enabled: canTasks,
  })
  const weekly = useQuery({
    queryKey: ['my-space', 'summary'],
    queryFn: () => {
      const value = new Date()
      value.setDate(value.getDate() - ((value.getDay() + 6) % 7))
      return tasksApi.weeklySummary(value.toISOString().slice(0, 10))
    },
    enabled: canTasks,
  })
  const projects = useQuery({
    queryKey: ['my-space', 'projects'],
    queryFn: () =>
      projectsApi.list({ status: 'active', page: 1, page_size: 4 }),
    enabled: canProjects,
  })
  const meetings = useQuery({
    queryKey: ['my-space', 'meetings'],
    queryFn: meetingApi.dashboard,
    enabled: canMeetings,
  })
  const leave = useQuery({
    queryKey: ['my-space', 'leave'],
    queryFn: leaveApi.mySummary,
    enabled: canLeave,
  })
  const payroll = useQuery({
    queryKey: ['my-space', 'payroll'],
    queryFn: payrollApi.payslips,
    enabled: canPayroll,
  })
  const reports = useQuery({
    queryKey: ['my-space', 'reports'],
    queryFn: () => reportsApi.list({ page: 1, page_size: 4 }),
    enabled: canReports,
  })

  const rows = tasks.data?.items ?? []
  const open = rows.filter(
    (task) => !['completed', 'cancelled'].includes(task.status),
  )
  const dueToday = open.filter(
    (task) => task.due_date === new Date().toISOString().slice(0, 10),
  ).length
  const meetingRows = [
    ...(meetings.data?.today ?? []),
    ...(meetings.data?.upcoming ?? []),
  ].slice(0, 4)
  const availableLeave =
    leave.data?.balances.reduce(
      (total, item) => total + Number(item.available_after_pending),
      0,
    ) ?? 0

  return (
    <Page className="space-y-6">
      <PageHeader
        actions={
          <>
            {(permissions.has('activity.create_own') ||
              permissions.has('activity.manage')) && (
              <Link
                className="button-secondary"
                search={{ create: 'activity' } as never}
                to="/tasks"
              >
                Record activity
              </Link>
            )}
            {permissions.has('tasks.create_own') && (
              <Link
                className="button-primary"
                search={{ create: 'task' } as never}
                to="/tasks"
              >
                <Plus className="size-4" /> New task
              </Link>
            )}
          </>
        }
        description="Your personal operational workspace—what you are doing, waiting on, and expected to deliver next."
        eyebrow="Personal workspace"
        title="My Space"
      />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricLink
          icon={Clock3}
          label="Due today"
          to="/tasks?due=today"
          value={dueToday}
        />
        <MetricLink
          icon={TriangleAlert}
          label="Overdue"
          tone={(weekly.data?.overdue_tasks ?? 0) > 0 ? 'danger' : 'default'}
          to="/tasks?due=overdue"
          value={weekly.data?.overdue_tasks ?? 0}
        />
        <MetricLink
          icon={Video}
          label="Upcoming meetings"
          to="/meetings/upcoming"
          value={meetingRows.length}
        />
        <MetricLink
          detail="Completed in the current week"
          icon={CheckCircle2}
          label="Delivered"
          tone="success"
          to="/tasks?status=completed"
          value={weekly.data?.completed_tasks ?? 0}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(19rem,.8fr)]">
        <Surface className="overflow-hidden">
          <header className="flex items-center justify-between border-b px-5 py-4">
            <div>
              <h2 className="text-lg font-semibold">My tasks</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                The next work items in your queue.
              </p>
            </div>
            <Link className="text-sm font-semibold text-primary" to="/tasks">
              View all
            </Link>
          </header>
          {open.length ? (
            <div className="divide-y">
              {open.slice(0, 6).map((task) => (
                <Link
                  className="flex items-center gap-3 px-5 py-3.5 hover:bg-muted/45"
                  key={task.id}
                  search={{ task: task.id } as never}
                  to="/tasks"
                >
                  <span
                    className={`size-2 shrink-0 rounded-full ${task.is_overdue ? 'bg-danger' : task.priority === 'urgent' ? 'bg-warning' : 'bg-primary'}`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {task.title}
                    </span>
                    <span className="block text-xs capitalize text-muted-foreground">
                      {task.status.replaceAll('_', ' ')} ·{' '}
                      {task.due_date
                        ? `Due ${new Date(task.due_date).toLocaleDateString()}`
                        : 'No due date'}
                    </span>
                  </span>
                  <ArrowRight className="size-4 text-muted-foreground" />
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              description="No open task needs your attention. New assignments will appear here."
              icon={CheckCircle2}
              title="You are all caught up"
            />
          )}
        </Surface>

        <Surface className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">My schedule</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Meetings and commitments ahead.
              </p>
            </div>
            <CalendarDays className="size-5 text-primary" />
          </div>
          <div className="mt-4 space-y-2">
            {meetingRows.map((meeting) => (
              <Link
                className="block rounded-lg border p-3 hover:border-primary-border hover:bg-primary-subtle/40"
                key={meeting.id}
                params={{ meetingId: meeting.id }}
                to="/meetings/$meetingId"
              >
                <p className="truncate text-sm font-medium">{meeting.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {new Date(meeting.start_datetime).toLocaleString(undefined, {
                    weekday: 'short',
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </p>
              </Link>
            ))}
            {!meetingRows.length && (
              <p className="rounded-lg border border-dashed p-5 text-center text-sm text-muted-foreground">
                No upcoming meeting is on your schedule.
              </p>
            )}
          </div>
          {canMeetings && (
            <Link className="button-secondary mt-4 w-full" to="/calendar">
              Open calendar
            </Link>
          )}
        </Surface>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {canProjects && (
          <PersonalArea
            count={projects.data?.total ?? 0}
            description="Active workstreams you can access"
            icon={FolderKanban}
            label="My projects"
            to="/projects"
          />
        )}
        {canReports && (
          <PersonalArea
            count={reports.data?.total ?? 0}
            description="Generated and submitted reports"
            icon={FileText}
            label="My reports"
            to="/reports"
          />
        )}
        {canLeave && (
          <PersonalArea
            count={`${availableLeave.toLocaleString(undefined, { maximumFractionDigits: 1 })} days`}
            description={`${leave.data?.pending_requests.length ?? 0} pending request(s)`}
            icon={CalendarDays}
            label="My leave"
            to="/leave"
          />
        )}
        {canPayroll && (
          <PersonalArea
            count={payroll.data?.length ?? 0}
            description="Secure payslips available to you"
            icon={WalletCards}
            label="My payroll"
            to="/payroll"
          />
        )}
        {permissions.has('vouchers.view_own') && (
          <PersonalArea
            count="Open"
            description="Your expense and disbursement requests"
            icon={ReceiptText}
            label="My vouchers"
            to="/vouchers"
          />
        )}
      </section>
    </Page>
  )
}

function PersonalArea({
  count,
  description,
  icon: Icon,
  label,
  to,
}: {
  count: string | number
  description: string
  icon: typeof ListChecks
  label: string
  to: string
}) {
  return (
    <Link
      className="group rounded-[12px] border bg-card p-4 transition hover:border-primary-border hover:shadow-sm"
      to={to as never}
    >
      <div className="flex items-center justify-between">
        <span className="grid size-9 place-items-center rounded-lg bg-primary-subtle text-primary">
          <Icon className="size-[18px]" />
        </span>
        <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </div>
      <p className="mt-4 text-sm font-semibold">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{count}</p>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
    </Link>
  )
}
