import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'

import { LeaveAdminPage } from '@/features/leave/leave-admin-page'
import { LeaveManagerPage } from '@/features/leave/leave-manager-page'
import { LeavePage, LeaveRequestDetailPage } from '@/features/leave/leave-page'

const mocks = vi.hoisted(() => ({
  userId: 'employee-1',
  permissions: ['leave.view_own', 'leave.request'],
  mySummary: vi.fn(),
  types: vi.fn(),
  requests: vi.fn(),
  preview: vi.fn(),
  createRequest: vi.fn(),
  submit: vi.fn(),
  request: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
  managerSummary: vi.fn(),
  availability: vi.fn(),
  balances: vi.fn(),
  periods: vi.fn(),
  ledger: vi.fn(),
  adjust: vi.fn(),
  workingWeek: vi.fn(),
  usageReport: vi.fn(),
  statusReport: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to }: { children: ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useParams: () => ({ requestId: 'request-1' }),
}))

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({
    user: { id: mocks.userId, permissions: mocks.permissions },
  }),
}))

vi.mock('@/components/feedback/confirmation', () => ({
  useConfirmation: () => vi.fn().mockResolvedValue(true),
}))

vi.mock('@/features/leave/api', () => ({
  leaveApi: {
    mySummary: mocks.mySummary,
    types: mocks.types,
    requests: mocks.requests,
    preview: mocks.preview,
    createRequest: mocks.createRequest,
    submit: mocks.submit,
    request: mocks.request,
    approve: mocks.approve,
    reject: mocks.reject,
    withdraw: vi.fn(),
    cancel: vi.fn(),
    downloadAttachment: vi.fn(),
    deleteAttachment: vi.fn(),
    uploadAttachment: vi.fn(),
    managerSummary: mocks.managerSummary,
    availability: mocks.availability,
    balances: mocks.balances,
    periods: mocks.periods,
    ledger: mocks.ledger,
    adjust: mocks.adjust,
    workingWeek: mocks.workingWeek,
    usageReport: mocks.usageReport,
    statusReport: mocks.statusReport,
    exportBalances: vi.fn(),
    exportUsage: vi.fn(),
    createType: vi.fn(),
    updateType: vi.fn(),
    setTypeActive: vi.fn(),
    createPeriod: vi.fn(),
    setPeriodStatus: vi.fn(),
    updateWorkingWeek: vi.fn(),
  },
}))

vi.mock('@/features/users/api', () => ({
  userAdminApi: {
    employees: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}))
vi.mock('@/features/organizations/api', () => ({
  organizationApi: {
    departments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}))
vi.mock('@/features/calendar/api', () => ({
  calendarApi: {
    holidays: vi.fn().mockResolvedValue([]),
    createHoliday: vi.fn(),
    deleteHoliday: vi.fn(),
  },
}))

const type = {
  id: 'type-1',
  name: 'Annual Leave',
  code: 'ANNUAL',
  description: 'Rest and recharge',
  is_active: true,
  is_paid: true,
  default_entitlement: 20,
  accrual_enabled: false,
  accrual_frequency: null,
  carryover_enabled: true,
  carryover_limit: 5,
  carryover_expiry_months: 3,
  minimum_notice_days: 2,
  maximum_consecutive_days: 10,
  attachment_required: false,
  half_day_supported: true,
  eligible_employment_types: 'permanent',
  probation_eligible: true,
  color: '#3b82f6',
}
const balance = {
  entitlement_id: 'entitlement-1',
  employee_id: 'employee-1',
  leave_type_id: 'type-1',
  leave_period_id: 'period-1',
  entitled: 20,
  accrued: 0,
  carried_forward: 2,
  adjustments: 0,
  used: 5,
  pending: 3,
  expired: 0,
  available: 15,
  available_after_pending: 12,
}
const request = {
  id: 'request-1',
  employee_id: 'employee-1',
  employee_number: 'EMP-001',
  employee_name: 'Taylor Example',
  department_id: 'department-1',
  department_name: 'Product',
  leave_type_id: 'type-1',
  leave_type_name: 'Annual Leave',
  leave_type_code: 'ANNUAL',
  leave_period_id: 'period-1',
  leave_period_name: '2026',
  start_date: '2026-10-05',
  end_date: '2026-10-07',
  duration_days: 3,
  half_day: false,
  reason: 'Family time',
  status: 'submitted',
  reviewed_by_id: null,
  reviewed_at: null,
  review_comment: null,
  calendar_event_id: null,
  created_at: '2026-09-08T10:00:00Z',
  updated_at: '2026-09-08T10:00:00Z',
}

function renderPage(node: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.userId = 'employee-1'
  mocks.permissions = ['leave.view_own', 'leave.request']
  mocks.types.mockResolvedValue([type])
  mocks.mySummary.mockResolvedValue({
    balances: [balance],
    pending_requests: [request],
    upcoming_approved: [],
    recent_history: [request],
  })
  mocks.requests.mockResolvedValue({
    items: [request],
    total: 1,
    page: 1,
    page_size: 10,
  })
  mocks.preview.mockResolvedValue({
    calendar_span: 3,
    excluded_non_working_days: 1,
    excluded_holidays: 0,
    chargeable_days: 2,
  })
  mocks.createRequest.mockResolvedValue({ ...request, status: 'draft' })
  mocks.submit.mockResolvedValue(request)
  mocks.request.mockResolvedValue({
    ...request,
    manager_id: 'manager-1',
    manager_name: 'Morgan Manager',
    reviewer_name: null,
    balance_effect: 0,
    attachments: [],
    history: [
      {
        id: 'history-1',
        event_type: 'submitted',
        comment: null,
        actor_id: 'employee-1',
        created_at: '2026-09-08T10:00:00Z',
      },
    ],
  })
  mocks.approve.mockResolvedValue({ ...request, status: 'approved' })
  mocks.reject.mockResolvedValue({ ...request, status: 'rejected' })
  mocks.managerSummary.mockResolvedValue({
    pending_count: 1,
    pending: [request],
    away_today: [],
    upcoming: [],
    recently_reviewed: [],
  })
  mocks.availability.mockResolvedValue([])
  mocks.periods.mockResolvedValue([
    {
      id: 'period-1',
      name: '2026',
      start_date: '2026-01-01',
      end_date: '2026-12-31',
      status: 'open',
    },
  ])
  mocks.balances.mockResolvedValue({
    items: [
      {
        ...balance,
        employee_number: 'EMP-001',
        employee_name: 'Taylor Example',
        department_id: 'department-1',
        department_name: 'Product',
        leave_type_name: 'Annual Leave',
        leave_type_code: 'ANNUAL',
        period_name: '2026',
      },
    ],
    total: 1,
    page: 1,
    page_size: 25,
  })
  mocks.ledger.mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 25,
  })
  mocks.workingWeek.mockResolvedValue({
    weekdays: [0, 1, 2, 3, 4],
    exclude_holidays: true,
  })
  mocks.usageReport.mockResolvedValue([])
  mocks.statusReport.mockResolvedValue([])
})

test('My Leave explains balances and uses backend working-day preview', async () => {
  renderPage(<LeavePage />)

  expect(await screen.findByRole('heading', { name: 'My Leave' })).toBeVisible()
  expect(screen.getByText('12')).toBeVisible()
  expect(screen.getByText('days available')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: /request leave/i }))
  fireEvent.change(screen.getByLabelText('Start date'), {
    target: { value: '2026-10-05' },
  })
  fireEvent.change(screen.getByLabelText('End date'), {
    target: { value: '2026-10-07' },
  })

  expect(await screen.findByText('2 days')).toBeVisible()
  expect(mocks.preview).toHaveBeenCalledWith({
    start_date: '2026-10-05',
    end_date: '2026-10-07',
    half_day: false,
  })
})

test('submits a valid leave request after preview', async () => {
  renderPage(<LeavePage />)
  await screen.findByRole('heading', { name: 'My Leave' })
  fireEvent.click(screen.getByRole('button', { name: /request leave/i }))
  fireEvent.change(screen.getByLabelText('Start date'), {
    target: { value: '2026-10-05' },
  })
  fireEvent.change(screen.getByLabelText('End date'), {
    target: { value: '2026-10-07' },
  })
  await screen.findByText('2 days')
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Submit request' }))
  })

  await vi.waitFor(() => expect(mocks.createRequest).toHaveBeenCalledTimes(1))
  await vi.waitFor(() => expect(mocks.submit).toHaveBeenCalledWith('request-1'))
})

test('blocks requests that exceed the available balance with a clear explanation', async () => {
  mocks.preview.mockResolvedValueOnce({
    calendar_span: 25,
    excluded_non_working_days: 7,
    excluded_holidays: 0,
    chargeable_days: 18,
  })
  renderPage(<LeavePage />)
  await screen.findByRole('heading', { name: 'My Leave' })
  fireEvent.click(screen.getByRole('button', { name: /request leave/i }))
  fireEvent.change(screen.getByLabelText('Start date'), {
    target: { value: '2026-10-05' },
  })
  fireEvent.change(screen.getByLabelText('End date'), {
    target: { value: '2026-10-29' },
  })

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'You have 12 days available, but this request requires 18 days.',
  )
  expect(screen.getByRole('button', { name: 'Submit request' })).toBeDisabled()
})

test('enforces required supporting documents before submission', async () => {
  mocks.types.mockResolvedValueOnce([{ ...type, attachment_required: true }])
  renderPage(<LeavePage />)
  await screen.findByRole('heading', { name: 'My Leave' })
  fireEvent.click(screen.getByRole('button', { name: /request leave/i }))
  fireEvent.change(screen.getByLabelText('Start date'), {
    target: { value: '2026-10-05' },
  })
  fireEvent.change(screen.getByLabelText('End date'), {
    target: { value: '2026-10-07' },
  })

  expect(
    await screen.findByText('required', { selector: 'span' }),
  ).toBeVisible()
  expect(screen.getByRole('button', { name: 'Submit request' })).toBeDisabled()
  const document = new File(['supporting evidence'], 'support.pdf', {
    type: 'application/pdf',
  })
  fireEvent.change(screen.getByLabelText(/Supporting document/), {
    target: { files: [document] },
  })
  expect(screen.getByText(/support\.pdf/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Submit request' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Remove support.pdf' }))
  expect(screen.queryByText(/support\.pdf/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Submit request' })).toBeDisabled()
})

test('manager workspace exposes only manager views and pending reviews', async () => {
  mocks.permissions = [
    'leave.view_own',
    'leave.view_team',
    'leave.approve',
    'leave.reject',
  ]
  renderPage(<LeaveManagerPage />)

  expect(
    await screen.findByRole('heading', { name: 'Team Leave' }),
  ).toBeVisible()
  expect(screen.getByText('Taylor Example')).toBeVisible()
  expect(screen.getByText('Pending requests (1)')).toBeVisible()
  expect(mocks.requests).toHaveBeenCalledWith(
    expect.objectContaining({ scope: 'pending' }),
  )
})

test('request detail exposes review actions only with manager permissions', async () => {
  mocks.userId = 'manager-1'
  mocks.permissions = ['leave.view_team', 'leave.approve', 'leave.reject']
  renderPage(<LeaveRequestDetailPage />)

  expect(
    await screen.findByRole('heading', { name: 'Annual Leave' }),
  ).toBeVisible()
  expect(screen.getByRole('button', { name: 'Approve' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
  expect(screen.getByLabelText('Reason for rejection')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Reject request' })).toBeDisabled()
})

test('employee request detail does not expose manager review actions', async () => {
  mocks.permissions = ['leave.view_own', 'leave.request']
  renderPage(<LeaveRequestDetailPage />)

  await screen.findByRole('heading', { name: 'Annual Leave' })
  expect(
    screen.queryByRole('button', { name: 'Approve' }),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: 'Reject' }),
  ).not.toBeInTheDocument()
})

test('admin balance management provides filters and controlled adjustment', async () => {
  mocks.permissions = [
    'leave.types.view',
    'leave.types.manage',
    'leave.balances.adjust',
    'leave.holidays.manage',
    'leave.reports.view',
    'leave.export',
  ]
  renderPage(<LeaveAdminPage />)
  expect(
    await screen.findByRole('heading', { name: 'Leave Administration' }),
  ).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: /Leave Balances/ }))
  expect(await screen.findByText('Taylor Example')).toBeVisible()
  fireEvent.click(
    screen.getByRole('button', { name: 'Adjust Taylor Example balance' }),
  )
  expect(
    screen.getByRole('heading', { name: 'Adjust leave balance' }),
  ).toBeVisible()
  expect(
    screen.getByText(
      'Every change creates an immutable ledger and audit entry.',
    ),
  ).toBeVisible()
  expect(screen.getByLabelText('Adjustment type')).toHaveValue('add')
})

test('admin exposes balance history, periods, and data-driven reports', async () => {
  mocks.permissions = [
    'leave.types.view',
    'leave.types.manage',
    'leave.balances.adjust',
    'leave.holidays.manage',
    'leave.reports.view',
    'leave.export',
  ]
  mocks.ledger.mockResolvedValueOnce({
    items: [
      {
        id: 'ledger-1',
        employee_id: 'employee-1',
        leave_type_id: 'type-1',
        leave_period_id: 'period-1',
        entry_type: 'adjustment',
        amount: 1,
        effective_date: '2026-09-08',
        reason: 'Annual allocation correction',
        reference_id: null,
        actor_id: 'manager-1',
        actor_name: 'Morgan Manager',
        created_at: '2026-09-08T10:00:00Z',
      },
    ],
    total: 1,
    page: 1,
    page_size: 25,
  })
  renderPage(<LeaveAdminPage />)
  await screen.findByRole('heading', { name: 'Leave Administration' })

  fireEvent.click(screen.getByRole('button', { name: /Leave Balances/ }))
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'View Taylor Example balance history',
    }),
  )
  expect(
    await screen.findByRole('heading', { name: 'Balance history' }),
  ).toBeVisible()
  expect(await screen.findByText('Morgan Manager')).toBeVisible()
  expect(screen.getByText('Annual allocation correction')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Close dialog' }))

  fireEvent.click(screen.getByRole('button', { name: /Leave Periods/ }))
  expect(await screen.findByText('Current/open period')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: /Reports/ }))
  expect(
    await screen.findByRole('heading', { name: 'Leave Reports' }),
  ).toBeVisible()
  expect(screen.getByRole('button', { name: 'Export CSV' })).toBeVisible()
})

test('admin navigation hides configuration areas without permissions', async () => {
  mocks.permissions = ['leave.view_own']
  renderPage(<LeaveAdminPage />)
  expect(
    await screen.findByRole('heading', { name: 'Access denied' }),
  ).toBeVisible()
  expect(
    screen.queryByRole('button', { name: /Leave Balances/ }),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: /Reports/ }),
  ).not.toBeInTheDocument()
})

test('My Leave renders a useful retry state when the backend is unavailable', async () => {
  mocks.mySummary.mockRejectedValueOnce(new Error('offline'))
  renderPage(<LeavePage />)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Leave information could not be loaded',
  )
  expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible()
})
