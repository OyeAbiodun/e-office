import { Outlet, useRouterState } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'

import { CommandCenter, type ShellPanel } from '@/components/command-center'
import { Sidebar } from '@/components/sidebar'
import { TopNav } from '@/components/top-nav'
import { ContextHelp } from '@/features/help/context-help'
import { useAuth } from '@/features/auth/auth-store'
import { useNotificationRealtime } from '@/features/notifications/use-notification-realtime'
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
  useNotificationRealtime(user)
  const [collapsed, setCollapsed] = useState(false)
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
    if (!user) return
    const leaf = crumbs.at(-1)?.label ?? 'Dashboard'
    const parent = crumbs.at(-2)?.label ?? 'MeetingHQ'
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
