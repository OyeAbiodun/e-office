import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'

import { UserManagementPage } from '@/features/users/user-management-page'

const mocks = vi.hoisted(() => ({
  employees: vi.fn(),
  employmentHistory: vi.fn(),
  roles: vi.fn(),
  workspaces: vi.fn(),
  units: vi.fn(),
  teams: vi.fn(),
  confirm: vi.fn(async () => true),
}))

vi.mock('@/components/feedback/confirmation', () => ({
  useConfirmation: () => mocks.confirm,
}))

vi.mock('@/features/users/api', () => ({
  userAdminApi: {
    employees: mocks.employees,
    employmentHistory: mocks.employmentHistory,
    roles: mocks.roles,
    create: vi.fn(),
    update: vi.fn(),
    activate: vi.fn(),
    disable: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
    resetPassword: vi.fn(),
    bulk: vi.fn(),
    terminate: vi.fn(),
    rehire: vi.fn(),
  },
}))

vi.mock('@/features/organizations/api', () => ({
  organizationApi: {
    workspaces: mocks.workspaces,
    organizationUnits: mocks.units,
  },
}))

vi.mock('@/features/teams/api', () => ({
  teamsApi: { list: mocks.teams },
}))

const employee = {
  id: 'employee-1',
  organization_id: 'organization-1',
  email: 'elliot@example.test',
  username: 'elliot',
  first_name: 'Elliot',
  last_name: 'Employee',
  display_name: 'Elliot Employee',
  avatar_url: null,
  phone: null,
  alternative_phone: null,
  job_title: 'Product manager',
  department: 'Product',
  department_id: 'department-1',
  manager_id: null,
  employee_number: 'EMP-001',
  employment_status: 'active' as const,
  employment_type: 'permanent' as const,
  employment_start_date: '2026-01-05',
  employment_confirmation_date: null,
  employment_end_date: null,
  location: null,
  workspace_id: 'workspace-1',
  team_id: null,
  status: 'active' as const,
  email_verified: true,
  force_password_change: false,
  last_login: null,
  timezone: 'UTC',
  language: 'en',
  notification_preferences: {},
  roles: [
    {
      id: 'role-employee',
      organization_id: 'organization-1',
      name: 'Employee',
      description: null,
      system_role: true,
      member_count: 1,
      permissions: [],
    },
  ],
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <UserManagementPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mocks.employees.mockResolvedValue({
    items: [employee],
    total: 1,
    page: 1,
    page_size: 100,
    total_pages: 1,
  })
  mocks.employmentHistory.mockResolvedValue({
    items: [
      {
        id: 'history-1',
        user_id: employee.id,
        changed_by: null,
        change_type: 'hired',
        old_values: {},
        new_values: { employee_number: 'EMP-001' },
        effective_date: '2026-01-05',
        reason: null,
        created_at: '2026-01-05T09:00:00Z',
      },
    ],
    total: 1,
    page: 1,
    page_size: 25,
    total_pages: 1,
  })
  mocks.roles.mockResolvedValue(employee.roles)
  mocks.workspaces.mockResolvedValue([{ id: 'workspace-1', name: 'Main' }])
  mocks.units.mockResolvedValue([
    { id: 'department-1', name: 'Product', unit_type: 'department' },
  ])
  mocks.teams.mockResolvedValue([])
})

test('employee editor exposes organization context and effective-dated history', async () => {
  renderPage()
  expect(await screen.findByText('Elliot Employee')).toBeVisible()
  expect(screen.getByText(/Product · permanent/)).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: 'Elliot Employee' }))
  expect(await screen.findByText('Employment history')).toBeVisible()
  expect(await screen.findByText('Hired')).toBeVisible()
  expect(screen.getByDisplayValue('EMP-001')).toBeVisible()
  expect(screen.getByRole('combobox', { name: 'Department' })).toHaveValue(
    'department-1',
  )
  expect(screen.getByRole('textbox', { name: 'Effective date' })).toBeVisible()
  expect(screen.getByRole('textbox', { name: 'Change reason' })).toBeVisible()
})
