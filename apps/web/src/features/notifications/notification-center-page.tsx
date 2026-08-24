import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Archive,
  Bell,
  BellRing,
  CheckCheck,
  Clock3,
  Mail,
  MonitorUp,
  Search,
  Settings2,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import type { LucideIcon } from 'lucide-react'

import {
  notificationApi,
  type NotificationPreferences,
} from '@/features/notifications/api'

export function NotificationCenterPage() {
  const [category, setCategory] = useState('all')
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [settingsOpen, setSettingsOpen] = useState(false)
  const queryClient = useQueryClient()
  const query = new URLSearchParams()
  if (category !== 'all') query.set('category', category)
  if (unreadOnly) query.set('unread_only', 'true')
  if (search.trim()) query.set('search', search.trim())
  query.set('page', String(page))
  query.set('page_size', '25')
  const notifications = useQuery({
    queryKey: ['notifications', query.toString()],
    queryFn: () => notificationApi.listFiltered(query.toString()),
    refetchInterval: 15_000,
  })
  const preferences = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: notificationApi.preferences,
  })
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ['notifications'] })
  const readAll = useMutation({
    mutationFn: notificationApi.markAllRead,
    onSuccess: refresh,
  })
  const archive = useMutation({
    mutationFn: notificationApi.archive,
    onSuccess: refresh,
  })
  const markRead = useMutation({
    mutationFn: notificationApi.markRead,
    onSuccess: refresh,
  })
  const bulk = useMutation({
    mutationFn: (action: 'read' | 'archive') =>
      notificationApi.bulk([...selected], action),
    onSuccess: () => {
      setSelected(new Set())
      refresh()
    },
  })
  const visible = notifications.data?.notifications ?? []

  useEffect(() => {
    setPage(1)
    setSelected(new Set())
  }, [category, unreadOnly, search])

  useEffect(() => {
    const latest = notifications.data?.notifications.find(
      (item) => !item.read_at,
    )
    if (
      latest &&
      preferences.data?.browser_enabled &&
      'Notification' in window &&
      Notification.permission === 'granted'
    ) {
      new Notification(latest.title, { body: latest.body, tag: latest.id })
    }
  }, [notifications.data, preferences.data?.browser_enabled])

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-primary">
            Activity & alerts
          </p>
          <h1 className="mt-1 text-3xl font-semibold">Notification Center</h1>
          <p className="mt-2 text-muted-foreground">
            Invitations, reminders, mentions, approvals, and delivery history.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold hover:bg-muted"
            disabled={readAll.isPending || !notifications.data?.unread}
            onClick={() => readAll.mutate()}
            type="button"
          >
            <CheckCheck className="size-4" /> Mark all read
          </button>
          <button
            className="rounded-xl border p-2.5 hover:bg-muted"
            onClick={() => setSettingsOpen((value) => !value)}
            title="Notification preferences"
            type="button"
          >
            <Settings2 className="size-4" />
          </button>
        </div>
      </header>
      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Metric
          icon={BellRing}
          label="Unread"
          value={notifications.data?.unread ?? 0}
        />
        <Metric
          icon={Bell}
          label="In inbox"
          value={notifications.data?.total ?? 0}
        />
        <Metric
          icon={BellRing}
          label="Mentions"
          value={notifications.data?.mentions ?? 0}
        />
        <Metric
          icon={Clock3}
          label="Meetings"
          value={notifications.data?.meetings ?? 0}
        />
        <Metric
          icon={Mail}
          label="Approvals"
          value={notifications.data?.approvals ?? 0}
        />
      </section>
      {settingsOpen && preferences.data && (
        <Preferences
          preferences={preferences.data}
          onSaved={() => {
            setSettingsOpen(false)
            void queryClient.invalidateQueries({
              queryKey: ['notification-preferences'],
            })
          }}
        />
      )}
      <div className="mt-6 grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="rounded-2xl border bg-card p-3 lg:self-start">
          {['all', 'meetings', 'mentions', 'approvals', 'general'].map(
            (item) => (
              <button
                className={`block w-full rounded-xl px-3 py-2 text-left text-sm capitalize ${
                  category === item
                    ? 'bg-primary/10 font-semibold text-primary'
                    : 'hover:bg-muted'
                }`}
                key={item}
                onClick={() => setCategory(item)}
                type="button"
              >
                {item}
              </button>
            ),
          )}
          <label className="mt-3 flex items-center gap-2 border-t px-3 pt-4 text-sm">
            <input
              checked={unreadOnly}
              onChange={(event) => setUnreadOnly(event.target.checked)}
              type="checkbox"
            />
            Unread only
          </label>
        </aside>
        <main className="overflow-hidden rounded-2xl border bg-card">
          <label className="relative block border-b p-4">
            <Search className="absolute left-7 top-7 size-4 text-muted-foreground" />
            <input
              aria-label="Search notifications"
              className="h-10 w-full rounded-xl border bg-background pl-10 pr-3 text-sm"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search notification history"
              value={search}
            />
          </label>
          {selected.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-b bg-muted/40 px-4 py-3">
              <span className="mr-auto text-sm font-semibold">
                {selected.size} selected
              </span>
              <button
                className="rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold"
                onClick={() => bulk.mutate('read')}
                type="button"
              >
                Mark selected read
              </button>
              <button
                className="rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold"
                onClick={() => bulk.mutate('archive')}
                type="button"
              >
                Archive selected
              </button>
            </div>
          )}
          {notifications.isLoading && (
            <div className="space-y-3 p-5">
              {[1, 2, 3].map((item) => (
                <div
                  className="h-24 animate-pulse rounded-xl bg-muted"
                  key={item}
                />
              ))}
            </div>
          )}
          {notifications.isError && (
            <p className="p-8 text-center text-destructive" role="alert">
              Notifications could not be loaded.
            </p>
          )}
          {visible.map((item) => (
            <article
              className={`flex gap-4 border-b p-5 last:border-0 ${
                item.read_at ? '' : 'bg-primary/[0.035]'
              }`}
              key={item.id}
            >
              <input
                aria-label={`Select ${item.title}`}
                checked={selected.has(item.id)}
                className="mt-3"
                onChange={(event) =>
                  setSelected((current) => {
                    const next = new Set(current)
                    if (event.target.checked) next.add(item.id)
                    else next.delete(item.id)
                    return next
                  })
                }
                type="checkbox"
              />
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                {item.category === 'meetings' ? (
                  <BellRing className="size-5" />
                ) : (
                  <Bell className="size-5" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold">{item.title}</h2>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] capitalize">
                    {item.priority}
                  </span>
                  {!item.read_at && (
                    <span
                      className="size-2 rounded-full bg-primary"
                      title="Unread"
                    />
                  )}
                </div>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  {item.body}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  }).format(new Date(item.delivered_at))}
                </p>
              </div>
              <div className="flex gap-1">
                {!item.read_at && (
                  <button
                    className="rounded-lg p-2 hover:bg-muted"
                    onClick={() => markRead.mutate(item.id)}
                    title="Mark read"
                    type="button"
                  >
                    <CheckCheck className="size-4" />
                  </button>
                )}
                <button
                  className="rounded-lg p-2 hover:bg-muted"
                  onClick={() => archive.mutate(item.id)}
                  title="Archive"
                  type="button"
                >
                  <Archive className="size-4" />
                </button>
              </div>
            </article>
          ))}
          {!notifications.isLoading && visible.length === 0 && (
            <div className="p-14 text-center">
              <Bell className="mx-auto size-9 text-muted-foreground" />
              <p className="mt-3 font-medium">No notifications here</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Adjust the filters or check back after new activity.
              </p>
            </div>
          )}
          {(notifications.data?.total_pages ?? 1) > 1 && (
            <footer className="flex items-center justify-between gap-3 border-t p-4 text-sm">
              <span className="text-muted-foreground">
                Page {notifications.data?.page} of{' '}
                {notifications.data?.total_pages}
              </span>
              <div className="flex gap-2">
                <button
                  className="rounded-lg border px-3 py-1.5 disabled:opacity-50"
                  disabled={page <= 1}
                  onClick={() => setPage((value) => value - 1)}
                  type="button"
                >
                  Previous
                </button>
                <button
                  className="rounded-lg border px-3 py-1.5 disabled:opacity-50"
                  disabled={page >= (notifications.data?.total_pages ?? 1)}
                  onClick={() => setPage((value) => value + 1)}
                  type="button"
                >
                  Next
                </button>
              </div>
            </footer>
          )}
        </main>
      </div>
    </div>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Bell
  label: string
  value: string | number
}) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border bg-card p-4">
      <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
        <Icon className="size-5" />
      </span>
      <div>
        <p className="text-2xl font-semibold">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  )
}

function Preferences({
  preferences,
  onSaved,
}: {
  preferences: NotificationPreferences
  onSaved: () => void
}) {
  const [form, setForm] = useState(preferences)
  const save = useMutation({
    mutationFn: () => notificationApi.updatePreferences(form),
    onSuccess: onSaved,
  })
  const requestBrowser = async () => {
    if ('Notification' in window) {
      const result = await Notification.requestPermission()
      setForm((current) => ({
        ...current,
        browser_enabled: result === 'granted',
      }))
    }
  }
  return (
    <section className="mt-6 rounded-2xl border bg-card p-5">
      <h2 className="font-semibold">Delivery preferences</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {(
          [
            ['in_app_enabled', Bell, 'In-app'],
            ['email_enabled', Mail, 'Email'],
            ['browser_enabled', MonitorUp, 'Browser'],
          ] as Array<
            [
              'in_app_enabled' | 'email_enabled' | 'browser_enabled',
              LucideIcon,
              string,
            ]
          >
        ).map(([field, Icon, label]) => (
          <label
            className="flex items-center gap-3 rounded-xl border p-3"
            key={field}
          >
            <Icon className="size-4 text-primary" />
            <span className="flex-1 text-sm font-medium">{label}</span>
            <input
              checked={form[field]}
              onChange={(event) =>
                setForm({ ...form, [field]: event.target.checked })
              }
              type="checkbox"
            />
          </label>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            checked={form.quiet_hours_enabled}
            onChange={(event) =>
              setForm({ ...form, quiet_hours_enabled: event.target.checked })
            }
            type="checkbox"
          />
          Quiet hours
        </label>
        <input
          aria-label="Quiet hours start"
          className="rounded-lg border bg-background px-3 py-2 text-sm"
          onChange={(event) =>
            setForm({ ...form, quiet_hours_start: event.target.value })
          }
          type="time"
          value={form.quiet_hours_start ?? '22:00'}
        />
        <input
          aria-label="Quiet hours end"
          className="rounded-lg border bg-background px-3 py-2 text-sm"
          onChange={(event) =>
            setForm({ ...form, quiet_hours_end: event.target.value })
          }
          type="time"
          value={form.quiet_hours_end ?? '07:00'}
        />
        <button
          className="text-sm font-semibold text-primary"
          onClick={() => void requestBrowser()}
          type="button"
        >
          Request browser permission
        </button>
        <button
          className="ml-auto rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
          disabled={save.isPending}
          onClick={() => save.mutate()}
          type="button"
        >
          Save preferences
        </button>
      </div>
    </section>
  )
}
