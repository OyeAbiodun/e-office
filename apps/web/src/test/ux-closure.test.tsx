import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'

const mocks = vi.hoisted(() => ({
  articles: vi.fn(),
  favorites: vi.fn(),
  recent: vi.fn(),
  supportRequests: vi.fn(),
  navigation: vi.fn(),
  features: vi.fn(),
}))

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    Link: ({ children, to, ...props }: { children: ReactNode; to: string }) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
    Navigate: ({ to }: { to: string }) => <p>Redirected to {to}</p>,
  }
})

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({
    user: {
      first_name: 'Avery',
      roles: ['Super Admin'],
      permissions: ['admin.manage', 'users.manage', 'roles.manage'],
    },
  }),
}))

vi.mock('@/features/help/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/help/api')>()
  return {
    ...actual,
    helpApi: {
      ...actual.helpApi,
      articles: mocks.articles,
      favorites: mocks.favorites,
      recent: mocks.recent,
      supportRequests: mocks.supportRequests,
    },
  }
})

vi.mock('@/features/platform/api', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@/features/platform/api')>()
  return {
    ...actual,
    platformApi: {
      ...actual.platformApi,
      navigation: mocks.navigation,
      features: mocks.features,
    },
  }
})

import { AdministrationPage } from '@/features/platform/administration-page'
import { HelpCenterPage } from '@/features/help/help-center-page'

function renderPage(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  )
}

beforeEach(() => {
  mocks.articles.mockResolvedValue([])
  mocks.favorites.mockResolvedValue([])
  mocks.recent.mockResolvedValue([])
  mocks.supportRequests.mockResolvedValue([])
  mocks.features.mockResolvedValue([])
  mocks.navigation.mockResolvedValue([
    {
      id: 'admin',
      key: 'administration',
      label: 'Administration',
      path: '/administration',
      icon: 'settings',
      permission: 'admin.manage',
      required_role: null,
      feature_key: null,
      badge: null,
      parent_key: null,
      section: 'administration',
      position: 1,
      enabled: true,
      hidden: false,
    },
    {
      id: 'users',
      key: 'users',
      label: 'Users',
      path: '/users',
      icon: 'user-cog',
      permission: 'users.manage',
      required_role: null,
      feature_key: null,
      badge: null,
      parent_key: 'administration',
      section: 'admin',
      position: 2,
      enabled: true,
      hidden: false,
    },
    {
      id: 'roles',
      key: 'roles',
      label: 'Roles & Permissions',
      path: '/roles',
      icon: 'shield',
      permission: 'roles.manage',
      required_role: null,
      feature_key: null,
      badge: null,
      parent_key: 'administration',
      section: 'admin',
      position: 3,
      enabled: true,
      hidden: false,
    },
  ])
})

test('Help Centre renders its no-results state without an explicit icon', async () => {
  renderPage(<HelpCenterPage />)
  expect(await screen.findByText('No guides found')).toBeInTheDocument()
  expect(
    screen.getByText('No guides found').closest('[role="status"]'),
  ).toHaveTextContent('No guides found')
  expect(screen.getByRole('button', { name: 'Clear filters' })).toBeVisible()
})

test('Help support history renders an accessible empty state', async () => {
  renderPage(<HelpCenterPage />)
  fireEvent.click(screen.getByRole('tab', { name: 'Get support' }))
  expect(await screen.findByText('No support requests')).toBeInTheDocument()
})

test('Administration groups permitted destinations in one control center', async () => {
  renderPage(<AdministrationPage />)
  expect(
    await screen.findByRole('heading', { name: 'Administration' }),
  ).toBeVisible()
  expect(
    await screen.findByRole('navigation', { name: 'People & access' }),
  ).toBeVisible()
  expect(screen.getByRole('link', { name: /Users/ })).toHaveAttribute(
    'href',
    '/users',
  )
  expect(
    screen.getByRole('link', { name: /Roles & Permissions/ }),
  ).toHaveAttribute('href', '/roles')
  await waitFor(() => expect(mocks.navigation).toHaveBeenCalledOnce())
})
