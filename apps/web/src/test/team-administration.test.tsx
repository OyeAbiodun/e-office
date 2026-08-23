import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { TeamDetailPage } from '@/features/teams/team-detail-page'
import { TeamsPage } from '@/features/teams/teams-page'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  overview: vi.fn(),
  members: vi.fn(),
  channels: vi.fn(),
  integrations: vi.fn(),
  documents: vi.fn(),
  createChannel: vi.fn(),
  channelPreference: vi.fn(),
  channelLifecycle: vi.fn(),
  createDocument: vi.fn(),
  updateIntegration: vi.fn(),
  update: vi.fn(),
  archive: vi.fn(),
  restore: vi.fn(),
  bulkMembers: vi.fn(),
}))
const organizationApi = vi.hoisted(() => ({
  workspaces: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useParams: () => ({ teamId: 'team-1' }),
}))
vi.mock('@/features/teams/api', () => ({ teamsApi: api }))
vi.mock('@/features/organizations/api', () => ({ organizationApi }))

const team = {
  id: 'team-1',
  organization_id: 'org-1',
  workspace_id: 'workspace-1',
  name: 'Product Launch',
  slug: 'product-launch',
  description: 'Cross-functional launch collaboration',
  avatar_url: null,
  banner_url: null,
  color: '#2563eb',
  icon: null,
  classification: 'confidential',
  owner_id: 'user-1',
  settings: {},
  visibility: 'private',
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
  api.list.mockResolvedValue([team])
  organizationApi.workspaces.mockResolvedValue([
    { id: 'workspace-1', name: 'Main Workspace', archived_at: null },
  ])
  api.overview.mockResolvedValue({
    team,
    owner_count: 1,
    administrator_count: 0,
    member_count: 4,
    guest_count: 0,
    channel_count: 2,
    meeting_count: 3,
    upcoming_meeting_count: 1,
    calendar_count: 1,
    file_count: 5,
    storage_bytes: 1024,
    wiki_count: 1,
    note_count: 2,
    app_count: 1,
    active_member_count: 3,
    open_action_count: 2,
    announcement_count: 1,
    health_score: 90,
    recent_activity: [],
    recent_conversations: [],
    upcoming_meetings: [],
  })
  api.members.mockResolvedValue([
    {
      id: 'member-1',
      user_id: 'user-1',
      email: 'textabi12@gmail.com',
      display_name: 'Abiodun',
      role: 'owner',
      joined_at: '2026-08-01T00:00:00Z',
    },
  ])
  api.channels.mockResolvedValue([])
  api.integrations.mockResolvedValue([])
  api.documents.mockResolvedValue([])
  api.createChannel.mockResolvedValue({})
  api.createDocument.mockResolvedValue({})
  api.update.mockResolvedValue(team)
})

test('searches Teams and creates governed collaboration spaces', async () => {
  renderWithClient(<TeamsPage />)
  expect(await screen.findByText('Product Launch')).toBeVisible()
  fireEvent.change(screen.getByLabelText('Search teams'), {
    target: { value: 'product' },
  })
  await waitFor(() =>
    expect(api.list).toHaveBeenLastCalledWith({
      search: 'product',
      archived: false,
    }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'New team' }))
  fireEvent.change(screen.getByLabelText('Team name'), {
    target: { value: 'Operations' },
  })
  fireEvent.change(screen.getByLabelText('Slug'), {
    target: { value: 'operations' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Create team' }))
  await waitFor(() =>
    expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Operations',
        slug: 'operations',
        workspace_id: 'workspace-1',
      }),
    ),
  )
})

test('navigates live Team surfaces and persists channel, wiki, and settings changes', async () => {
  renderWithClient(<TeamDetailPage />)
  expect(
    await screen.findByRole('heading', { name: 'Product Launch' }),
  ).toBeVisible()
  expect(screen.getByText('90%')).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: 'Channels' }))
  fireEvent.click(screen.getByRole('button', { name: 'New channel' }))
  fireEvent.change(screen.getByLabelText('Channel name'), {
    target: { value: 'Announcements' },
  })
  fireEvent.change(screen.getByLabelText('Type'), {
    target: { value: 'announcement' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Create channel' }))
  await waitFor(() =>
    expect(api.createChannel).toHaveBeenCalledWith(
      'team-1',
      expect.objectContaining({
        name: 'Announcements',
        channel_kind: 'announcement',
      }),
    ),
  )

  fireEvent.click(screen.getByRole('button', { name: 'Wiki' }))
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Launch plan' },
  })
  fireEvent.change(screen.getByLabelText('Content'), {
    target: { value: 'Validated launch knowledge.' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Add wiki' }))
  expect(api.createDocument).toHaveBeenCalledWith('team-1', {
    document_type: 'wiki',
    title: 'Launch plan',
    content: 'Validated launch knowledge.',
  })

  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  fireEvent.change(screen.getByLabelText('Classification'), {
    target: { value: 'restricted' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await waitFor(() =>
    expect(api.update).toHaveBeenCalledWith(
      'team-1',
      expect.objectContaining({ classification: 'restricted' }),
    ),
  )
})

test('reveals archived channels and restores them from channel management', async () => {
  api.channels.mockResolvedValue([
    {
      id: 'channel-1',
      organization_id: 'org-1',
      workspace_id: 'workspace-1',
      team_id: 'team-1',
      name: 'Release history',
      description: null,
      channel_kind: 'announcement',
      visibility: 'members',
      read_only: false,
      moderation_enabled: true,
      settings: {},
      archived_at: '2026-08-03T00:00:00Z',
      favorite: false,
      pinned: false,
      message_count: 8,
      member_count: 4,
      created_at: '2026-08-01T00:00:00Z',
      updated_at: '2026-08-03T00:00:00Z',
    },
  ])

  renderWithClient(<TeamDetailPage />)
  await screen.findByRole('heading', { name: 'Product Launch' })
  fireEvent.click(screen.getByRole('button', { name: 'Channels' }))
  expect(screen.queryByText('Release history')).not.toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Filter channel lifecycle'), {
    target: { value: 'archived' },
  })
  expect(screen.getByText('Release history')).toBeVisible()
  fireEvent.click(screen.getByLabelText('Channel actions for Release history'))
  fireEvent.click(screen.getByRole('button', { name: 'Restore channel' }))

  await waitFor(() =>
    expect(api.channelLifecycle).toHaveBeenCalledWith(
      'team-1',
      'channel-1',
      'restore',
    ),
  )
})
