import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { IntegrationCenterPage } from '@/features/integrations/integration-center-page'
import { PlatformPage } from '@/features/platform/platform-page'
import { RolesPage } from '@/features/users/roles-page'

const mocks = vi.hoisted(() => ({
  authPermissions: [
    'integrations.view',
    'integrations.manage',
    'integrations.test',
  ],
  confirm: vi.fn(async () => true),
  configure: vi.fn(),
  configureSmtp: vi.fn(),
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
  smtpConfiguration: vi.fn(),
  smtpTemplatePreview: vi.fn(),
  sendSmtpTestEmail: vi.fn(),
  testIntegration: vi.fn(),
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
    user: {
      id: 'admin-1',
      roles: ['Super Admin'],
      permissions: mocks.authPermissions,
    },
  }),
}))

vi.mock('@/features/integrations/api', () => ({
  integrationApi: {
    list: mocks.integrations,
    configure: mocks.configure,
    disconnect: mocks.disconnect,
    synchronize: mocks.synchronize,
    audit: mocks.audit,
    smtpConfiguration: mocks.smtpConfiguration,
    configureSmtp: mocks.configureSmtp,
    sendSmtpTestEmail: mocks.sendSmtpTestEmail,
    smtpTemplatePreview: mocks.smtpTemplatePreview,
    test: mocks.testIntegration,
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

const smtpConfiguration = {
  provider_display_name: 'Transactional SMTP',
  host: 'smtp.example.test',
  port: 587,
  security_mode: 'starttls',
  allow_insecure: false,
  connection_timeout: 20,
  authentication_enabled: true,
  authentication_method: 'password',
  username: 'mailer@example.test',
  password_configured: true,
  password_mask: '••••••••••••',
  from_email: 'meetings@example.test',
  from_name: 'MeetingHQ',
  reply_to: null,
  return_path: null,
  enabled: true,
  max_retry_attempts: 3,
  retry_delay_seconds: 1,
  timeout_seconds: 20,
  default_priority: 'normal',
  state: 'healthy',
  revision: 2,
  updated_at: '2026-08-03T00:00:00Z',
  last_validated_at: '2026-08-03T00:01:00Z',
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
  mocks.authPermissions.splice(
    0,
    mocks.authPermissions.length,
    'integrations.view',
    'integrations.manage',
    'integrations.test',
  )
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
  mocks.smtpConfiguration.mockResolvedValue(smtpConfiguration)
  mocks.configureSmtp.mockResolvedValue(smtpConfiguration)
  mocks.testIntegration.mockResolvedValue({
    key: 'smtp',
    status: 'healthy',
    message: 'SMTP connection succeeded.',
    latency_ms: 12,
    checked_at: '2026-08-03T00:01:00Z',
  })
  mocks.sendSmtpTestEmail.mockResolvedValue({
    status: 'accepted',
    message: 'SMTP server accepted the message.',
    recipient: 'operator@example.test',
    message_id: '<safe-test-id@meetinghq>',
    latency_ms: 15,
    accepted_at: '2026-08-03T00:01:30Z',
  })
  mocks.smtpTemplatePreview.mockResolvedValue({
    key: 'smtp.test',
    version: '2026.09.1',
    subject: 'MeetingHQ | SMTP test successful',
    text: 'MeetingHQ SMTP test successful',
    html: '<!doctype html><html><body><h1>SMTP test successful</h1></body></html>',
  })
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

test('SMTP administration preserves a stored secret and tests the shared delivery path', async () => {
  const smtpProvider = {
    ...provider,
    key: 'smtp',
    name: 'SMTP',
    auth_type: 'smtp',
    configured: true,
    validated: true,
    health: 'healthy',
  }
  mocks.integrations.mockResolvedValue([smtpProvider])
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['integrations'], [smtpProvider])
  render(
    <QueryClientProvider client={client}>
      <IntegrationCenterPage />
    </QueryClientProvider>,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Configure' }))
  expect(
    await screen.findByRole('heading', { name: 'SMTP delivery' }),
  ).toBeVisible()
  expect(await screen.findByText('Credential stored securely')).toBeVisible()
  const password = screen.getByLabelText('Password / app password')
  expect(password).toHaveValue('')
  expect(password).toHaveAttribute(
    'placeholder',
    '•••••••••••• (leave blank to preserve)',
  )
  fireEvent.change(screen.getByLabelText('Provider display name'), {
    target: { value: 'Primary SMTP' },
  })
  fireEvent.click(
    screen.getByRole('button', { name: 'Save SMTP configuration' }),
  )
  await waitFor(() =>
    expect(mocks.configureSmtp).toHaveBeenCalledWith(
      expect.objectContaining({
        provider_display_name: 'Primary SMTP',
        password: '',
      }),
    ),
  )

  fireEvent.click(screen.getByRole('button', { name: 'Test & delivery' }))
  fireEvent.click(screen.getByRole('button', { name: 'Test connection' }))
  await waitFor(() =>
    expect(mocks.testIntegration).toHaveBeenCalledWith('smtp'),
  )
  fireEvent.change(screen.getByLabelText('SMTP test recipient'), {
    target: { value: 'operator@example.test' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send test email' }))
  await waitFor(() =>
    expect(mocks.sendSmtpTestEmail).toHaveBeenCalledWith(
      'operator@example.test',
    ),
  )
})

test('SMTP validation immediately enables test delivery for the current revision', async () => {
  const smtpProvider = {
    ...provider,
    key: 'smtp',
    name: 'SMTP',
    auth_type: 'smtp',
    configured: true,
    validated: false,
    health: 'attention',
  }
  mocks.integrations.mockResolvedValue([smtpProvider])
  mocks.smtpConfiguration.mockResolvedValue({
    ...smtpConfiguration,
    state: 'configured',
    last_validated_at: null,
  })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['integrations'], [smtpProvider])
  render(
    <QueryClientProvider client={client}>
      <IntegrationCenterPage />
    </QueryClientProvider>,
  )

  fireEvent.click(await screen.findByRole('button', { name: 'Configure' }))
  expect(await screen.findByText('Credential stored securely')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Test & delivery' }))
  fireEvent.change(screen.getByLabelText('SMTP test recipient'), {
    target: { value: ' operator@example.test ' },
  })
  const send = screen.getByRole('button', { name: 'Send test email' })
  expect(send).toBeDisabled()
  expect(
    screen.getByText(/Test the current SMTP configuration successfully/),
  ).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: 'Test connection' }))
  await waitFor(() => expect(send).toBeEnabled())
  fireEvent.click(send)
  await waitFor(() =>
    expect(mocks.sendSmtpTestEmail).toHaveBeenCalledWith(
      'operator@example.test',
    ),
  )
})

test('SMTP test delivery validates recipients and explains missing permission', async () => {
  const smtpProvider = {
    ...provider,
    key: 'smtp',
    name: 'SMTP',
    auth_type: 'smtp',
    configured: true,
    validated: true,
    health: 'healthy',
  }
  mocks.integrations.mockResolvedValue([smtpProvider])
  mocks.authPermissions.splice(
    0,
    mocks.authPermissions.length,
    'integrations.view',
  )
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['integrations'], [smtpProvider])
  render(
    <QueryClientProvider client={client}>
      <IntegrationCenterPage />
    </QueryClientProvider>,
  )

  fireEvent.click(await screen.findByRole('button', { name: 'Configure' }))
  expect(
    await screen.findByText(/do not have permission to change SMTP/),
  ).toBeVisible()
  expect(
    screen.getByRole('button', { name: 'Save SMTP configuration' }),
  ).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Test & delivery' }))
  fireEvent.change(screen.getByLabelText('SMTP test recipient'), {
    target: { value: 'not-an-email' },
  })
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Enter a valid recipient email address.',
  )
  expect(
    screen.getAllByText('You do not have permission to test SMTP.'),
  ).toHaveLength(2)
  expect(screen.getByRole('button', { name: 'Send test email' })).toBeDisabled()
})

test('saving SMTP configuration clears validation from the previous revision', async () => {
  const smtpProvider = {
    ...provider,
    key: 'smtp',
    name: 'SMTP',
    auth_type: 'smtp',
    configured: true,
    validated: true,
    health: 'healthy',
  }
  const nextRevision = {
    ...smtpConfiguration,
    state: 'configured',
    revision: 3,
    last_validated_at: null,
  }
  mocks.integrations.mockResolvedValue([smtpProvider])
  mocks.smtpConfiguration
    .mockResolvedValueOnce(smtpConfiguration)
    .mockResolvedValue(nextRevision)
  mocks.configureSmtp.mockResolvedValue(nextRevision)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['integrations'], [smtpProvider])
  render(
    <QueryClientProvider client={client}>
      <IntegrationCenterPage />
    </QueryClientProvider>,
  )

  fireEvent.click(await screen.findByRole('button', { name: 'Configure' }))
  expect(await screen.findByText('Credential stored securely')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Test & delivery' }))
  fireEvent.click(screen.getByRole('button', { name: 'Test connection' }))
  expect(await screen.findByText('SMTP connection succeeded.')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'setup' }))
  fireEvent.click(
    screen.getByRole('button', { name: 'Save SMTP configuration' }),
  )
  await waitFor(() => expect(mocks.configureSmtp).toHaveBeenCalled())
  fireEvent.click(screen.getByRole('button', { name: 'Test & delivery' }))
  expect(
    screen.queryByText('SMTP connection succeeded.'),
  ).not.toBeInTheDocument()
  expect(
    screen.getByText(/Test the current SMTP configuration successfully/),
  ).toBeVisible()
})

test('SMTP test delivery renders a safe provider failure', async () => {
  const smtpProvider = {
    ...provider,
    key: 'smtp',
    name: 'SMTP',
    auth_type: 'smtp',
    configured: true,
    validated: true,
    health: 'healthy',
  }
  mocks.integrations.mockResolvedValue([smtpProvider])
  mocks.sendSmtpTestEmail.mockResolvedValueOnce({
    status: 'failed',
    message: 'SMTP rejected the recipient address.',
    recipient: 'operator@example.test',
    message_id: null,
    latency_ms: 9,
    accepted_at: null,
  })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['integrations'], [smtpProvider])
  render(
    <QueryClientProvider client={client}>
      <IntegrationCenterPage />
    </QueryClientProvider>,
  )

  fireEvent.click(await screen.findByRole('button', { name: 'Configure' }))
  expect(await screen.findByText('Credential stored securely')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Test & delivery' }))
  fireEvent.change(screen.getByLabelText('SMTP test recipient'), {
    target: { value: 'operator@example.test' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send test email' }))
  expect(
    await screen.findByText('SMTP rejected the recipient address.'),
  ).toBeVisible()
})

test('SMTP administration previews safe branded transactional email without sending it', async () => {
  const smtpProvider = {
    ...provider,
    key: 'smtp',
    name: 'SMTP',
    auth_type: 'smtp',
    configured: true,
    validated: true,
    health: 'healthy',
  }
  mocks.integrations.mockResolvedValue([smtpProvider])
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['integrations'], [smtpProvider])
  render(
    <QueryClientProvider client={client}>
      <IntegrationCenterPage />
    </QueryClientProvider>,
  )

  fireEvent.click(await screen.findByRole('button', { name: 'Configure' }))
  fireEvent.click(screen.getByRole('button', { name: 'Email preview' }))
  expect(
    await screen.findByText('MeetingHQ | SMTP test successful'),
  ).toBeVisible()
  expect(mocks.smtpTemplatePreview).toHaveBeenCalledWith('smtp.test')
  expect(screen.getByTitle('Transactional email preview')).toHaveAttribute(
    'sandbox',
    '',
  )
  expect(mocks.sendSmtpTestEmail).not.toHaveBeenCalled()
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
