import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { WorkspaceDetailPage } from '@/features/workspaces/workspace-detail-page'
import { WorkspaceListPage } from '@/features/workspaces/workspace-list-page'

const api = vi.hoisted(() => ({
  searchWorkspaces: vi.fn(),
  workspaceTemplates: vi.fn(),
  createWorkspace: vi.fn(),
  bulkWorkspaceLifecycle: vi.fn(),
  workspaceOverview: vi.fn(),
  workspaceMembers: vi.fn(),
  workspaceIntegrations: vi.fn(),
  archiveWorkspace: vi.fn(),
  restoreWorkspace: vi.fn(),
  updateWorkspace: vi.fn(),
  updateWorkspaceIntegration: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useParams: () => ({ workspaceId: 'workspace-1' }),
}))
vi.mock('@/features/organizations/api', () => ({ organizationApi: api }))

const workspace = {
  id: 'workspace-1',
  organization_id: 'org-1',
  name: 'Main Workspace',
  slug: 'main',
  description: 'Primary collaboration workspace',
  logo_url: null,
  brand_color: '#2563eb',
  classification: 'internal',
  visibility: 'members',
  data_region: 'us-central',
  owner_id: 'user-1',
  settings: {},
  archived_at: null,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

function renderWithClient(component: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {component}
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.searchWorkspaces.mockResolvedValue([workspace])
  api.workspaceTemplates.mockResolvedValue([])
  api.workspaceOverview.mockResolvedValue({
    workspace,
    team_count: 2,
    member_count: 8,
    administrator_count: 1,
    channel_count: 4,
    meeting_count: 11,
    calendar_count: 2,
    file_count: 6,
    storage_bytes: 2048,
    app_count: 1,
    recent_activity: [],
    audit_history: [],
  })
  api.workspaceMembers.mockResolvedValue([
    {
      id: 'membership-1',
      user_id: 'user-1',
      display_name: 'Abiodun',
      email: 'textabi12@gmail.com',
      role: 'owner',
      created_at: '2026-08-01T00:00:00Z',
    },
  ])
  api.workspaceIntegrations.mockResolvedValue([])
  api.updateWorkspace.mockResolvedValue(workspace)
  api.updateWorkspaceIntegration.mockResolvedValue({})
})

test('searches, selects, and archives workspaces through persisted APIs', async () => {
  renderWithClient(<WorkspaceListPage />)
  expect(await screen.findByText('Main Workspace')).toBeVisible()
  fireEvent.change(screen.getByLabelText('Search workspaces'), {
    target: { value: 'main' },
  })
  await waitFor(() =>
    expect(api.searchWorkspaces).toHaveBeenLastCalledWith({
      search: 'main',
      archived: false,
    }),
  )
  fireEvent.click(await screen.findByLabelText('Select Main Workspace'))
  fireEvent.click(screen.getByRole('button', { name: 'Archive' }))
  await waitFor(() =>
    expect(api.bulkWorkspaceLifecycle).toHaveBeenCalledWith(
      ['workspace-1'],
      'archive',
    ),
  )
})

test('renders live workspace footprint and persists governance changes', async () => {
  renderWithClient(<WorkspaceDetailPage />)
  expect(
    await screen.findByRole('heading', { name: 'Main Workspace' }),
  ).toBeVisible()
  expect(screen.getByText('11')).toBeVisible()
  expect(screen.getByText('2.0 KB')).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: 'Settings & policies' }))
  fireEvent.change(screen.getByLabelText('Classification'), {
    target: { value: 'confidential' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await waitFor(() =>
    expect(api.updateWorkspace).toHaveBeenCalledWith(
      'workspace-1',
      expect.objectContaining({ classification: 'confidential' }),
    ),
  )

  fireEvent.click(screen.getByRole('button', { name: 'Apps & integrations' }))
  fireEvent.click(screen.getAllByRole('button', { name: 'Connect' })[0]!)
  expect(api.updateWorkspaceIntegration).toHaveBeenCalledWith('workspace-1', {
    provider: 'sharepoint',
    display_name: 'SharePoint',
    enabled: true,
    configuration: {},
  })
})
