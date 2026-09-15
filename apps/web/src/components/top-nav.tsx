import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Activity,
  Bell,
  CalendarDays,
  CalendarRange,
  Circle,
  CircleHelp,
  ChevronRight,
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
import { PRODUCT } from '@/lib/product'

interface TopNavProps {
  breadcrumbs: Array<{ label: string; path: string; icon?: string }>
  onCommand: () => void
  onMobileNavigation: () => void
  onHelp?: () => void
  onNotifications: () => void
  onQuickCreate: () => void
  canViewNotifications?: boolean
}

export function TopNav({
  breadcrumbs,
  onCommand,
  onMobileNavigation,
  onHelp,
  onNotifications,
  onQuickCreate,
  canViewNotifications = true,
}: TopNavProps) {
  const notifications = useQuery({
    queryKey: ['notifications', 'top-navigation'],
    queryFn: notificationApi.list,
    enabled: canViewNotifications,
    refetchInterval: 10_000,
  })
  const unread = notifications.data?.unread ?? 0
  const breadcrumbIcons = {
    activity: Activity,
    bell: Bell,
    'calendar-days': CalendarDays,
    'calendar-range': CalendarRange,
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
    <header className="app-top-nav sticky top-0 z-30 border-b border-border bg-background/92 backdrop-blur-xl">
      <div className="flex h-[60px] items-center gap-3 px-3 sm:px-5">
        <button
          aria-label="Open navigation"
          className="rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
          onClick={onMobileNavigation}
          type="button"
        >
          <Menu aria-hidden="true" className="size-5" />
        </button>
        <nav
          aria-label="Breadcrumb"
          className="hidden min-w-0 flex-1 items-center gap-1.5 overflow-hidden text-sm text-muted-foreground lg:flex"
        >
          <Link className="shrink-0 hover:text-foreground" to="/">
            {PRODUCT.name}
          </Link>
          {breadcrumbs.map((crumb, index) => {
            const Icon =
              breadcrumbIcons[crumb.icon as keyof typeof breadcrumbIcons] ??
              Circle
            return (
              <span
                className="flex min-w-0 shrink items-center gap-1.5"
                key={crumb.path}
              >
                <ChevronRight
                  aria-hidden="true"
                  className="size-3.5 shrink-0"
                />
                <Icon aria-hidden="true" className="size-3.5 shrink-0" />
                {index === breadcrumbs.length - 1 ? (
                  <span
                    aria-current="page"
                    className="truncate font-medium text-foreground"
                  >
                    {crumb.label}
                  </span>
                ) : (
                  <Link
                    className="truncate hover:text-foreground"
                    to={crumb.path as never}
                  >
                    {crumb.label}
                  </Link>
                )}
              </span>
            )
          })}
        </nav>
        <button
          aria-label="Search OfficeFlow. Shortcut Control K"
          className="hidden h-9 w-full max-w-[28rem] items-center gap-3 rounded-lg border bg-card px-3 text-left text-sm text-muted-foreground transition hover:border-primary-border hover:bg-muted/60 sm:flex"
          onClick={onCommand}
          type="button"
        >
          <Search className="size-4" />
          <span className="flex-1">Search or run a command…</span>
          <kbd className="rounded-md border bg-background px-2 py-0.5 text-[11px]">
            Ctrl K
          </kbd>
        </button>
        <div className="ml-auto flex items-center gap-2">
          <button
            aria-label="Quick create"
            className="button-primary h-9 min-h-9 px-3"
            onClick={onQuickCreate}
            type="button"
          >
            <Plus className="size-4" />
            <span className="hidden md:inline">Create</span>
          </button>
          <ThemeToggle />
          <button
            aria-label="Help for this page"
            className="button-ghost size-9 min-h-9 p-0"
            onClick={() => onHelp?.()}
            title="Help for this page"
            type="button"
          >
            <CircleHelp aria-hidden="true" className="size-4" />
          </button>
          <button
            aria-label="Notifications and activity"
            className="button-ghost relative size-9 min-h-9 p-0"
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
        aria-label="Mobile breadcrumb"
        className="flex h-8 items-center gap-1.5 overflow-x-auto border-t px-4 text-xs text-muted-foreground lg:hidden"
      >
        <Link className="shrink-0 hover:text-foreground" to="/">
          {PRODUCT.name}
        </Link>
        {breadcrumbs.slice(-2).map((crumb, index, values) => (
          <span className="flex shrink-0 items-center gap-1.5" key={crumb.path}>
            <ChevronRight aria-hidden="true" className="size-3" />
            {index === values.length - 1 ? (
              <span aria-current="page" className="text-foreground">
                {crumb.label}
              </span>
            ) : (
              <Link to={crumb.path as never}>{crumb.label}</Link>
            )}
          </span>
        ))}
      </nav>
    </header>
  )
}
