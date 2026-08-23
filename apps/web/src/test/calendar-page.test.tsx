import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const calendarMocks = vi.hoisted(() => ({
  calendars: vi.fn(),
  events: vi.fn(),
  resources: vi.fn(),
  holidays: vi.fn(),
  categories: vi.fn(),
  availability: vi.fn(),
  shares: vi.fn(),
  createEvent: vi.fn(),
  updateEvent: vi.fn(),
  deleteEvent: vi.fn(),
  setRecurrence: vi.fn(),
  reserve: vi.fn(),
  createResource: vi.fn(),
  importIcs: vi.fn(),
  exportIcs: vi.fn(),
  createAvailability: vi.fn(),
  deleteAvailability: vi.fn(),
  suggestions: vi.fn(),
  share: vi.fn(),
  revokeShare: vi.fn(),
  createCategory: vi.fn(),
}))

vi.mock('@/features/calendar/api', () => ({ calendarApi: calendarMocks }))
vi.mock('@/features/organizations/api', () => ({
  organizationApi: {
    workspaces: vi.fn().mockResolvedValue([{ id: 'workspace-1' }]),
    members: vi.fn().mockResolvedValue([]),
  },
}))
vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    to,
    activeProps,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    to: string
    activeProps?: object
  }) => {
    void activeProps
    return (
      <a href={to} {...props}>
        {children}
      </a>
    )
  },
}))

import { CalendarPage } from '@/features/calendar/calendar-page'

const calendar = {
  id: 'calendar-1',
  name: 'Delivery',
  color: '#2563eb',
  type: 'organization',
  timezone: 'UTC',
  is_default: true,
}

function renderCalendar(view: 'agenda' | 'resources' = 'agenda') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <CalendarPage view={view} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  calendarMocks.calendars.mockResolvedValue([calendar])
  calendarMocks.events.mockResolvedValue([
    {
      id: 'event-1',
      calendar_id: calendar.id,
      title: 'Customer planning',
      description: null,
      start_datetime: '2026-08-03T14:00:00Z',
      end_datetime: '2026-08-03T15:00:00Z',
      timezone: 'UTC',
      status: 'confirmed',
      all_day: false,
      recurrence_rule_id: null,
      recurrence_parent_id: null,
      original_start_datetime: null,
      category_id: null,
    },
  ])
  calendarMocks.resources.mockResolvedValue([])
  calendarMocks.holidays.mockResolvedValue([])
  calendarMocks.categories.mockResolvedValue([])
  calendarMocks.availability.mockResolvedValue([])
  calendarMocks.shares.mockResolvedValue([])
  calendarMocks.createEvent.mockResolvedValue({
    id: 'event-created',
    calendar_id: calendar.id,
  })
})

test('calendar overlays hide and restore persisted calendar events', async () => {
  renderCalendar()
  expect(await screen.findByText('Customer planning')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Delivery' }))
  await waitFor(() =>
    expect(screen.queryByText('Customer planning')).not.toBeInTheDocument(),
  )
  expect(screen.getByText('Your schedule is clear')).toBeInTheDocument()
})

test('event editor submits recurrence as part of the persisted event', async () => {
  renderCalendar()
  fireEvent.click(await screen.findByRole('button', { name: 'New event' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), {
    target: { value: 'Weekly delivery review' },
  })
  fireEvent.change(screen.getByRole('combobox', { name: 'Repeat' }), {
    target: { value: 'weekly' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Create event' }))
  await waitFor(() => expect(calendarMocks.createEvent).toHaveBeenCalledOnce())
  expect(calendarMocks.createEvent.mock.calls.at(0)![1]).toMatchObject({
    title: 'Weekly delivery review',
    recurrence: { frequency: 'weekly', interval: 1 },
  })
})

test('resource management creates a real room in the active workspace', async () => {
  calendarMocks.createResource.mockResolvedValue({
    id: 'room-1',
    name: 'Executive room',
  })
  renderCalendar('resources')
  fireEvent.change(
    await screen.findByRole('textbox', { name: 'Resource name' }),
    {
      target: { value: 'Executive room' },
    },
  )
  fireEvent.click(screen.getByRole('button', { name: 'Add resource' }))
  await waitFor(() =>
    expect(calendarMocks.createResource).toHaveBeenCalledWith(
      expect.objectContaining({
        workspace_id: 'workspace-1',
        name: 'Executive room',
        category: 'room',
      }),
    ),
  )
})
