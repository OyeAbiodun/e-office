import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { IntegrationCenterPage } from '@/features/integrations/integration-center-page'
import { PlatformPage } from '@/features/platform/platform-page'
import { RolesPage } from '@/features/users/roles-page'

const mocks = vi.hoisted(() => ({
  confirm: vi.fn(async () => true),
  configure: vi.fn(),
  disconnect: vi.fn(),
  audit: vi.fn(),
  features: vi.fn(),
  integrations: vi.fn(),
  menus: vi.fn(),
  configuration: vi.fn(),
  health: vi.fn(),
  permissions: vi.fn(),
  roles: vi.fn(),
  synchronize: vi.fn(),
  updateFeature: vi.fn(),
  updateMenu: vi.fn(),
  previewMenus: vi.fn(),
  publishMenus: vi.fn(),
  resetMenus: vi.fn(),
  exportMenus: vi.fn(),
  importMenus: vi.fn(),
  setConfiguration: vi.fn(),
  updateRole: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  Navigate: ({ to }: { to: string }) => <div>Navigate to {to}</div>,
  useNavigate: () => mocks.navigate,
}))

vi.mock('@/components/feedback/confirmation', () => ({
  useConfirmation: () => mocks.confirm,
}))

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({
    user: { id: 'admin-1', roles: ['Super Admin'] },
  }),
}))

vi.mock('@/features/integrations/api', () => ({
  integrationApi: {
    list: mocks.integrations,
    configure: mocks.configure,
    disconnect: mocks.disconnect,
    synchronize: mocks.synchronize,
    audit: mocks.audit,
  },
}))

vi.mock('@/features/platform/api', () => ({
  platformApi: {
    features: mocks.features,
    updateFeature: mocks.updateFeature,
    menus: mocks.menus,
    updateMenu: mocks.updateMenu,
    previewMenus: mocks.previewMenus,
    publishMenus: mocks.publishMenus,
    resetMenus: mocks.resetMenus,
    exportMenus: mocks.exportMenus,
    importMenus: mocks.importMenus,
    configuration: mocks.configuration,
    setConfiguration: mocks.setConfiguration,
  },
}))

vi.mock('@/features/system-health/api', () => ({
  systemHealthApi: { snapshot: mocks.health },
}))

vi.mock('@/features/users/api', () => ({
  userAdminApi: {
    roles: mocks.roles,
    permissions: mocks.permissions,
    updateRole: mocks.updateRole,
  },
}))

const provider = {
  key: 'gmail',
  name: 'Gmail',
  category: 'Email',
  description: 'Google Workspace mail delivery.',
  auth_type: 'oauth',
  enabled: true,
  configured: false,
  health: 'attention',
  updated_at: null,
}

const calendarFeature = {
  id: 'feature-1',
  key: 'calendar',
  name: 'Calendar',
  description: 'Scheduling and calendar views.',
  enabled: true,
  hidden: false,
  maintenance_mode: false,
  release_stage: 'public',
  updated_at: '2026-08-03T00:00:00Z',
}

function renderWithClient(node: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['integrations'], [provider])
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/')
  mocks.features.mockResolvedValue([calendarFeature])
  mocks.integrations.mockResolvedValue([provider])
  mocks.menus.mockResolvedValue([])
  mocks.configuration.mockResolvedValue([])
  mocks.health.mockResolvedValue({
    status: 'healthy',
    score: 98,
    checked_at: '2026-08-03T00:00:00Z',
    last_updated: '2026-08-03T00:00:00Z',
    version: '0.1.0',
    environment: 'test',
    uptime_seconds: 100,
    components: [],
    queue: { pending: 0, failed: 0, delivered: 1 },
    warnings: [],
    errors: [],
    recommendations: [],
  })
  mocks.updateFeature.mockResolvedValue({
    ...calendarFeature,
    enabled: false,
  })
  mocks.configure.mockResolvedValue({ ...provider, configured: true })
  mocks.disconnect.mockResolvedValue({ key: 'gmail', configured: false })
  mocks.synchronize.mockResolvedValue({ key: 'gmail', configured: true })
  mocks.audit.mockResolvedValue([])
  mocks.previewMenus.mockResolvedValue([])
  mocks.publishMenus.mockResolvedValue([])
  mocks.resetMenus.mockResolvedValue([])
  mocks.exportMenus.mockResolvedValue({ items: [] })
  mocks.importMenus.mockResolvedValue([])
  mocks.permissions.mockResolvedValue([
    {
      id: 'permission-view',
      name: 'meetings.view',
      resource: 'meetings',
      action: 'view',
      description: 'View meetings',
    },
    {
      id: 'permission-manage',
      name: 'meetings.manage',
      resource: 'meetings',
      action: 'manage',
      description: 'Manage meetings',
    },
  ])
  mocks.roles.mockResolvedValue([
    {
      id: 'role-admin',
      organization_id: 'organization-1',
      name: 'Admin',
      description: 'Tenant administration',
      system_role: true,
      permissions: [
        {
          id: 'permission-view',
          name: 'meetings.view',
          resource: 'meetings',
          action: 'view',
          description: 'View meetings',
        },
      ],
    },
  ])
  mocks.updateRole.mockResolvedValue({})
})

test('Platform Management governs provider availability without exposing credentials', async () => {
  window.history.replaceState({}, '', '/platform?section=connections')
  renderWithClient(<PlatformPage />)
  expect(
    await screen.findByRole('heading', { name: 'Platform Management' }),
  ).toBeInTheDocument()
  expect(
    await screen.findByRole('heading', { name: 'External Connections' }),
  ).toBeInTheDocument()
  expect(await screen.findByText(/Configuration required/)).toBeVisible()
  expect(screen.queryByLabelText('Gmail Client secret')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Configure' })).toHaveAttribute(
    'href',
    '/integrations?provider=gmail',
  )

  fireEvent.click(screen.getByRole('button', { name: 'Enabled' }))
  await waitFor(() => expect(mocks.confirm).toHaveBeenCalled())
  await waitFor(() =>
    expect(mocks.updateFeature).toHaveBeenCalledWith('gmail', {
      enabled: false,
    }),
  )
})

test('Integration Center configures credentials inside its protected boundary', async () => {
  renderWithClient(<IntegrationCenterPage />)
  expect(
    await screen.findByRole('heading', { name: 'Integration Center' }),
  ).toBeVisible()
  fireEvent.click(await screen.findByRole('button', { name: 'Configure' }))
  fireEvent.change(screen.getByLabelText('Gmail Client ID'), {
    target: { value: 'client-id' },
  })
  fireEvent.change(screen.getByLabelText('Gmail Client secret'), {
    target: { value: 'client-secret' },
  })
  fireEvent.change(screen.getByLabelText('Gmail Tenant or domain'), {
    target: { value: 'example.test' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save configuration' }))
  await waitFor(() =>
    expect(mocks.configure).toHaveBeenCalledWith('gmail', {
      client_id: 'client-id',
      client_secret: 'client-secret',
      tenant: 'example.test',
    }),
  )
})

test('Role policies are collapsed by default and save grouped permission changes', async () => {
  renderWithClient(<RolesPage />)
  const role = await screen.findByRole('button', {
    name: /Organization Admin/,
  })
  expect(role).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByText('Manage meetings')).not.toBeInTheDocument()

  fireEvent.click(role)
  fireEvent.click(screen.getByRole('button', { name: /meetings/i }))
  fireEvent.click(
    screen.getByRole('button', { name: 'Enable meetings.manage' }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

  await waitFor(() => expect(mocks.confirm).toHaveBeenCalled())
  await waitFor(() =>
    expect(mocks.updateRole).toHaveBeenCalledWith('role-admin', {
      permission_ids: ['permission-view', 'permission-manage'],
    }),
  )
})
