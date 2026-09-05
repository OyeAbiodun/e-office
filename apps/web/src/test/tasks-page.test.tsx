import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen } from '@testing-library/react'

import { TasksPage } from '@/features/tasks/tasks-page'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  dailySummary: vi.fn(),
  weeklySummary: vi.fn(),
  employees: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  recordActivity: vi.fn(),
}))

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({
    user: {
      permissions: ['tasks.view_own', 'tasks.create_own', 'tasks.edit_own'],
    },
  }),
}))

vi.mock('@/features/tasks/api', () => ({
  tasksApi: {
    list: mocks.list,
    dailySummary: mocks.dailySummary,
    weeklySummary: mocks.weeklySummary,
    create: mocks.create,
    update: mocks.update,
    recordActivity: mocks.recordActivity,
    get: vi.fn(),
    comment: vi.fn(),
  },
}))

vi.mock('@/features/users/api', () => ({
  userAdminApi: { employees: mocks.employees },
}))

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <TasksPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mocks.list.mockResolvedValue({
    items: [
      {
        id: 'task-1',
        sequence: 12,
        title: 'Prepare the customer review',
        description: null,
        status: 'not_started',
        priority: 'high',
        progress: null,
        assignee_id: 'user-1',
        created_by_id: 'user-1',
        assigned_by_id: null,
        department_id: null,
        team_id: null,
        meeting_id: null,
        meeting_action_item_id: null,
        start_date: null,
        due_date: '2026-09-05',
        completed_at: null,
        reminder_at: null,
        follow_up_at: null,
        tags: [],
        created_at: '2026-09-05T10:00:00Z',
        updated_at: '2026-09-05T10:00:00Z',
        is_overdue: false,
        overdue_days: 0,
        assignee_name: 'Taylor Example',
        department_name: null,
        meeting_title: null,
      },
    ],
    total: 1,
    page: 1,
    page_size: 25,
    total_pages: 1,
  })
  mocks.dailySummary.mockResolvedValue({
    completed_tasks: 1,
    in_progress_tasks: 2,
    activities: [],
    blockers: [],
    meetings_attended: 1,
  })
  mocks.weeklySummary.mockResolvedValue({
    completed_tasks: 3,
    pending_tasks: 2,
    overdue_tasks: 0,
    activity_count: 2,
    activity_minutes: 65,
    meetings_attended: 1,
    upcoming_due: 2,
  })
  mocks.employees.mockResolvedValue({ items: [] })
  mocks.create.mockResolvedValue({ id: 'task-created' })
})

test('shows live work summaries and supports lightweight task creation', async () => {
  renderPage()

  expect(await screen.findByText('Prepare the customer review')).toBeVisible()
  expect(screen.getByText('Today’s summary')).toBeVisible()
  expect(screen.getByRole('heading', { name: 'This week' })).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'My team' }),
  ).not.toBeInTheDocument()

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /new task/i }))
  })
  const title = await screen.findByLabelText('Title')
  await act(async () => {
    fireEvent.change(title, {
      target: { value: 'Send review notes' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  })

  await vi.waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1))
  expect(mocks.create.mock.calls[0]?.[0]).toEqual(
    expect.objectContaining({
      title: 'Send review notes',
      priority: 'normal',
    }),
  )
})
