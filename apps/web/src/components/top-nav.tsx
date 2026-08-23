import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Activity,
  Bell,
  CalendarDays,
  Circle,
  CircleHelp,
  FileClock,
  Flag,
  LayoutDashboard,
  Mail,
  Menu,
  MessageSquareText,
  Plug,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  UserRound,
  Users,
  Video,
} from 'lucide-react'

import { ThemeToggle } from '@/components/theme-toggle'
import { ProfileMenu } from '@/features/auth/profile-menu'
import { notificationApi } from '@/features/notifications/api'

interface TopNavProps {
  breadcrumbs: Array<{ label: string; path: string; icon?: string }>
  onCommand: () => void
  onMobileNavigation: () => void
  onHelp?: () => void
  onNotifications: () => void
  onQuickCreate: () => void
}

export function TopNav({
  breadcrumbs,
  onCommand,
  onMobileNavigation,
  onHelp,
  onNotifications,
  onQuickCreate,
}: TopNavProps) {
  const notifications = useQuery({
    queryKey: ['notifications', 'top-navigation'],
    queryFn: notificationApi.list,
    refetchInterval: 10_000,
  })
  const unread = notifications.data?.unread ?? 0
  const breadcrumbIcons = {
    activity: Activity,
    bell: Bell,
    'calendar-days': CalendarDays,
    'file-clock': FileClock,
    flag: Flag,
    'layout-dashboard': LayoutDashboard,
    mail: Mail,
    messages: MessageSquareText,
    plug: Plug,
    settings: Settings2,
    shield: ShieldCheck,
    user: UserRound,
    users: Users,
    video: Video,
    circle: Circle,
  }
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/88 backdrop-blur-xl">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
        <button
          aria-label="Open navigation"
          className="rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
          onClick={onMobileNavigation}
          type="button"
        >
          <Menu aria-hidden="true" className="size-5" />
        </button>
        <button
          aria-label="Search MeetingHQ. Shortcut Control K"
          className="hidden h-10 max-w-lg flex-1 items-center gap-3 rounded-xl border bg-muted/45 px-3 text-left text-sm text-muted-foreground transition hover:border-primary/40 hover:bg-muted sm:flex"
          onClick={onCommand}
          type="button"
        >
          <Search className="size-4" />
          <span className="flex-1">Search people, meetings, channels…</span>
          <kbd className="rounded-md border bg-background px-2 py-0.5 text-[11px]">
            Ctrl K
          </kbd>
        </button>
        <div className="ml-auto flex items-center gap-2">
          <button
            aria-label="Quick create"
            className="flex h-9 items-center gap-2 rounded-xl bg-primary px-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/15"
            onClick={onQuickCreate}
            type="button"
          >
            <Plus className="size-4" />
            <span className="hidden md:inline">Create</span>
          </button>
          <ThemeToggle />
          <button
            aria-label="Help for this page"
            className="rounded-xl border border-border p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={() => onHelp?.()}
            title="Help for this page"
            type="button"
          >
            <CircleHelp aria-hidden="true" className="size-4" />
          </button>
          <button
            aria-label="Notifications and activity"
            className="relative rounded-xl border border-border p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={onNotifications}
            type="button"
          >
            <Bell aria-hidden="true" className="size-4" />
            {unread > 0 && (
              <span
                aria-label={`${unread} unread notifications`}
                className="absolute -right-1.5 -top-1.5 grid min-w-5 animate-pulse place-items-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white"
              >
                {unread > 99 ? '99+' : unread}
              </span>
            )}
          </button>
          <ProfileMenu />
        </div>
      </div>
      <nav
        aria-label="Breadcrumb"
        className="flex h-9 items-center gap-2 overflow-x-auto border-t px-4 text-xs text-muted-foreground sm:px-6"
      >
        <Link className="shrink-0 hover:text-foreground" to="/">
          MeetingHQ
        </Link>
        {breadcrumbs.map((crumb, index) => (
          <span className="flex shrink-0 items-center gap-2" key={crumb.path}>
            <span aria-hidden="true">/</span>
            {(() => {
              const Icon =
                breadcrumbIcons[crumb.icon as keyof typeof breadcrumbIcons] ??
                Circle
              return <Icon aria-hidden="true" className="size-3.5" />
            })()}
            {index === breadcrumbs.length - 1 ? (
              <span aria-current="page" className="capitalize text-foreground">
                {crumb.label}
              </span>
            ) : (
              <Link
                className="capitalize hover:text-foreground"
                to={crumb.path as never}
              >
                {crumb.label}
              </Link>
            )}
          </span>
        ))}
      </nav>
    </header>
  )
}
