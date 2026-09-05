import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { OrganizationPage } from '@/features/organizations/organization-page'

const organizationApiMock = vi.hoisted(() => ({
  organizationOverview: vi.fn(),
  organizationUnits: vi.fn(),
  organizationPolicies: vi.fn(),
  createOrganizationUnit: vi.fn(),
  members: vi.fn(),
  deleteOrganizationUnit: vi.fn(),
  updateOrganizationPolicy: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}))

vi.mock('@/features/organizations/api', () => ({
  organizationApi: organizationApiMock,
}))

const overview = {
  organization: {
    id: 'org-1',
    name: 'MeetingHQ',
    slug: 'meetinghq',
    logo_url: null,
    status: 'active',
    timezone: 'America/Chicago',
    country: 'US',
    default_language: 'en',
    brand_color: '#2563eb',
    settings: {},
  },
  member_count: 14,
  active_member_count: 12,
  workspace_count: 3,
  team_count: 5,
  pending_invitation_count: 2,
  department_count: 1,
  branch_count: 0,
  location_count: 1,
  administrators: [
    {
      id: 'user-1',
      display_name: 'Abiodun',
      email: 'textabi12@gmail.com',
      role: 'Super Admin',
    },
  ],
  recent_activity: [],
  audit_history: [],
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <OrganizationPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  organizationApiMock.organizationOverview.mockResolvedValue(overview)
  organizationApiMock.organizationUnits.mockResolvedValue([])
  organizationApiMock.organizationPolicies.mockResolvedValue({
    security: { enabled: true, enforcement: 'organization_default' },
  })
  organizationApiMock.createOrganizationUnit.mockResolvedValue({
    id: 'unit-1',
  })
  organizationApiMock.members.mockResolvedValue([])
  organizationApiMock.updateOrganizationPolicy.mockResolvedValue({
    enabled: false,
  })
})

test('renders live tenant metrics and administrator identity', async () => {
  renderPage()
  expect(
    await screen.findByRole('heading', { name: 'MeetingHQ' }),
  ).toBeVisible()
  expect(screen.getByText('14')).toBeVisible()
  expect(screen.getByText('12 active')).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: 'Administrators' }))
  expect(screen.getByText('textabi12@gmail.com')).toBeVisible()
  expect(screen.getByText('Super Admin')).toBeVisible()
})

test('creates structure and updates tenant policy through the backend API', async () => {
  renderPage()
  await screen.findByRole('heading', { name: 'MeetingHQ' })

  fireEvent.click(screen.getByRole('button', { name: 'Structure' }))
  fireEvent.change(screen.getByLabelText('Name'), {
    target: { value: 'Product Engineering' },
  })
  fireEvent.change(screen.getByLabelText('Code'), {
    target: { value: 'ENG' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Add unit' }))
  await waitFor(() =>
    expect(organizationApiMock.createOrganizationUnit).toHaveBeenCalledWith({
      name: 'Product Engineering',
      code: 'ENG',
      unit_type: 'department',
      manager_id: null,
      status: 'active',
      address: {},
      working_hours: {},
    }),
  )

  fireEvent.click(screen.getByRole('button', { name: 'Policies' }))
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Disable Security policies',
    }),
  )
  expect(organizationApiMock.updateOrganizationPolicy).toHaveBeenCalledWith(
    'security',
    {
      enabled: false,
      enforcement: 'organization_default',
    },
  )
})
