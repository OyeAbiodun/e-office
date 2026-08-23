import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()

  return {
    ...actual,
    Link: ({ children, to }: { children: ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  }
})

vi.mock('@/features/auth/profile-menu', () => ({
  ProfileMenu: () => <button type="button">Profile</button>,
}))

vi.mock('@/features/notifications/api', () => ({
  notificationApi: {
    list: vi.fn(async () => ({
      items: [],
      unread: 0,
      mentions: 0,
      meetings: 0,
      approvals: 0,
      tasks: 0,
      total: 0,
      page: 1,
      page_size: 25,
      total_pages: 1,
      next_cursor: null,
    })),
  },
}))

import { TopNav } from '@/components/top-nav'
import { ThemeProvider } from '@/components/theme-provider'
import { humanizeEvent } from '@/lib/activity'

test('humanizes internal activity event names for people', () => {
  expect(humanizeEvent('PresenceChanged')).toBe('Presence Changed')
  expect(humanizeEvent('workspace.member_added')).toBe('Workspace Member Added')
})

test('top navigation exposes functional global actions', () => {
  const onCommand = vi.fn()
  const onMobileNavigation = vi.fn()
  const onNotifications = vi.fn()
  const onQuickCreate = vi.fn()
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TopNav
          breadcrumbs={[{ label: 'Chat', path: '/chat' }]}
          onCommand={onCommand}
          onMobileNavigation={onMobileNavigation}
          onNotifications={onNotifications}
          onQuickCreate={onQuickCreate}
        />
      </ThemeProvider>
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: /Search MeetingHQ/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Quick create' }))
  fireEvent.click(
    screen.getByRole('button', { name: 'Notifications and activity' }),
  )
  expect(onCommand).toHaveBeenCalledOnce()
  expect(onQuickCreate).toHaveBeenCalledOnce()
  expect(onNotifications).toHaveBeenCalledOnce()
})
