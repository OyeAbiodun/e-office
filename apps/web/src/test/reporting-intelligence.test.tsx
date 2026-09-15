import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { AnchorHTMLAttributes, ReactNode } from 'react'

import { ReportDetailPage } from '@/features/reports/report-detail-page'
import { ReportsPage } from '@/features/reports/reports-page'

const mocks = vi.hoisted(() => ({
  permissions: [
    'reports.view_own',
    'reports.create_own',
    'reports.submit_own',
    'reports.review_team',
    'reports.manage_policy',
    'reports.export',
  ],
  dashboard: vi.fn(),
  list: vi.fn(),
  detail: vi.fn(),
  preview: vi.fn(),
  policy: vi.fn(),
  updatePolicy: vi.fn(),
  generate: vi.fn(),
  edit: vi.fn(),
  submit: vi.fn(),
  review: vi.fn(),
  export: vi.fn(),
  assignees: vi.fn(),
  departments: vi.fn(),
  teams: vi.fn(),
  projects: vi.fn(),
}))

vi.mock('@tanstack/react-router', async (original) => {
  const actual = await original<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useParams: () => ({ reportId: 'report-1' }),
    useNavigate: () => vi.fn(),
    Link: ({
      children,
      to,
      ...props
    }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
  }
})

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({
    user: {
      id: 'employee-1',
      display_name: 'Riley Reporter',
      permissions: mocks.permissions,
    },
  }),
}))

vi.mock('@/features/reports/api', () => ({
  reportsApi: {
    dashboard: mocks.dashboard,
    list: mocks.list,
    detail: mocks.detail,
    preview: mocks.preview,
    policy: mocks.policy,
    updatePolicy: mocks.updatePolicy,
    generate: mocks.generate,
    edit: mocks.edit,
    submit: mocks.submit,
    review: mocks.review,
    export: mocks.export,
  },
}))

vi.mock('@/features/tasks/api', () => ({
  tasksApi: { assignees: mocks.assignees },
}))
vi.mock('@/features/organizations/api', () => ({
  organizationApi: { departments: mocks.departments, teams: mocks.teams },
}))
vi.mock('@/features/projects/api', () => ({
  projectsApi: { list: mocks.projects },
}))

const report = {
  id: 'report-1',
  report_type: 'employee',
  subject_type: 'employee',
  subject_id: 'employee-1',
  subject_name: 'Riley Reporter',
  owner_id: 'employee-1',
  manager_id: 'manager-1',
  period_type: 'weekly',
  period_start: '2026-09-07',
  period_end: '2026-09-13',
  timezone: 'UTC',
  status: 'submitted',
  submission_mode: 'manual',
  version: 2,
  authoritative_snapshot: {
    summary: {
      tasks_total: 8,
      tasks_completed: 6,
      tasks_overdue: 1,
      activities: 5,
      meetings: 2,
      projects: 1,
    },
  },
  narrative: { accomplishments: 'Completed the verified rollout.' },
  source_refs: [],
  policy_snapshot: {},
  reviewer_id: null,
  review_comment: null,
  return_reason: null,
  generated_at: '2026-09-13T12:00:00Z',
  submitted_at: '2026-09-13T13:00:00Z',
  reviewed_at: null,
  finalized_at: null,
  submission_reminder_sent_at: null,
}

function renderPage(node: ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {node}
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.dashboard.mockResolvedValue({
    pending_my_review: 1,
    awaiting_manager_review: 2,
    returned: 0,
    finalized_this_period: 4,
    reporting_compliance_percent: 80,
    active_projects: 3,
    projects_at_risk: 1,
    open_tasks: 12,
    overdue_tasks: 2,
    unresolved_blockers: 1,
    department_activity: [{ department: 'Operations', activities: 7 }],
  })
  mocks.list.mockResolvedValue({
    items: [report],
    total: 1,
    page: 1,
    page_size: 25,
    total_pages: 1,
  })
  mocks.preview.mockResolvedValue({
    snapshot: { summary: {} },
    source_refs: [],
  })
  mocks.assignees.mockResolvedValue([
    { id: 'employee-1', display_name: 'Riley Reporter' },
  ])
  mocks.departments.mockResolvedValue({ items: [] })
  mocks.teams.mockResolvedValue([])
  mocks.projects.mockResolvedValue({ items: [] })
  mocks.policy.mockResolvedValue({
    id: 'policy-1',
    organization_id: 'org-1',
    daily_enabled: true,
    weekly_enabled: true,
    monthly_enabled: true,
    review_before_send: true,
    automatic_submit: false,
    week_start: 0,
    week_end: 6,
    generation_time: '18:00:00',
    submission_deadline_hours: 24,
    manager_review_required: true,
    reminder_hours_before: 4,
    timezone: 'UTC',
    enabled_report_types: ['daily', 'weekly', 'monthly', 'custom'],
    updated_at: '2026-09-13T12:00:00Z',
  })
  mocks.detail.mockResolvedValue({
    report,
    versions: [
      {
        id: 'version-1',
        version: 1,
        snapshot: {},
        narrative: {},
        created_at: report.generated_at,
      },
    ],
    history: [
      {
        id: 'history-1',
        actor_id: 'employee-1',
        action: 'submitted',
        note: null,
        created_at: report.submitted_at,
      },
    ],
  })
  mocks.review.mockResolvedValue({ ...report, status: 'final' })
})

test('renders live management intelligence and report history', async () => {
  renderPage(<ReportsPage />)
  expect(await screen.findByText('Reporting compliance')).toBeVisible()
  expect(await screen.findByText('80%')).toBeVisible()
  expect(screen.getByText('Operations')).toBeVisible()
  expect(screen.getByText('Riley Reporter')).toBeVisible()
  expect(
    screen.getByRole('region', { name: 'Work delivery chart' }),
  ).toBeVisible()
  expect(
    screen.getByRole('link', {
      name: 'Overdue tasks: 2. Open filtered results',
    }),
  ).toHaveAttribute('href', '/tasks?due=overdue')
})

test('keeps report lists bounded and supports server page-size selection', async () => {
  renderPage(<ReportsPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Report history' }))
  expect(
    await screen.findByRole('heading', { name: 'Report history' }),
  ).toBeVisible()
  expect(document.querySelector('[data-report-list]')).toHaveClass(
    'data-region',
  )
  fireEvent.change(screen.getByLabelText('Rows'), { target: { value: '10' } })
  await waitFor(() =>
    expect(mocks.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ page_size: 10 }),
    ),
  )
})

test('exposes manager review and organization policy controls by permission', async () => {
  renderPage(<ReportsPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Manager review' }))
  await waitFor(() =>
    expect(mocks.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'pending_review' }),
    ),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Reporting policy' }))
  expect(await screen.findByText('Organization reporting policy')).toBeVisible()
  expect(
    screen.getByLabelText('Automatically submit generated reports'),
  ).not.toBeChecked()
})

test('reviews a submitted report and shows immutable source metrics', async () => {
  renderPage(<ReportDetailPage />)
  expect(await screen.findByText('Report narrative')).toBeVisible()
  expect(screen.getByText('8')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: /accept and finalize/i }))
  await waitFor(() =>
    expect(mocks.review).toHaveBeenCalledWith('report-1', 'accept', undefined),
  )
})

test('requires a reason before returning a report', async () => {
  renderPage(<ReportDetailPage />)
  const button = await screen.findByRole('button', { name: 'Return' })
  expect(button).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Return note'), {
    target: { value: 'Add the customer validation outcome.' },
  })
  fireEvent.click(button)
  await waitFor(() =>
    expect(mocks.review).toHaveBeenCalledWith(
      'report-1',
      'return',
      'Add the customer validation outcome.',
    ),
  )
})
