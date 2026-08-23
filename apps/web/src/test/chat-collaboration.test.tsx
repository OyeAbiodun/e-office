import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const chatMocks = vi.hoisted(() => ({
  get: vi.fn(),
  messages: vi.fn(),
  pins: vi.fn(),
  tabs: vi.fn(),
  draft: vi.fn(),
  saveDraft: vi.fn(),
  send: vi.fn(),
  socket: vi.fn(),
  read: vi.fn(),
  react: vi.fn(),
  edit: vi.fn(),
  remove: vi.fn(),
  pin: vi.fn(),
  saveMessage: vi.fn(),
}))

vi.mock('@/features/chat/api', () => ({ chatApi: chatMocks }))
vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({ conversationId: 'channel-1' }),
  Link: ({
    children,
    to,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}))

import { ConversationPage } from '@/features/chat/conversation-page'

function renderConversation() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <ConversationPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  chatMocks.socket.mockReturnValue(null)
  chatMocks.get.mockResolvedValue({
    id: 'channel-1',
    organization_id: 'organization-1',
    workspace_id: 'workspace-1',
    team_id: 'team-1',
    type: 'public_team',
    name: 'Product launch',
    description: null,
    visibility: 'members',
    channel_kind: 'shared',
    created_by: 'user-1',
    created_at: '2026-08-02T20:00:00Z',
    updated_at: '2026-08-02T20:00:00Z',
    archived_at: null,
    unread_count: 0,
    member_count: 1,
    last_message: null,
  })
  chatMocks.messages.mockResolvedValue({
    items: [],
    next_cursor: null,
    has_more: false,
  })
  chatMocks.pins.mockResolvedValue([])
  chatMocks.tabs.mockResolvedValue(
    ['Posts', 'Files', 'Meetings', 'Wiki', 'Notes', 'Calendar', 'Apps'].map(
      (name, index) => ({
        id: `tab-${index}`,
        conversation_id: 'channel-1',
        name,
        tab_type: name.toLowerCase(),
        configuration: '{}',
        sort_order: index,
      }),
    ),
  )
  chatMocks.draft.mockResolvedValue({
    id: 'draft-1',
    body: 'Persisted launch update',
    updated_at: '2026-08-02T20:00:00Z',
  })
  chatMocks.saveDraft.mockResolvedValue({})
  chatMocks.send.mockResolvedValue({ id: 'message-1' })
})

test('team channel renders its collaboration tabs and restores its draft', async () => {
  renderConversation()
  expect(
    await screen.findByRole('navigation', { name: 'Channel tabs' }),
  ).toHaveTextContent('PostsFilesMeetingsWikiNotesCalendarApps')
  expect(screen.getByRole('textbox', { name: 'Message composer' })).toHaveValue(
    'Persisted launch update',
  )
})

test('editing autosaves a durable draft and sending clears the composer', async () => {
  renderConversation()
  const composer = await screen.findByRole('textbox', {
    name: 'Message composer',
  })
  await waitFor(() => expect(composer).toHaveValue('Persisted launch update'))
  fireEvent.change(composer, { target: { value: 'Ready for review' } })
  await waitFor(
    () =>
      expect(chatMocks.saveDraft).toHaveBeenCalledWith(
        'channel-1',
        'Ready for review',
      ),
    { timeout: 1200 },
  )
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  await waitFor(() => expect(chatMocks.send).toHaveBeenCalledOnce())
  expect(composer).toHaveValue('')
})
