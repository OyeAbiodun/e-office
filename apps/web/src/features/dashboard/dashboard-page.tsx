import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Activity,
  ArrowRight,
  Bell,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileCheck2,
  FolderKanban,
  HeartPulse,
  ListChecks,
  Plus,
  ShieldCheck,
  TriangleAlert,
  Users,
  Video,
  WalletCards,
} from 'lucide-react'

import {
  ErrorState,
  LoadingState,
  MetricLink,
  Page,
  PageHeader,
  Surface,
} from '@/components/page'
import { useAuth } from '@/features/auth/auth-store'
import { getDashboard } from '@/features/dashboard/api'
import { financeApi } from '@/features/finance/api'
import { leaveApi } from '@/features/leave/api'
import { meetingApi } from '@/features/meetings/api'
import { notificationApi } from '@/features/notifications/api'
import { projectsApi } from '@/features/projects/api'
import { reportsApi } from '@/features/reports/api'
import { tasksApi } from '@/features/tasks/api'
import { humanizeEvent } from '@/lib/activity'

type HomePersona = 'administrator' | 'finance' | 'manager' | 'employee'

function resolveHomePersona(
  roles: string[],
  permissions: string[],
): HomePersona {
  const allowed = new Set(permissions)
  if (
    roles.some((role) => ['Super Admin', 'Admin'].includes(role)) ||
    allowed.has('admin.manage')
  )
    return 'administrator'
  if (
    roles.some((role) =>
      ['Accountant', 'Payroll Officer', 'Payroll Approver', 'Auditor'].includes(
        role,
      ),
    ) ||
    allowed.has('finance.accounts.view') ||
    allowed.has('payroll.periods.view')
  )
    return 'finance'
  if (
    allowed.has('tasks.view_team') ||
    allowed.has('reports.review_team') ||
    allowed.has('leave.view_team')
  )
    return 'manager'
  return 'employee'
}

const time = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))

const greeting = () => {
  const hour = new Date().getHours()
  return hour < 12
    ? 'Good morning'
    : hour < 18
      ? 'Good afternoon'
      : 'Good evening'
}

export function DashboardPage() {
  const { user } = useAuth()
  const permissions = new Set(user?.permissions ?? [])
  const persona = resolveHomePersona(user?.roles ?? [], user?.permissions ?? [])
  const canViewTasks = permissions.has('tasks.view_own')
  const canViewProjects = permissions.has('projects.view')
  const canViewMeetings =
    permissions.has('meetings.read') || permissions.has('meetings.view')
  const canViewNotifications = permissions.has('notifications.view')
  const canViewLeave = permissions.has('leave.view_own')
  const canViewReports = [
    'reports.view_own',
    'reports.view_team',
    'reports.view_department',
    'reports.view_management',
  ].some((permission) => permissions.has(permission))
  const canViewVouchers = permissions.has('vouchers.view_own')

  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })
  const tasks = useQuery({
    queryKey: ['home', 'tasks'],
    queryFn: () => tasksApi.list({ scope: 'mine', page: 1, page_size: 6 }),
    enabled: canViewTasks,
  })
  const weekly = useQuery({
    queryKey: ['home', 'work-summary'],
    queryFn: () => {
      const date = new Date()
      date.setDate(date.getDate() - ((date.getDay() + 6) % 7))
      return tasksApi.weeklySummary(date.toISOString().slice(0, 10))
    },
    enabled: canViewTasks,
  })
  const projects = useQuery({
    queryKey: ['home', 'projects'],
    queryFn: () =>
      projectsApi.list({ status: 'active', page: 1, page_size: 6 }),
    enabled: canViewProjects,
  })
  const meetings = useQuery({
    queryKey: ['home', 'meetings'],
    queryFn: meetingApi.dashboard,
    enabled: canViewMeetings,
  })
  const notifications = useQuery({
    queryKey: ['home', 'notifications'],
    queryFn: notificationApi.list,
    enabled: canViewNotifications,
  })
  const leave = useQuery({
    queryKey: ['home', 'leave'],
    queryFn: leaveApi.mySummary,
    enabled: canViewLeave,
  })
  const managerLeave = useQuery({
    queryKey: ['home', 'manager-leave'],
    queryFn: leaveApi.managerSummary,
    enabled: permissions.has('leave.view_team'),
  })
  const reporting = useQuery({
    queryKey: ['home', 'reporting'],
    queryFn: reportsApi.dashboard,
    enabled: canViewReports,
  })
  const vouchers = useQuery({
    queryKey: ['home', 'vouchers'],
    queryFn: financeApi.summary,
    enabled: canViewVouchers,
  })

  if (dashboard.isLoading) {
    return (
      <Page>
        <LoadingState label="Loading your OfficeFlow home" />
      </Page>
    )
  }
  if (dashboard.isError || !dashboard.data) {
    return (
      <Page>
        <ErrorState
          description="Your permitted workspace data could not be loaded. Check your connection and try again."
          onRetry={() => void dashboard.refetch()}
          title="Home is temporarily unavailable"
        />
      </Page>
    )
  }

  const name = user?.display_name || user?.first_name || 'there'
  const activeProjects = projects.data?.items ?? []
  const atRiskProjects = activeProjects.filter(
    (project) => project.health === 'at_risk' || project.health === 'off_track',
  ).length
  const voucherCount = (status: string) =>
    vouchers.data?.groups
      .filter((group) => group.status === status)
      .reduce((total, group) => total + group.count, 0) ?? 0
  const availableLeave =
    leave.data?.balances.reduce(
      (total, balance) => total + Number(balance.available_after_pending),
      0,
    ) ?? 0

  return (
    <Page className="space-y-6">
      <PageHeader
        actions={<HomeActions permissions={permissions} />}
        description={`Here is what needs attention across ${dashboard.data.organization_name}.`}
        eyebrow={homeEyebrow(persona)}
        title={`${greeting()}, ${name}`}
      />

      {persona === 'administrator' && (
        <AdministratorMetrics
          dashboard={dashboard.data}
          unread={notifications.data?.unread ?? 0}
        />
      )}
      {persona === 'finance' && (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricLink
            detail="Needs review or action"
            icon={WalletCards}
            label="Pending vouchers"
            to="/vouchers?status=submitted"
            value={voucherCount('submitted')}
          />
          <MetricLink
            detail="Approved and awaiting payment"
            icon={FileCheck2}
            label="Approved unpaid"
            to="/vouchers?status=approved"
            value={voucherCount('approved')}
          />
          <MetricLink
            detail="Open payroll workspace"
            icon={ShieldCheck}
            label="Payroll operations"
            to="/payroll"
            value={
              permissions.has('payroll.periods.view') ? 'Ready' : 'Restricted'
            }
          />
          <MetricLink
            detail="Accounts and reconciliations"
            icon={Activity}
            label="Finance center"
            to="/finance"
            value={
              permissions.has('finance.accounts.view') ? 'Open' : 'Restricted'
            }
          />
        </section>
      )}
      {persona === 'manager' && (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricLink
            icon={TriangleAlert}
            label="Team overdue"
            tone={(weekly.data?.overdue_tasks ?? 0) > 0 ? 'danger' : 'default'}
            to="/tasks?scope=team&due=overdue"
            value={weekly.data?.overdue_tasks ?? 0}
          />
          <MetricLink
            icon={FileCheck2}
            label="Reports to review"
            to="/reports?tab=review&status=pending_review"
            value={reporting.data?.pending_my_review ?? 0}
          />
          <MetricLink
            icon={CalendarDays}
            label="Team away today"
            to="/leave/team?view=away"
            value={managerLeave.data?.away_today.length ?? 0}
          />
          <MetricLink
            icon={FolderKanban}
            label="Projects at risk"
            tone={atRiskProjects > 0 ? 'warning' : 'default'}
            to="/projects?health=at_risk"
            value={reporting.data?.projects_at_risk ?? atRiskProjects}
          />
        </section>
      )}
      {persona === 'employee' && (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricLink
            icon={Clock3}
            label="Tasks due today"
            to="/tasks?due=today"
            value={
              tasks.data?.items.filter(
                (task) =>
                  task.due_date === new Date().toISOString().slice(0, 10),
              ).length ?? 0
            }
          />
          <MetricLink
            icon={TriangleAlert}
            label="Overdue tasks"
            tone={(weekly.data?.overdue_tasks ?? 0) > 0 ? 'danger' : 'default'}
            to="/tasks?due=overdue"
            value={weekly.data?.overdue_tasks ?? 0}
          />
          <MetricLink
            icon={Video}
            label="Upcoming meetings"
            to="/meetings/upcoming"
            value={meetings.data?.upcoming.length ?? 0}
          />
          {canViewLeave ? (
            <MetricLink
              detail="After pending requests"
              icon={CalendarDays}
              label="Available leave"
              to="/leave"
              value={`${availableLeave.toLocaleString(undefined, { maximumFractionDigits: 1 })} days`}
            />
          ) : (
            <MetricLink
              icon={FolderKanban}
              label="Active projects"
              to="/projects"
              value={projects.data?.total ?? 0}
            />
          )}
        </section>
      )}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(19rem,.75fr)]">
        <FocusPanel meetings={meetings.data} tasks={tasks.data?.items ?? []} />
        <AttentionPanel
          notifications={notifications.data?.notifications ?? []}
          persona={persona}
          reporting={reporting.data}
          teamAway={managerLeave.data?.away_today.length ?? 0}
        />
      </section>

      {canViewProjects && (
        <Surface className="p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">Projects in motion</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Delivery health and deadlines from your authorized portfolio.
              </p>
            </div>
            <Link className="text-sm font-semibold text-primary" to="/projects">
              View all <ArrowRight className="ml-1 inline size-4" />
            </Link>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {activeProjects.slice(0, 3).map((project) => (
              <Link
                className="rounded-[10px] border p-4 transition hover:border-primary-border hover:bg-primary-subtle/40"
                key={project.id}
                params={{ projectId: project.id }}
                to="/projects/$projectId"
              >
                <div className="flex items-start justify-between gap-3">
                  <strong className="truncate text-sm">{project.name}</strong>
                  <span className="status-badge">
                    {project.health.replaceAll('_', ' ')}
                  </span>
                </div>
                <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.min(100, project.progress)}%` }}
                  />
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  {project.progress}% complete · {project.overdue_task_count}{' '}
                  overdue
                </p>
              </Link>
            ))}
            {!activeProjects.length && (
              <p className="col-span-full rounded-[10px] border border-dashed p-6 text-center text-sm text-muted-foreground">
                No active projects are visible to you.
              </p>
            )}
          </div>
        </Surface>
      )}

      <Surface className="p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Recent activity</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Meaningful updates from your organization.
            </p>
          </div>
          <Clock3 className="size-5 text-primary" />
        </div>
        <div className="mt-4 grid gap-x-6 md:grid-cols-2">
          {dashboard.data.recent_activity.slice(0, 6).map((item) => (
            <div
              className="flex gap-3 border-b py-3 last:border-b-0"
              key={item.id}
            >
              <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
                <Activity className="size-4" />
              </span>
              <div>
                <p className="text-sm font-medium">
                  {humanizeEvent(item.event_type)}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {new Date(item.occurred_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
          {!dashboard.data.recent_activity.length && (
            <p className="py-6 text-sm text-muted-foreground">
              New activity will appear here as work progresses.
            </p>
          )}
        </div>
      </Surface>
    </Page>
  )
}

function homeEyebrow(persona: HomePersona) {
  if (persona === 'administrator') return 'Administration overview'
  if (persona === 'finance') return 'Finance & payroll overview'
  if (persona === 'manager') return 'Team overview'
  return 'Your workspace'
}

function HomeActions({ permissions }: { permissions: Set<string> }) {
  return (
    <>
      {permissions.has('tasks.create_own') && (
        <Link
          className="button-secondary"
          search={{ create: 'task' } as never}
          to="/tasks"
        >
          <ListChecks className="size-4" /> New task
        </Link>
      )}
      {(permissions.has('meetings.create') ||
        permissions.has('meetings.manage')) && (
        <Link className="button-primary" to="/meetings/new">
          <Plus className="size-4" /> Schedule meeting
        </Link>
      )}
    </>
  )
}

function AdministratorMetrics({
  dashboard,
  unread,
}: {
  dashboard: Awaited<ReturnType<typeof getDashboard>>
  unread: number
}) {
  const value = (id: string) =>
    dashboard.widgets.find((item) => item.id === id)?.value ?? 0
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricLink
        icon={Users}
        label="Active people"
        to="/users?status=active"
        value={value('members')}
      />
      <MetricLink
        icon={Bell}
        label="Pending invitations"
        to="/invitations?status=pending"
        value={value('invitations')}
      />
      <MetricLink
        icon={HeartPulse}
        label="System health"
        to="/system-health"
        value="View status"
      />
      <MetricLink
        icon={ShieldCheck}
        label="Unread activity"
        to="/notifications?status=unread"
        value={unread}
      />
    </section>
  )
}

function FocusPanel({
  tasks,
  meetings,
}: {
  tasks: Awaited<ReturnType<typeof tasksApi.list>>['items']
  meetings: Awaited<ReturnType<typeof meetingApi.dashboard>> | undefined
}) {
  const scheduled = [
    ...(meetings?.today ?? []),
    ...(meetings?.upcoming ?? []),
  ].slice(0, 3)
  return (
    <Surface className="overflow-hidden">
      <header className="flex items-center justify-between border-b px-5 py-4">
        <div>
          <h2 className="text-lg font-semibold">Next up</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Work and meetings that need your focus.
          </p>
        </div>
        <Link className="text-sm font-semibold text-primary" to="/my-space">
          Open My Space
        </Link>
      </header>
      <div className="divide-y">
        {tasks.slice(0, 3).map((task) => (
          <Link
            className="flex items-center gap-3 px-5 py-3.5 hover:bg-muted/45"
            key={task.id}
            search={{ task: task.id } as never}
            to="/tasks"
          >
            <span
              className={`size-2 shrink-0 rounded-full ${task.is_overdue ? 'bg-danger' : 'bg-primary'}`}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">
                {task.title}
              </span>
              <span className="block text-xs text-muted-foreground">
                {task.due_date
                  ? `Due ${new Date(task.due_date).toLocaleDateString()}`
                  : 'No due date'}{' '}
                · {task.status.replaceAll('_', ' ')}
              </span>
            </span>
            <ArrowRight className="size-4 text-muted-foreground" />
          </Link>
        ))}
        {scheduled.map((meeting) => (
          <Link
            className="flex items-center gap-3 px-5 py-3.5 hover:bg-muted/45"
            key={meeting.id}
            params={{ meetingId: meeting.id }}
            to="/meetings/$meetingId"
          >
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary-subtle text-primary">
              <Video className="size-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">
                {meeting.title}
              </span>
              <span className="block text-xs text-muted-foreground">
                {time(meeting.start_datetime)} · {meeting.location_type}
              </span>
            </span>
            <ArrowRight className="size-4 text-muted-foreground" />
          </Link>
        ))}
        {!tasks.length && !scheduled.length && (
          <div className="p-10 text-center">
            <CheckCircle2 className="mx-auto size-7 text-success" />
            <p className="mt-3 font-medium">You are all caught up</p>
            <p className="mt-1 text-sm text-muted-foreground">
              No immediate work or meetings need attention.
            </p>
          </div>
        )}
      </div>
    </Surface>
  )
}

function AttentionPanel({
  notifications,
  persona,
  reporting,
  teamAway,
}: {
  notifications: Awaited<
    ReturnType<typeof notificationApi.list>
  >['notifications']
  persona: HomePersona
  reporting: Awaited<ReturnType<typeof reportsApi.dashboard>> | undefined
  teamAway: number
}) {
  const managerAttention =
    persona === 'manager' &&
    ((reporting?.pending_my_review ?? 0) > 0 || teamAway > 0)
  return (
    <Surface className="p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Needs attention</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Exceptions and requests worth reviewing.
          </p>
        </div>
        <Bell className="size-5 text-primary" />
      </div>
      <div className="mt-4 space-y-2">
        {persona === 'manager' && (reporting?.pending_my_review ?? 0) > 0 && (
          <Link
            className="flex items-center gap-3 rounded-lg bg-warning/10 p-3 text-sm"
            search={{ tab: 'review' } as never}
            to="/reports"
          >
            <FileCheck2 className="size-4 text-warning" />
            <span className="flex-1">
              {reporting?.pending_my_review} reports await review
            </span>
            <ArrowRight className="size-4" />
          </Link>
        )}
        {persona === 'manager' && teamAway > 0 && (
          <Link
            className="flex items-center gap-3 rounded-lg bg-info/10 p-3 text-sm"
            to="/leave/team"
          >
            <CalendarDays className="size-4 text-info" />
            <span className="flex-1">{teamAway} team members away today</span>
            <ArrowRight className="size-4" />
          </Link>
        )}
        {notifications.slice(0, 4).map((item) => (
          <Link
            className="flex gap-3 rounded-lg p-3 hover:bg-muted"
            key={item.id}
            to={(item.action_url || '/notifications') as never}
          >
            <span className="mt-1 size-2 shrink-0 rounded-full bg-primary" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">
                {item.title}
              </span>
              <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
                {item.body}
              </span>
            </span>
          </Link>
        ))}
        {!notifications.length && !managerAttention && (
          <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            Nothing needs your attention right now.
          </p>
        )}
      </div>
      <Link className="button-secondary mt-4 w-full" to="/notifications">
        View notifications
      </Link>
    </Surface>
  )
}
