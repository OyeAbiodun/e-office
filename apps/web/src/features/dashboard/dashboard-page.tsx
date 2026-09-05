import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Activity,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Bell,
  Plus,
  Users,
  Video,
} from 'lucide-react'

import { getDashboard } from '@/features/dashboard/api'
import { meetingApi } from '@/features/meetings/api'
import { notificationApi } from '@/features/notifications/api'
import { tasksApi } from '@/features/tasks/api'
import { useAuth } from '@/features/auth/auth-store'
import { humanizeEvent } from '@/lib/activity'

function DashboardSkeleton() {
  return (
    <div
      className="mx-auto max-w-7xl space-y-6 p-5 sm:p-8"
      aria-label="Loading dashboard"
    >
      <div className="h-20 w-2/3 animate-pulse rounded-2xl bg-muted" />
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <div className="h-72 animate-pulse rounded-2xl bg-muted" />
        <div className="h-72 animate-pulse rounded-2xl bg-muted" />
      </div>
      <div className="grid gap-5 md:grid-cols-3">
        {[1, 2, 3].map((item) => (
          <div className="h-36 animate-pulse rounded-2xl bg-muted" key={item} />
        ))}
      </div>
    </div>
  )
}

const formatTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))

export function DashboardPage() {
  const { user } = useAuth()
  const permissions = new Set(user?.permissions ?? [])
  const canViewWork = permissions.has('tasks.view_own')
  const greetingName = user?.display_name ?? user?.first_name ?? 'there'
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })
  const meetings = useQuery({
    queryKey: ['meeting-dashboard'],
    queryFn: meetingApi.dashboard,
  })
  const notifications = useQuery({
    queryKey: ['notifications'],
    queryFn: notificationApi.list,
  })
  const work = useQuery({
    queryKey: ['dashboard-work'],
    queryFn: () => tasksApi.list({ scope: 'mine', page: 1, page_size: 5 }),
    enabled: canViewWork,
  })
  const loading =
    dashboard.isLoading ||
    meetings.isLoading ||
    notifications.isLoading ||
    (canViewWork && work.isLoading)
  const error =
    dashboard.isError ||
    meetings.isError ||
    notifications.isError ||
    (canViewWork && work.isError)
  if (loading) return <DashboardSkeleton />
  if (
    error ||
    !dashboard.data ||
    !meetings.data ||
    !notifications.data ||
    (canViewWork && !work.data)
  )
    return (
      <div
        className="grid min-h-[60vh] place-items-center p-8 text-center"
        role="alert"
      >
        <div>
          <Activity className="mx-auto size-10 text-muted-foreground" />
          <h1 className="mt-4 text-xl font-semibold">
            Your workspace could not be loaded
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Check your connection, then retry.
          </p>
          <button
            className="mt-5 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            onClick={() => window.location.reload()}
            type="button"
          >
            Retry
          </button>
        </div>
      </div>
    )

  const scheduled = [...meetings.data.today, ...meetings.data.upcoming].slice(
    0,
    4,
  )
  const actionItems = meetings.data.my_action_items
  return (
    <div className="mx-auto max-w-7xl space-y-7 p-5 sm:p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-primary">
            Your digital workplace
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Good{' '}
            {new Date().getHours() < 12
              ? 'morning'
              : new Date().getHours() < 18
                ? 'afternoon'
                : 'evening'}
            {', '}
            {greetingName}
          </h1>
          <p className="mt-2 text-muted-foreground">
            Here’s what needs your attention in{' '}
            {dashboard.data.organization_name}.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            className="rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold hover:bg-muted"
            to="/chat/new"
          >
            New message
          </Link>
          {canViewWork && (
            <Link
              className="rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold hover:bg-muted"
              to="/tasks"
            >
              My work
            </Link>
          )}
          <Link
            className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
            to="/meetings/new"
          >
            <Plus className="size-4" /> Schedule
          </Link>
        </div>
      </header>

      {canViewWork && work.data && (
        <section className="grid gap-5 lg:grid-cols-[1.55fr_1fr]">
          <article className="overflow-hidden rounded-2xl border bg-card shadow-sm">
            <header className="flex items-center justify-between border-b p-5">
              <div>
                <h2 className="font-semibold">Today and upcoming</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Your next meetings across every workspace.
                </p>
              </div>
              <Link
                className="text-sm font-semibold text-primary"
                to="/calendar"
              >
                Open calendar
              </Link>
            </header>
            {scheduled.length ? (
              <div className="divide-y">
                {scheduled.map((meeting) => (
                  <div
                    className="flex items-center gap-4 p-4 transition hover:bg-muted/40"
                    key={meeting.id}
                  >
                    <div className="w-16 text-center">
                      <p className="text-sm font-semibold">
                        {formatTime(meeting.start_datetime)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(meeting.start_datetime).toLocaleDateString(
                          undefined,
                          { month: 'short', day: 'numeric' },
                        )}
                      </p>
                    </div>
                    <span className="h-10 w-1 rounded-full bg-primary" />
                    <div className="min-w-0 flex-1">
                      <Link
                        className="block truncate font-semibold hover:text-primary"
                        params={{ meetingId: meeting.id }}
                        to="/meetings/$meetingId"
                      >
                        {meeting.title}
                      </Link>
                      <p className="mt-1 truncate text-sm text-muted-foreground">
                        {meeting.location_type} · {meeting.status}
                      </p>
                    </div>
                    {meeting.meeting_url ? (
                      <a
                        className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
                        href={meeting.meeting_url}
                        rel="noreferrer"
                        target="_blank"
                      >
                        Join
                      </a>
                    ) : (
                      <Link
                        className="rounded-xl border px-4 py-2 text-sm font-semibold hover:bg-muted"
                        params={{ meetingId: meeting.id }}
                        to="/meetings/$meetingId"
                      >
                        Prepare
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-10 text-center">
                <CalendarDays className="mx-auto size-8 text-muted-foreground" />
                <p className="mt-3 font-medium">No meetings on your horizon</p>
                <Link
                  className="mt-4 inline-flex text-sm font-semibold text-primary"
                  to="/meetings/new"
                >
                  Schedule a meeting
                </Link>
              </div>
            )}
          </article>

          <article className="rounded-2xl border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold">Invitations & reminders</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Meeting updates requiring your attention.
                </p>
              </div>
              <Bell className="size-5 text-primary" />
            </div>
            <div className="mt-5 grid grid-cols-3 gap-2">
              {[
                ['Unread', notifications.data.unread],
                ['Pending RSVP', meetings.data.pending_rsvps],
                ['Upcoming', meetings.data.upcoming.length],
              ].map(([label, value]) => (
                <div
                  className="rounded-xl bg-muted/55 p-3 text-center"
                  key={label}
                >
                  <p className="text-xl font-semibold">{value}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{label}</p>
                </div>
              ))}
            </div>
            <div className="mt-5 space-y-2">
              {notifications.data.notifications
                .slice(0, 3)
                .map((notification) => (
                  <button
                    className="flex items-center gap-3 rounded-xl p-3 hover:bg-muted"
                    key={notification.id}
                    onClick={() => {
                      if (!notification.read_at)
                        void notificationApi.markRead(notification.id)
                      if (notification.action_url)
                        window.location.assign(notification.action_url)
                    }}
                    type="button"
                  >
                    <span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary">
                      <Bell className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1 text-left">
                      <p className="truncate text-sm font-semibold">
                        {notification.title}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {notification.body}
                      </p>
                    </div>
                    {!notification.read_at && (
                      <span className="size-2 rounded-full bg-primary" />
                    )}
                  </button>
                ))}
              {!notifications.data.notifications.length && (
                <p className="rounded-xl border border-dashed p-5 text-center text-sm text-muted-foreground">
                  You are all caught up.
                </p>
              )}
            </div>
            <Link
              className="mt-3 flex items-center justify-center gap-1 rounded-xl border py-2 text-sm font-semibold hover:bg-muted"
              to="/meetings"
            >
              Review meetings <ArrowRight className="size-4" />
            </Link>
          </article>
        </section>
      )}

      <section className="grid gap-5 lg:grid-cols-3">
        <article className="rounded-2xl border bg-card p-5 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Assigned action items</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Commitments captured from your meetings.
              </p>
            </div>
            <CheckCircle2 className="size-5 text-primary" />
          </div>
          {actionItems.length ? (
            <div className="mt-4 divide-y">
              {actionItems.slice(0, 5).map((item, index) => (
                <div
                  className="flex items-center gap-3 py-3"
                  key={String(item.id ?? index)}
                >
                  <span className="size-4 rounded-full border-2 border-primary" />
                  <p className="text-sm font-medium">
                    {String(item.title ?? item.description ?? 'Meeting action')}
                  </p>
                  {item.due_date && (
                    <time className="ml-auto text-xs text-muted-foreground">
                      {String(item.due_date)}
                    </time>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-5 rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              You have no open meeting actions.
            </p>
          )}
        </article>
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">Quick actions</h2>
          <div className="mt-4 space-y-2">
            {[
              {
                label: 'Schedule meeting',
                to: '/meetings/new' as const,
                icon: Video,
              },
              ...(permissions.has('users.write')
                ? [
                    {
                      label: 'Invite member',
                      to: '/invitations' as const,
                      icon: Users,
                    },
                  ]
                : []),
              {
                label: 'Open my calendar',
                to: '/calendar' as const,
                icon: CalendarDays,
              },
            ].map(({ label, to, icon: Icon }) => (
              <Link
                className="flex items-center gap-3 rounded-xl border p-3 text-sm font-semibold hover:bg-muted"
                key={label}
                to={to}
              >
                <Icon className="size-4 text-primary" /> {label}
                <ArrowRight className="ml-auto size-4" />
              </Link>
            ))}
          </div>
        </article>
      </section>

      <section className="grid gap-5 lg:grid-cols-[1.55fr_1fr]">
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Work to focus on</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                The most immediate work from your live queue.
              </p>
            </div>
            <CheckCircle2 className="size-5 text-primary" />
          </div>
          {work.data.items.length ? (
            <div className="mt-4 divide-y">
              {work.data.items.map((task) => (
                <Link
                  className="flex items-center gap-3 py-3 hover:text-primary"
                  key={task.id}
                  to="/tasks"
                >
                  <span
                    aria-hidden="true"
                    className={`size-2 rounded-full ${task.is_overdue ? 'bg-red-500' : task.priority === 'urgent' || task.priority === 'high' ? 'bg-amber-500' : 'bg-primary'}`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{task.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {task.due_date
                        ? `Due ${new Date(task.due_date).toLocaleDateString()}`
                        : 'No due date'}{' '}
                      · {task.status.replaceAll('_', ' ')}
                    </p>
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground" />
                </Link>
              ))}
            </div>
          ) : (
            <p className="mt-5 rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              No open tasks in your queue.
            </p>
          )}
          <Link
            className="mt-4 inline-flex text-sm font-semibold text-primary"
            to="/tasks"
          >
            Open My Work <ArrowRight className="ml-1 size-4" />
          </Link>
        </article>
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">Workload snapshot</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            A fast, truthful view of your current queue.
          </p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-muted/60 p-4">
              <p className="text-2xl font-semibold">{work.data.total}</p>
              <p className="mt-1 text-xs text-muted-foreground">Task records</p>
            </div>
            <div className="rounded-xl bg-muted/60 p-4">
              <p className="text-2xl font-semibold">
                {work.data.items.filter((task) => task.is_overdue).length}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Overdue in this view
              </p>
            </div>
          </div>
        </article>
      </section>

      <section className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold">Recent activity</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Changes across your organization and workspaces.
            </p>
          </div>
          <Clock3 className="size-5 text-primary" />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {dashboard.data.recent_activity.slice(0, 6).map((item) => (
            <div className="flex gap-3 rounded-xl border p-3" key={item.id}>
              <span className="grid size-9 place-items-center rounded-full bg-muted">
                <Activity className="size-4" />
              </span>
              <div>
                <p className="text-sm font-medium">
                  {humanizeEvent(item.event_type)}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {new Date(item.occurred_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
          {!dashboard.data.recent_activity.length && (
            <p className="text-sm text-muted-foreground">No recent activity.</p>
          )}
        </div>
      </section>
    </div>
  )
}
