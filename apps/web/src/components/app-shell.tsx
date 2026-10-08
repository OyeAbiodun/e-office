import { Outlet, useRouterState } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { CommandCenter, type ShellPanel } from '@/components/command-center'
import { Sidebar } from '@/components/sidebar'
import { TopNav } from '@/components/top-nav'
import { ContextHelp } from '@/features/help/context-help'
import { useAuth } from '@/features/auth/auth-store'
import { useNotificationRealtime } from '@/features/notifications/use-notification-realtime'
import { organizationApi } from '@/features/organizations/api'
import { recordRecentPage } from '@/lib/recent-pages'
import { resolveBreadcrumbs } from '@/lib/route-metadata'

export function AppShell() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const search = useRouterState({
    select: (state) => state.location.searchStr,
  })
  const { user } = useAuth()
  const organization = useQuery({
    queryKey: ['organization', user?.organization_id],
    queryFn: organizationApi.organization,
    enabled: Boolean(user),
  })
  useNotificationRealtime(user)
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('officeflow-sidebar-collapsed') === 'true',
  )
  const [mobileOpen, setMobileOpen] = useState(false)
  const [panel, setPanel] = useState<ShellPanel>(null)
  const [helpOpen, setHelpOpen] = useState(false)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPanel('command')
      }
      if (event.key === 'Escape') setPanel(null)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const pathParts = useMemo(
    () => pathname.split('/').filter(Boolean),
    [pathname],
  )
  const crumbs = useMemo(
    () => resolveBreadcrumbs(pathname, search),
    [pathname, search],
  )
  const helpContextId = getHelpContextId(pathname)

  useEffect(() => {
    localStorage.setItem('officeflow-sidebar-collapsed', String(collapsed))
  }, [collapsed])

  useEffect(() => {
    const color = organization.data?.brand_color
    if (!color) return
    const root = document.documentElement
    root.style.setProperty('--primary', color)
    root.style.setProperty('--primary-hover', mixHex(color, '#000000', 0.16))
    root.style.setProperty('--primary-subtle', mixHex(color, '#ffffff', 0.88))
    root.style.setProperty('--primary-border', mixHex(color, '#ffffff', 0.58))
    root.style.setProperty('--sidebar-accent', mixHex(color, '#ffffff', 0.88))
    root.style.setProperty('--sidebar-accent-foreground', color)
  }, [organization.data?.brand_color])

  useEffect(() => {
    if (!user) return
    const leaf = crumbs.at(-1)?.label ?? 'Home'
    const parent = crumbs.at(-2)?.label ?? 'OfficeFlow'
    recordRecentPage(user.id, {
      path: `${pathname}${search ? `?${search}` : ''}`,
      label: leaf,
      parent,
      icon: pathParts[0] ?? 'dashboard',
      visitedAt: new Date().toISOString(),
    })
  }, [crumbs, pathParts, pathname, search, user])

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <a
        className="fixed left-3 top-3 z-[100] -translate-y-20 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground focus:translate-y-0"
        href="#main-content"
      >
        Skip to content
      </a>
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        onToggle={() => setCollapsed((value) => !value)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopNav
          breadcrumbs={crumbs}
          canViewNotifications={Boolean(
            user?.permissions.includes('notifications.view'),
          )}
          onCommand={() => setPanel('command')}
          onHelp={() => setHelpOpen(true)}
          onMobileNavigation={() => setMobileOpen(true)}
          onNotifications={() => setPanel('notifications')}
          onQuickCreate={() => setPanel('quick-create')}
        />
        <main className="flex-1 overflow-auto" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <CommandCenter panel={panel} onClose={() => setPanel(null)} />
      <ContextHelp
        contextId={helpContextId}
        onClose={() => setHelpOpen(false)}
        open={helpOpen}
      />
    </div>
  )
}

function mixHex(source: string, target: string, amount: number) {
  const channel = (value: string, offset: number) =>
    Number.parseInt(value.slice(offset, offset + 2), 16)
  const mixed = [1, 3, 5].map((offset) =>
    Math.round(
      channel(source, offset) * (1 - amount) + channel(target, offset) * amount,
    )
      .toString(16)
      .padStart(2, '0'),
  )
  return `#${mixed.join('')}`
}

function getHelpContextId(pathname: string) {
  const parts = pathname.split('/').filter(Boolean)
  if (parts.length === 0) return 'dashboard'
  const normalized = parts.map((part) =>
    /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(part) || /^\d+$/.test(part)
      ? 'detail'
      : part,
  )
  return normalized.join('.')
}
