import { useQuery } from '@tanstack/react-query'
import { useNavigate, useRouterState } from '@tanstack/react-router'
import {
  Activity,
  Bell,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  CalendarRange,
  ChartNoAxesCombined,
  CheckSquare2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  FileClock,
  FolderKanban,
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
  WalletCards,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'

import {
  buildSidebarNavigation,
  groupIsActive,
  sidebarGroupStorageKey,
  type SidebarGroup,
} from '@/components/sidebar-navigation'
import { useAuth } from '@/features/auth/auth-store'
import { mailApi } from '@/features/mail/api'
import { notificationApi } from '@/features/notifications/api'
import { organizationApi } from '@/features/organizations/api'
import { platformApi, type MenuDefinition } from '@/features/platform/api'
import { ProductWordmark } from '@/components/product-wordmark'

const icons = {
  activity: Activity,
  bell: Bell,
  briefcase: BriefcaseBusiness,
  building: Building2,
  'calendar-days': CalendarDays,
  'calendar-range': CalendarRange,
  'chart-no-axes-combined': ChartNoAxesCombined,
  'check-square': CheckSquare2,
  'circle-help': CircleHelp,
  'file-clock': FileClock,
  'folder-kanban': FolderKanban,
  'layout-dashboard': LayoutDashboard,
  mail: Mail,
  messages: MessageSquareText,
  plug: Plug,
  settings: Settings2,
  shield: ShieldCheck,
  'user-cog': UserRoundCog,
  users: Users,
  video: Video,
  'wallet-cards': WalletCards,
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
  const { user } = useAuth()
  const permissions = useMemo(
    () => new Set(user?.permissions ?? []),
    [user?.permissions],
  )
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
    try {
      return new Set(
        JSON.parse(localStorage.getItem(sidebarGroupStorageKey) ?? '[]'),
      )
    } catch {
      return new Set()
    }
  })
  const organization = useQuery({
    queryKey: ['organization'],
    queryFn: organizationApi.organization,
    enabled: permissions.has('organizations.read'),
  })
  const workspaces = useQuery({
    queryKey: ['workspaces'],
    queryFn: organizationApi.workspaces,
    enabled: permissions.has('workspaces.read'),
  })
  const navigation = useQuery({
    queryKey: ['platform-navigation'],
    queryFn: platformApi.navigation,
  })
  const notificationSummary = useQuery({
    queryKey: ['notifications', 'shell-summary'],
    queryFn: notificationApi.list,
    enabled: permissions.has('notifications.view'),
    refetchInterval: 10_000,
  })
  const mailSummary = useQuery({
    queryKey: ['mail-messages', 'inbox', 'shell-summary'],
    queryFn: () => mailApi.messages({ folder: 'inbox', page: 1, pageSize: 10 }),
    enabled: permissions.has('mail.view'),
    refetchInterval: 15_000,
  })
  const organizationLabel = organization.data?.name ?? 'Your organization'
  const workspace = workspaces.data?.[0]
  const allItems = navigation.data ?? []
  const sidebarItems = allItems.filter(
    (item) => item.parent_key !== 'administration',
  )
  const groupedNavigation = useMemo(
    () => buildSidebarNavigation(sidebarItems, permissions),
    [permissions, sidebarItems],
  )
  useEffect(() => {
    setExpandedGroups((current) => {
      const next = new Set(current)
      groupedNavigation.groups
        .filter((group) => groupIsActive(group, pathname))
        .forEach((group) => next.add(group.key))
      return next
    })
  }, [groupedNavigation.groups, pathname])
  useEffect(() => {
    localStorage.setItem(
      sidebarGroupStorageKey,
      JSON.stringify([...expandedGroups]),
    )
  }, [expandedGroups])
  const dynamicBadge = (item: MenuDefinition) => {
    const displayCount = (count: number) => (count > 99 ? '99+' : String(count))
    if (item.key === 'notifications' && notificationSummary.data?.unread)
      return displayCount(notificationSummary.data.unread)
    if (item.key === 'mail' && mailSummary.data?.unread)
      return displayCount(mailSummary.data.unread)
    return item.badge
  }
  const renderItem = (item: MenuDefinition, nested = false): ReactNode => {
    const Icon = icons[item.icon as keyof typeof icons] ?? LayoutDashboard
    const badge = dynamicBadge(item)
    const active =
      pathname === item.path ||
      (item.path !== '/' && pathname.startsWith(`${item.path}/`))
    return (
      <a
        aria-current={active ? 'page' : undefined}
        aria-label={collapsed ? item.label : undefined}
        className={`flex min-h-10 min-w-0 items-center gap-3 rounded-lg px-3 text-sm font-medium outline-none transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-primary ${
          active ? 'bg-sidebar-accent text-primary' : 'text-muted-foreground'
        } ${nested ? 'ml-3 border-l border-sidebar-border pl-4' : ''}`}
        href={item.path}
        key={item.key}
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
    )
  }
  const groupIcons: Record<string, typeof BriefcaseBusiness> = {
    'my-work': BriefcaseBusiness,
    communication: MessageSquareText,
    people: Users,
    'finance-payroll': WalletCards,
    intelligence: ChartNoAxesCombined,
    more: LayoutDashboard,
  }
  const renderGroup = (group: SidebarGroup) => {
    const expanded = expandedGroups.has(group.key)
    const active = groupIsActive(group, pathname)
    const GroupIcon = groupIcons[group.key] ?? LayoutDashboard
    return (
      <div key={group.key}>
        <button
          aria-expanded={expanded}
          className={`flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-sm font-semibold outline-none transition hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-primary ${
            active ? 'text-primary' : 'text-muted-foreground'
          }`}
          onClick={() =>
            setExpandedGroups((current) => {
              const next = new Set(current)
              if (next.has(group.key)) next.delete(group.key)
              else next.add(group.key)
              return next
            })
          }
          title={collapsed ? group.label : undefined}
          type="button"
        >
          <GroupIcon className="size-[18px] shrink-0" />
          {!collapsed && (
            <>
              <span className="truncate">{group.label}</span>
              <ChevronDown
                className={`ml-auto size-4 transition ${expanded ? 'rotate-180' : ''}`}
              />
            </>
          )}
        </button>
        {!collapsed && expanded && (
          <div className="mt-1 space-y-0.5">
            {group.items.map((item) => renderItem(item, true))}
          </div>
        )}
      </div>
    )
  }

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
        data-app-sidebar
        className={`${mobileOpen ? 'translate-x-0' : '-translate-x-full'} fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-2xl transition-transform lg:static lg:translate-x-0 lg:shadow-none ${
          collapsed ? 'lg:w-[76px]' : 'lg:w-64'
        }`}
      >
        <div className="flex h-[60px] items-center gap-3 border-b border-sidebar-border px-4">
          <ProductWordmark compact={collapsed} />
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
          <div className="border-b border-sidebar-border p-3">
            <div className="flex items-center gap-3 rounded-[10px] border bg-card/70 p-2.5">
              <div className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
                <Users className="size-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">
                  {workspace?.name ?? 'Primary workspace'}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {organizationLabel}
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
          {groupedNavigation.direct
            .filter((item) => item.key === 'dashboard')
            .map((item) => renderItem(item))}
          {!collapsed
            ? groupedNavigation.groups.map(renderGroup)
            : groupedNavigation.groups.flatMap((group) =>
                group.items.map((item) => renderItem(item)),
              )}
          <div className="my-2 border-t border-sidebar-border" />
          {groupedNavigation.direct
            .filter((item) => item.key !== 'dashboard')
            .map((item) => renderItem(item))}
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
