import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { MailPage } from '@/features/mail/mail-page'

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  messages: vi.fn(),
  message: vi.fn(),
  folders: vi.fn(),
  status: vi.fn(),
  templates: vi.fn(),
  signatures: vi.fn(),
  createDraft: vi.fn(),
  send: vi.fn(),
  read: vi.fn(),
  star: vi.fn(),
  move: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mocks.navigate,
  useParams: () => ({}),
}))

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({ user: { email: 'admin@meetinghq.example' } }),
}))

vi.mock('@/features/mail/api', () => ({
  mailApi: {
    messages: mocks.messages,
    message: mocks.message,
    folders: mocks.folders,
    status: mocks.status,
    templates: mocks.templates,
    signatures: mocks.signatures,
    createDraft: mocks.createDraft,
    updateDraft: vi.fn(),
    send: mocks.send,
    uploadAttachment: vi.fn(),
    read: mocks.read,
    star: mocks.star,
    move: mocks.move,
    label: vi.fn(),
    createFolder: vi.fn(),
    createTemplate: vi.fn(),
    createSignature: vi.fn(),
  },
}))

const message = {
  id: 'message-1',
  thread_id: 'thread-1',
  folder: 'inbox',
  status: 'delivered',
  from_email: 'avery@example.test',
  from_name: 'Avery Recipient',
  to_recipients: [{ email: 'admin@meetinghq.example' }],
  cc_recipients: [],
  bcc_recipients: [],
  subject: 'Quarterly planning',
  body_html: '<p>Please review the plan.</p>',
  body_text: 'Please review the plan.',
  preview: 'Please review the plan.',
  labels: ['Planning'],
  is_read: false,
  is_starred: false,
  read_receipt_requested: true,
  delivery_status: 'delivered',
  delivery_error: null,
  sent_at: '2026-08-03T12:00:00Z',
  read_at: null,
  created_at: '2026-08-03T12:00:00Z',
  updated_at: '2026-08-03T12:00:00Z',
  attachments: [],
}

function renderMail() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MailPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/mail')
  mocks.folders.mockResolvedValue([
    {
      id: null,
      name: 'inbox',
      color: '#64748b',
      system: true,
      count: 1,
      unread: 1,
    },
    {
      id: null,
      name: 'drafts',
      color: '#64748b',
      system: true,
      count: 0,
      unread: 0,
    },
    {
      id: null,
      name: 'sent',
      color: '#64748b',
      system: true,
      count: 0,
      unread: 0,
    },
    {
      id: null,
      name: 'trash',
      color: '#64748b',
      system: true,
      count: 0,
      unread: 0,
    },
  ])
  mocks.messages.mockResolvedValue({
    items: [message],
    total: 1,
    page: 1,
    page_size: 25,
    total_pages: 1,
    unread: 1,
  })
  mocks.message.mockResolvedValue(message)
  mocks.status.mockResolvedValue({
    internal_delivery: true,
    external_delivery: false,
    provider: null,
    configuration_url: '/integrations',
  })
  mocks.templates.mockResolvedValue([])
  mocks.signatures.mockResolvedValue([])
  mocks.star.mockResolvedValue({ ...message, is_starred: true })
  mocks.move.mockResolvedValue({ ...message, folder: 'trash' })
  mocks.createDraft.mockResolvedValue({
    ...message,
    id: 'draft-1',
    folder: 'drafts',
  })
  mocks.send.mockResolvedValue({
    ...message,
    id: 'draft-1',
    folder: 'sent',
  })
})

test('renders a responsive mailbox with provider status and persisted message data', async () => {
  renderMail()
  expect(await screen.findByRole('heading', { name: 'Mail' })).toBeVisible()
  expect(await screen.findByText('Quarterly planning')).toBeVisible()
  expect(screen.getByText(/Configure SMTP in Integration Center/)).toBeVisible()
  expect(await screen.findByText('Please review the plan.')).toBeVisible()
  fireEvent.click(screen.getByRole('listitem'))
  fireEvent.click(await screen.findByRole('button', { name: 'Star message' }))
  await waitFor(() =>
    expect(mocks.star).toHaveBeenCalledWith('message-1', true),
  )
})

test('composes and sends organization mail through persisted draft workflow', async () => {
  renderMail()
  fireEvent.click(await screen.findByRole('button', { name: 'Compose' }))
  fireEvent.change(screen.getByLabelText('To recipients'), {
    target: { value: 'avery@example.test' },
  })
  fireEvent.change(screen.getByLabelText('Subject'), {
    target: { value: 'Planning follow-up' },
  })
  fireEvent.input(screen.getByRole('textbox', { name: 'Message body' }), {
    target: {
      innerHTML: '<p>Ready for review.</p>',
      innerText: 'Ready for review.',
    },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(mocks.createDraft).toHaveBeenCalled())
  await waitFor(() => expect(mocks.send).toHaveBeenCalledWith('draft-1'))
})
