import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Activity,
  Bell,
  CalendarPlus,
  CircleHelp,
  FileClock,
  FileText,
  Hash,
  LayoutDashboard,
  Mail,
  MailPlus,
  MessageSquarePlus,
  Plug,
  Search,
  ShieldCheck,
  Users,
  Video,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useAuth } from '@/features/auth/auth-store'
import { notificationApi } from '@/features/notifications/api'
import { platformApi } from '@/features/platform/api'
import { searchApi } from '@/features/search/api'
import { recentPages } from '@/lib/recent-pages'

export type ShellPanel = 'command' | 'notifications' | 'quick-create' | null

const resultIcons = {
  activity: Activity,
  bell: Bell,
  'calendar-days': CalendarPlus,
  'circle-help': CircleHelp,
  'file-clock': FileClock,
  'layout-dashboard': LayoutDashboard,
  mail: Mail,
  messages: Hash,
  plug: Plug,
  shield: ShieldCheck,
  users: Users,
  video: Video,
} as const

const createActions = [
  { label: 'Schedule meeting', to: '/meetings/new', icon: Video },
  { label: 'Start conversation', to: '/chat/new', icon: MessageSquarePlus },
  { label: 'Compose mail', to: '/mail/compose', icon: MailPlus },
  { label: 'Invite teammate', to: '/invitations', icon: MailPlus },
  { label: 'Create workspace', to: '/workspaces', icon: FileText },
] as const

export function CommandCenter({
  panel,
  onClose,
}: {
  panel: ShellPanel
  onClose: () => void
}) {
  const { user } = useAuth()
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const notifications = useQuery({
    queryKey: ['notifications'],
    queryFn: notificationApi.list,
    enabled: panel === 'notifications',
    refetchInterval: panel === 'notifications' ? 10_000 : false,
  })
  const navigation = useQuery({
    queryKey: ['platform-navigation'],
    queryFn: platformApi.navigation,
    enabled: panel === 'command' || panel === 'quick-create',
  })
  const search = useQuery({
    queryKey: ['global-search', query.trim()],
    queryFn: () => searchApi.search(query.trim()),
    enabled: panel === 'command' && query.trim().length >= 2,
    staleTime: 15_000,
  })

  useEffect(() => {
    if (panel === 'command')
      window.setTimeout(() => inputRef.current?.focus(), 0)
    if (!panel) setQuery('')
  }, [panel])

  const results = useMemo(() => {
    if (query.trim().length >= 2) return search.data?.results ?? []
    const menuResults = (navigation.data ?? []).map((item) => ({
      id: item.key,
      title: item.label,
      subtitle: `${item.section.replaceAll('-', ' ')} navigation`,
      url: item.path,
      icon: item.icon,
    }))
    const historyResults = user
      ? recentPages(user.id)
          .slice(0, 6)
          .map((item) => ({
            id: item.path,
            title: item.label,
            subtitle: `Recently visited · ${item.parent}`,
            url: item.path,
            icon: item.icon,
          }))
      : []
    return [...historyResults, ...menuResults].filter(
      (item, index, values) =>
        values.findIndex((candidate) => candidate.url === item.url) === index,
    )
  }, [navigation.data, query, search.data?.results, user])

  const permittedCreateActions = useMemo(() => {
    const paths = new Set((navigation.data ?? []).map((item) => item.path))
    return createActions.filter((item) => {
      if (item.to.startsWith('/meetings')) return paths.has('/meetings')
      if (item.to.startsWith('/chat')) return paths.has('/chat')
      if (item.to.startsWith('/mail')) return paths.has('/mail')
      if (item.to.startsWith('/invitations'))
        return paths.has('/members') || paths.has('/users')
      return paths.has('/workspaces') || paths.has('/administration')
    })
  }, [navigation.data])

  if (!panel) return null
  const title =
    panel === 'command'
      ? 'Search MeetingHQ'
      : panel === 'notifications'
        ? 'Activity center'
        : 'Quick create'

  return (
    <div
      aria-label={title}
      aria-modal="true"
      className="fixed inset-0 z-[80] flex items-start justify-center bg-black/55 p-4 pt-[10vh] backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onClose()
      }}
      role="dialog"
    >
      <section className="w-full max-w-xl overflow-hidden rounded-2xl border bg-card shadow-2xl">
        <header className="flex h-14 items-center gap-3 border-b px-4">
          {panel === 'command' ? (
            <>
              <Search className="size-5 text-muted-foreground" />
              <input
                aria-label="Search commands and workspace resources"
                className="h-full flex-1 bg-transparent text-sm outline-none"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search pages, people, meetings, mail, help, and settings…"
                ref={inputRef}
                value={query}
              />
            </>
          ) : (
            <h2 className="flex-1 font-semibold">{title}</h2>
          )}
          <button
            aria-label={`Close ${title}`}
            className="rounded-lg p-2 text-muted-foreground hover:bg-muted"
            onClick={onClose}
            type="button"
          >
            <X className="size-4" />
          </button>
        </header>
        <div className="max-h-[65vh] overflow-y-auto p-2">
          {panel === 'command' &&
            results.map((item) => {
              const Icon =
                resultIcons[item.icon as keyof typeof resultIcons] ?? Search
              return (
                <Link
                  className="flex items-center gap-3 rounded-xl p-3 transition hover:bg-muted focus:bg-muted focus:outline-none"
                  key={`${item.url}-${item.id}`}
                  onClick={onClose}
                  to={item.url as never}
                >
                  <span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary">
                    <Icon className="size-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">
                      {item.title}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {item.subtitle}
                    </span>
                  </span>
                </Link>
              )
            })}
          {panel === 'quick-create' &&
            permittedCreateActions.map(({ label, to, icon: Icon }) => (
              <Link
                className="flex items-center gap-3 rounded-xl p-3 transition hover:bg-muted focus:bg-muted focus:outline-none"
                key={label}
                onClick={onClose}
                to={to}
              >
                <span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-4" />
                </span>
                <span className="text-sm font-semibold">{label}</span>
              </Link>
            ))}
          {panel === 'command' && search.isFetching && (
            <p className="p-3 text-center text-xs text-muted-foreground">
              Searching your workspace…
            </p>
          )}
          {panel === 'command' && !search.isFetching && results.length === 0 && (
            <p className="p-8 text-center text-sm text-muted-foreground">
              No pages or resources match “{query}”.
            </p>
          )}
          {panel === 'notifications' && notifications.isLoading && (
            <div
              aria-label="Loading activity"
              aria-live="polite"
              className="space-y-3 p-3"
              role="status"
            >
              {[1, 2, 3].map((item) => (
                <div
                  className="h-16 animate-pulse rounded-xl bg-muted"
                  key={item}
                />
              ))}
            </div>
          )}
          {panel === 'notifications' && notifications.isError && (
            <div className="p-6 text-center">
              <p className="font-medium">Activity could not be loaded</p>
              <button
                className="mt-3 text-sm font-semibold text-primary"
                onClick={() => void notifications.refetch()}
                type="button"
              >
                Retry
              </button>
            </div>
          )}
          {panel === 'notifications' &&
            notifications.data?.notifications.length === 0 && (
              <div className="p-10 text-center">
                <Activity className="mx-auto size-8 text-muted-foreground" />
                <p className="mt-3 font-medium">You’re all caught up</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  New invitations, RSVP updates, mail, and reminders appear here.
                </p>
              </div>
            )}
          {panel === 'notifications' &&
            notifications.data?.notifications.map((item) => (
              <button
                className="flex w-full gap-3 rounded-xl p-3 text-left hover:bg-muted"
                key={item.id}
                onClick={() => {
                  if (!item.read_at) void notificationApi.markRead(item.id)
                  if (item.action_url) window.location.assign(item.action_url)
                }}
                type="button"
              >
                <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
                  <Bell className="size-4" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                    {item.body}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {new Intl.DateTimeFormat(undefined, {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    }).format(new Date(item.delivered_at))}
                  </p>
                </div>
                {!item.read_at && (
                  <span className="ml-auto mt-2 size-2 shrink-0 rounded-full bg-primary" />
                )}
              </button>
            ))}
        </div>
      </section>
    </div>
  )
}
