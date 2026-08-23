import { useQuery } from '@tanstack/react-query'
import { useNavigate, useRouterState } from '@tanstack/react-router'
import {
  Activity,
  Bell,
  Building2,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  FileClock,
  LayoutDashboard,
  Mail,
  MessageSquareText,
  PanelLeftClose,
  Plug,
  Settings2,
  ShieldCheck,
  UserRoundCog,
  Users,
  Video,
  X,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { mailApi } from '@/features/mail/api'
import { notificationApi } from '@/features/notifications/api'
import { organizationApi } from '@/features/organizations/api'
import { platformApi, type MenuDefinition } from '@/features/platform/api'

const icons = {
  activity: Activity,
  bell: Bell,
  building: Building2,
  'calendar-days': CalendarDays,
  'circle-help': CircleHelp,
  'file-clock': FileClock,
  'layout-dashboard': LayoutDashboard,
  mail: Mail,
  messages: MessageSquareText,
  plug: Plug,
  settings: Settings2,
  shield: ShieldCheck,
  'user-cog': UserRoundCog,
  users: Users,
  video: Video,
}

interface SidebarProps {
  collapsed: boolean
  mobileOpen: boolean
  onCloseMobile: () => void
  onToggle: () => void
}

export function Sidebar({
  collapsed,
  mobileOpen,
  onCloseMobile,
  onToggle,
}: SidebarProps) {
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(['administration']),
  )
  const organization = useQuery({
    queryKey: ['organization'],
    queryFn: organizationApi.organization,
  })
  const workspaces = useQuery({
    queryKey: ['workspaces'],
    queryFn: organizationApi.workspaces,
  })
  const navigation = useQuery({
    queryKey: ['platform-navigation'],
    queryFn: platformApi.navigation,
  })
  const notificationSummary = useQuery({
    queryKey: ['notifications', 'shell-summary'],
    queryFn: notificationApi.list,
    refetchInterval: 10_000,
  })
  const mailSummary = useQuery({
    queryKey: ['mail-messages', 'inbox', 'shell-summary'],
    queryFn: () =>
      mailApi.messages({ folder: 'inbox', page: 1, pageSize: 10 }),
    refetchInterval: 15_000,
  })
  const label = organization.data?.name ?? 'MeetingHQ'
  const workspace = workspaces.data?.[0]
  const allItems = navigation.data ?? []
  const dynamicBadge = (item: MenuDefinition) => {
    if (item.key === 'notifications' && notificationSummary.data?.unread)
      return String(notificationSummary.data.unread)
    if (item.key === 'mail' && mailSummary.data?.unread)
      return String(mailSummary.data.unread)
    return item.badge
  }
  const renderNavigation = (
    items: MenuDefinition[],
    title?: string,
  ): ReactNode => (
    <div className="space-y-1">
      {title && !collapsed && (
        <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {title}
        </p>
      )}
      {items.map((item) => {
        const Icon = icons[item.icon as keyof typeof icons] ?? LayoutDashboard
        const children = allItems
          .filter((candidate) => candidate.parent_key === item.key)
          .sort((left, right) => left.position - right.position)
        const expanded = expandedGroups.has(item.key)
        const badge = dynamicBadge(item)
        return (
          <div key={item.key}>
            <div className="flex items-center gap-1">
              <a
                aria-label={collapsed ? item.label : undefined}
                className={`flex min-h-10 min-w-0 flex-1 items-center gap-3 rounded-xl px-3 text-sm font-medium transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground ${
                  pathname === item.path
                    ? 'bg-sidebar-accent text-primary'
                    : 'text-muted-foreground'
                }`}
                href={item.path}
                onClick={(event) => {
                  if (
                    event.button === 0 &&
                    !event.ctrlKey &&
                    !event.metaKey &&
                    !event.shiftKey &&
                    !event.altKey
                  ) {
                    event.preventDefault()
                    onCloseMobile()
                    void navigate({ to: item.path as never })
                  }
                }}
                title={collapsed ? item.label : undefined}
              >
                <Icon className="size-[18px] shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
                {!collapsed && badge && (
                  <span
                    className={`ml-auto rounded-full bg-primary/10 px-2 py-0.5 text-[10px] text-primary ${
                      item.key === 'notifications' ? 'animate-pulse' : ''
                    }`}
                  >
                    {badge}
                  </span>
                )}
              </a>
              {!collapsed && children.length > 0 && (
                <button
                  aria-label={`${expanded ? 'Collapse' : 'Expand'} ${item.label}`}
                  className="rounded-lg p-2 text-muted-foreground hover:bg-sidebar-accent"
                  onClick={() =>
                    setExpandedGroups((current) => {
                      const next = new Set(current)
                      if (next.has(item.key)) next.delete(item.key)
                      else next.add(item.key)
                      return next
                    })
                  }
                  type="button"
                >
                  <ChevronDown
                    className={`size-4 transition ${
                      expanded ? 'rotate-180' : ''
                    }`}
                  />
                </button>
              )}
            </div>
            {!collapsed && expanded && children.length > 0 && (
              <div className="ml-5 border-l pl-2">
                {renderNavigation(children)}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
  const sections = [
    ...new Set(
      allItems.filter((item) => !item.parent_key).map((item) => item.section),
    ),
  ]

  return (
    <>
      {mobileOpen && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-black/55 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
          type="button"
        />
      )}
      <aside
        className={`${mobileOpen ? 'translate-x-0' : '-translate-x-full'} fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-2xl transition-transform lg:static lg:translate-x-0 lg:shadow-none ${
          collapsed ? 'lg:w-[76px]' : 'lg:w-64'
        }`}
      >
        <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
          <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary text-sm font-bold text-primary-foreground shadow-lg shadow-primary/20">
            MH
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold tracking-tight">{label}</p>
              <p className="truncate text-xs text-muted-foreground">
                {workspace?.name ?? 'Digital workplace'}
              </p>
            </div>
          )}
          <button
            aria-label="Close navigation"
            className="rounded-lg p-2 text-muted-foreground hover:bg-muted lg:hidden"
            onClick={onCloseMobile}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>

        {!collapsed && (
          <div className="border-b p-3">
            <div className="flex items-center gap-3 rounded-xl border bg-card/50 p-3">
              <div className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
                <Users className="size-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">
                  {workspace?.name ?? 'Choose workspace'}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {label}
                </p>
              </div>
            </div>
          </div>
        )}

        <nav
          aria-label="Primary navigation"
          className="flex-1 space-y-3 overflow-y-auto p-3"
        >
          {navigation.isLoading && !collapsed && (
            <p className="px-3 py-4 text-xs text-muted-foreground">
              Loading navigation…
            </p>
          )}
          {navigation.isError && !collapsed && (
            <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-600">
              Navigation unavailable
            </p>
          )}
          {sections.map((section) => (
            <div key={section}>
              {renderNavigation(
                allItems
                  .filter(
                    (item) => item.section === section && !item.parent_key,
                  )
                  .sort((left, right) => left.position - right.position),
                section === 'work' ? undefined : section,
              )}
            </div>
          ))}
        </nav>

        <div className="hidden border-t p-3 lg:block">
          <button
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="flex h-10 w-full items-center justify-center gap-2 rounded-xl text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
            onClick={onToggle}
            type="button"
          >
            {collapsed ? (
              <ChevronRight className="size-4" />
            ) : (
              <>
                <PanelLeftClose className="size-4" />
                Collapse
                <ChevronLeft className="ml-auto size-4" />
              </>
            )}
          </button>
        </div>
      </aside>
    </>
  )
}
