import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { AnchorHTMLAttributes, ReactNode } from 'react'

import { ProjectsPage } from '@/features/projects/projects-page'

const mocks = vi.hoisted(() => ({
  permissions: ['projects.view', 'projects.create', 'projects.edit'],
  list: vi.fn(),
  create: vi.fn(),
  assignees: vi.fn(),
}))

vi.mock('@tanstack/react-router', async (original) => {
  const actual = await original<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
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
  useAuth: () => ({ user: { id: 'user-1', permissions: mocks.permissions } }),
}))

vi.mock('@/features/projects/api', () => ({
  projectsApi: {
    list: mocks.list,
    create: mocks.create,
  },
}))

vi.mock('@/features/tasks/api', () => ({
  tasksApi: { assignees: mocks.assignees },
}))

function renderPage(node: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.permissions = ['projects.view', 'projects.create', 'projects.edit']
  mocks.list.mockResolvedValue({
    items: [
      {
        id: 'project-1',
        project_code: 'PRJ-2026-0001',
        name: 'Customer portal rollout',
        description: 'Coordinate the production rollout.',
        project_manager_id: 'user-1',
        manager_name: 'Nora Admin',
        department_id: null,
        department_name: null,
        start_date: '2026-09-13',
        target_end_date: '2026-10-13',
        actual_end_date: null,
        status: 'active',
        priority: 'high',
        health: 'on_track',
        progress: 50,
        visibility: 'members',
        archived_at: null,
        created_at: '2026-09-13T12:00:00Z',
        member_count: 4,
        task_count: 6,
        completed_task_count: 3,
        overdue_task_count: 1,
        milestone_count: 2,
        open_risk_count: 1,
        open_issue_count: 0,
      },
    ],
    total: 1,
    page: 1,
    page_size: 25,
    total_pages: 1,
  })
  mocks.assignees.mockResolvedValue([
    { id: 'user-1', display_name: 'Nora Admin', job_title: 'Administrator' },
  ])
  mocks.create.mockResolvedValue({ id: 'project-2' })
})

test('renders live project delivery state and filters', async () => {
  renderPage(<ProjectsPage />)

  expect(await screen.findByText('Customer portal rollout')).toBeVisible()
  expect(screen.getByText('PRJ-2026-0001')).toBeVisible()
  expect(screen.getByText('50%')).toBeVisible()
  expect(screen.getByText(/1 overdue/)).toBeVisible()

  fireEvent.change(screen.getByLabelText('Search projects'), {
    target: { value: 'portal' },
  })
  await waitFor(() =>
    expect(mocks.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: 'portal', page: 1, page_size: 25 }),
    ),
  )
})

test('creates a project through the lightweight enterprise flow', async () => {
  renderPage(<ProjectsPage />)
  await screen.findByText('Customer portal rollout')
  fireEvent.click(screen.getByRole('button', { name: /new project/i }))
  fireEvent.change(screen.getByLabelText('Project name'), {
    target: { value: 'Finance modernization' },
  })
  await screen.findByRole('option', { name: /Nora Admin/ }, { timeout: 5_000 })
  fireEvent.change(screen.getByLabelText('Project manager'), {
    target: { value: 'user-1' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Create project' }))

  await waitFor(() =>
    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Finance modernization',
        project_manager_id: 'user-1',
        priority: 'normal',
      }),
      expect.anything(),
    ),
  )
})

test('hides create actions when permission is absent', async () => {
  mocks.permissions = ['projects.view']
  renderPage(<ProjectsPage />)
  await screen.findByText('Customer portal rollout')
  expect(
    screen.queryByRole('button', { name: /new project/i }),
  ).not.toBeInTheDocument()
})
