import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import {
  Archive,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  File,
  FileText,
  Inbox,
  Mail,
  MailOpen,
  Menu,
  MoreHorizontal,
  Paperclip,
  PenLine,
  Plus,
  Search,
  Send,
  Settings2,
  Star,
  Trash2,
  X,
} from 'lucide-react'
import {
  type ChangeEvent,
  type Dispatch,
  type FormEvent,
  type ReactNode,
  type RefObject,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import { notify } from '@/components/feedback/events'
import { useAuth } from '@/features/auth/auth-store'
import {
  mailApi,
  type MailDraft,
  type MailMessage,
  type MailTemplate,
} from '@/features/mail/api'

const systemIcons = {
  inbox: Inbox,
  drafts: FileText,
  sent: Send,
  trash: Trash2,
}

const emptyDraft: MailDraft = {
  to_recipients: [],
  cc_recipients: [],
  bcc_recipients: [],
  subject: '',
  body_html: '',
  body_text: '',
  read_receipt_requested: false,
}

interface MailPageProps {
  messageId?: string
  compose?: boolean
}

export function MailPage({
  messageId: initialMessageId,
  compose: initialCompose,
}: MailPageProps) {
  const navigate = useNavigate()
  const routeParams = useParams({ strict: false }) as { messageId?: string }
  const effectiveMessageId = initialMessageId ?? routeParams.messageId
  const queryClient = useQueryClient()
  const params = useMemo(() => new URLSearchParams(window.location.search), [])
  const [folder, setFolder] = useState(params.get('folder') ?? 'inbox')
  const [search, setSearch] = useState(params.get('search') ?? '')
  const [page, setPage] = useState(Number(params.get('page') ?? 1))
  const [pageSize, setPageSize] = useState(Number(params.get('pageSize') ?? 25))
  const [selectedId, setSelectedId] = useState<string | null>(
    effectiveMessageId ?? null,
  )
  const [composeOpen, setComposeOpen] = useState(Boolean(initialCompose))
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [mobileFolders, setMobileFolders] = useState(false)

  useEffect(() => {
    const next = new URLSearchParams()
    if (folder !== 'inbox') next.set('folder', folder)
    if (search) next.set('search', search)
    if (page > 1) next.set('page', String(page))
    if (pageSize !== 25) next.set('pageSize', String(pageSize))
    window.history.replaceState(
      null,
      '',
      `${window.location.pathname}${next.size ? `?${next}` : ''}`,
    )
  }, [folder, page, pageSize, search])

  const folders = useQuery({
    queryKey: ['mail-folders'],
    queryFn: mailApi.folders,
  })
  const messages = useQuery({
    queryKey: ['mail-messages', folder, search, page, pageSize],
    queryFn: () => mailApi.messages({ folder, search, page, pageSize }),
  })
  const selected = useQuery({
    queryKey: ['mail-message', selectedId],
    queryFn: () => mailApi.message(selectedId!),
    enabled: Boolean(selectedId),
  })
  const provider = useQuery({
    queryKey: ['mail-provider-status'],
    queryFn: mailApi.status,
  })

  useEffect(() => {
    if (!selectedId && messages.data?.items[0])
      setSelectedId(messages.data.items[0].id)
  }, [messages.data, selectedId])

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['mail-messages'] }),
      queryClient.invalidateQueries({ queryKey: ['mail-folders'] }),
      queryClient.invalidateQueries({ queryKey: ['mail-message'] }),
    ])
  }
  const mutateMessage = useMutation({
    mutationFn: ({
      id,
      action,
      value,
    }: {
      id: string
      action: 'star' | 'trash' | 'archive'
      value?: boolean
    }) =>
      action === 'star'
        ? mailApi.star(id, Boolean(value))
        : mailApi.move(id, action === 'trash' ? 'trash' : 'inbox'),
    onSuccess: invalidate,
  })

  const openMessage = (id: string) => {
    setSelectedId(id)
    void navigate({ to: '/mail/$messageId', params: { messageId: id } })
  }

  return (
    <section className="flex h-[calc(100vh-4rem)] min-h-[620px] flex-col overflow-hidden">
      <header className="flex flex-wrap items-center gap-3 border-b bg-card px-4 py-3 sm:px-6">
        <button
          aria-label="Show mail folders"
          className="rounded-lg border p-2 lg:hidden"
          onClick={() => setMobileFolders(true)}
          type="button"
        >
          <Menu className="size-4" />
        </button>
        <div className="mr-auto">
          <h1 className="text-xl font-semibold tracking-tight">Mail</h1>
          <p className="text-xs text-muted-foreground">
            Conversations, drafts, and organization mail
          </p>
        </div>
        <div className="relative min-w-[220px] flex-1 md:max-w-md">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            aria-label="Search mail"
            className="h-10 w-full rounded-xl border bg-background pl-9 pr-3 text-sm"
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
            placeholder="Search sender, subject, or message"
            value={search}
          />
        </div>
        <button
          className="flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-medium hover:bg-muted"
          onClick={() => setSettingsOpen(true)}
          type="button"
        >
          <Settings2 className="size-4" />
          <span className="hidden sm:inline">Mail settings</span>
        </button>
        <button
          className="flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20"
          onClick={() => setComposeOpen(true)}
          type="button"
        >
          <PenLine className="size-4" />
          Compose
        </button>
      </header>

      {provider.data && !provider.data.external_delivery && (
        <div className="flex items-center gap-3 border-b border-amber-300/60 bg-amber-50 px-5 py-2 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
          <CircleAlert className="size-4 shrink-0" />
          Internal organization mail is ready. Configure SMTP in Integration
          Center to deliver to external recipients.
          <a className="ml-auto font-semibold underline" href="/integrations">
            Configure
          </a>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <FolderPane
          folders={folders.data ?? []}
          mobileOpen={mobileFolders}
          onClose={() => setMobileFolders(false)}
          onCompose={() => setComposeOpen(true)}
          onSelect={(value) => {
            setFolder(value)
            setPage(1)
            setSelectedId(null)
            setMobileFolders(false)
            void navigate({ to: '/mail' })
          }}
          selected={folder}
        />
        <MessageList
          folder={folder}
          isError={messages.isError}
          isLoading={messages.isLoading}
          messages={messages.data?.items ?? []}
          onOpen={openMessage}
          onStar={(item) =>
            mutateMessage.mutate({
              id: item.id,
              action: 'star',
              value: !item.is_starred,
            })
          }
          page={page}
          pageSize={pageSize}
          selectedId={selectedId}
          setPage={setPage}
          setPageSize={setPageSize}
          total={messages.data?.total ?? 0}
          totalPages={messages.data?.total_pages ?? 1}
        />
        <ReadingPane
          isLoading={selected.isLoading}
          message={selected.data}
          onArchive={() =>
            selected.data &&
            mutateMessage.mutate({ id: selected.data.id, action: 'archive' })
          }
          onClose={() => {
            setSelectedId(null)
            void navigate({ to: '/mail' })
          }}
          onReply={() => setComposeOpen(true)}
          onStar={() =>
            selected.data &&
            mutateMessage.mutate({
              id: selected.data.id,
              action: 'star',
              value: !selected.data.is_starred,
            })
          }
          onTrash={() =>
            selected.data &&
            mutateMessage.mutate({ id: selected.data.id, action: 'trash' })
          }
        />
      </div>

      {composeOpen && (
        <Composer
          initial={
            selected.data
              ? {
                  ...emptyDraft,
                  to_recipients: [
                    {
                      email: selected.data.from_email,
                      name: selected.data.from_name,
                    },
                  ],
                  subject: selected.data.subject.startsWith('Re:')
                    ? selected.data.subject
                    : `Re: ${selected.data.subject}`,
                  reply_to_id: selected.data.id,
                }
              : emptyDraft
          }
          onClose={() => {
            setComposeOpen(false)
            if (initialCompose) void navigate({ to: '/mail' })
          }}
          onComplete={async () => {
            setComposeOpen(false)
            await invalidate()
            void navigate({ to: '/mail' })
          }}
        />
      )}
      {settingsOpen && <MailSettings onClose={() => setSettingsOpen(false)} />}
    </section>
  )
}

function FolderPane({
  folders,
  selected,
  mobileOpen,
  onSelect,
  onCompose,
  onClose,
}: {
  folders: Array<{
    id: string | null
    name: string
    count: number
    unread: number
    system: boolean
    color: string
  }>
  selected: string
  mobileOpen: boolean
  onSelect: (value: string) => void
  onCompose: () => void
  onClose: () => void
}) {
  return (
    <>
      {mobileOpen && (
        <button
          aria-label="Close mail folders"
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={onClose}
          type="button"
        />
      )}
      <aside
        className={`${mobileOpen ? 'translate-x-0' : '-translate-x-full'} fixed inset-y-0 left-0 z-50 w-64 border-r bg-card p-3 transition lg:static lg:z-auto lg:w-56 lg:translate-x-0`}
      >
        <button
          className="mb-4 flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary font-semibold text-primary-foreground lg:hidden"
          onClick={onCompose}
          type="button"
        >
          <Plus className="size-4" /> New message
        </button>
        <nav aria-label="Mailbox folders" className="space-y-1">
          {folders.map((item) => {
            const Icon =
              systemIcons[item.name as keyof typeof systemIcons] ?? Archive
            return (
              <button
                className={`flex h-10 w-full items-center gap-3 rounded-xl px-3 text-sm ${
                  selected === item.name
                    ? 'bg-primary/10 font-semibold text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
                key={item.id ?? item.name}
                onClick={() => onSelect(item.name)}
                type="button"
              >
                <Icon className="size-4" style={{ color: item.color }} />
                <span className="truncate capitalize">{item.name}</span>
                <span className="ml-auto text-xs">
                  {item.unread ? (
                    <span className="rounded-full bg-primary px-2 py-0.5 text-primary-foreground">
                      {item.unread > 99 ? '99+' : item.unread}
                    </span>
                  ) : (
                    item.count || ''
                  )}
                </span>
              </button>
            )
          })}
        </nav>
        <div className="mt-6 rounded-xl border bg-muted/40 p-3">
          <p className="text-xs font-semibold">Mailbox storage</p>
          <div className="my-2 h-1.5 overflow-hidden rounded-full bg-border">
            <div className="h-full w-[8%] rounded-full bg-primary" />
          </div>
          <p className="text-[11px] text-muted-foreground">
            Usage is calculated from stored attachments.
          </p>
        </div>
      </aside>
    </>
  )
}

function MessageList({
  folder,
  messages,
  selectedId,
  isLoading,
  isError,
  onOpen,
  onStar,
  page,
  pageSize,
  total,
  totalPages,
  setPage,
  setPageSize,
}: {
  folder: string
  messages: MailMessage[]
  selectedId: string | null
  isLoading: boolean
  isError: boolean
  onOpen: (id: string) => void
  onStar: (message: MailMessage) => void
  page: number
  pageSize: number
  total: number
  totalPages: number
  setPage: (value: number) => void
  setPageSize: (value: number) => void
}) {
  return (
    <section className="flex w-full min-w-0 flex-col border-r bg-card md:w-[340px] xl:w-[420px]">
      <div className="flex h-12 items-center gap-2 border-b px-4">
        <h2 className="mr-auto text-sm font-semibold capitalize">{folder}</h2>
        <span className="text-xs text-muted-foreground">{total} messages</span>
        <button
          aria-label="More mailbox actions"
          className="rounded-lg p-2 hover:bg-muted"
        >
          <MoreHorizontal className="size-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto" role="list">
        {isLoading &&
          Array.from({ length: 7 }, (_, index) => (
            <div className="animate-pulse border-b p-4" key={index}>
              <div className="mb-2 h-3 w-2/5 rounded bg-muted" />
              <div className="mb-2 h-3 w-4/5 rounded bg-muted" />
              <div className="h-3 w-full rounded bg-muted" />
            </div>
          ))}
        {isError && (
          <EmptyState
            icon={CircleAlert}
            title="Mail could not be loaded"
            description="Check your connection and try again."
          />
        )}
        {!isLoading && !isError && messages.length === 0 && (
          <EmptyState
            icon={MailOpen}
            title={`No messages in ${folder}`}
            description={
              folder === 'inbox'
                ? 'New organization mail will appear here.'
                : 'This folder is currently empty.'
            }
          />
        )}
        {messages.map((message) => (
          <article
            className={`group flex cursor-pointer gap-2 border-b px-3 py-3 transition hover:bg-muted/60 ${
              selectedId === message.id ? 'bg-primary/8' : ''
            } ${message.is_read ? '' : 'bg-primary/[0.035]'}`}
            key={message.id}
            onClick={() => onOpen(message.id)}
            role="listitem"
          >
            <button
              aria-label={
                message.is_starred ? 'Remove from starred' : 'Add to starred'
              }
              className="self-start rounded p-1 text-muted-foreground hover:text-amber-500"
              onClick={(event) => {
                event.stopPropagation()
                onStar(message)
              }}
              type="button"
            >
              <Star
                className={`size-4 ${message.is_starred ? 'fill-amber-400 text-amber-500' : ''}`}
              />
            </button>
            <div className="min-w-0 flex-1">
              <div className="flex gap-2">
                <p
                  className={`truncate text-sm ${message.is_read ? 'font-medium' : 'font-bold'}`}
                >
                  {folder === 'sent'
                    ? message.to_recipients[0]?.name ||
                      message.to_recipients[0]?.email ||
                      'Recipients'
                    : message.from_name}
                </p>
                <time className="ml-auto shrink-0 text-[11px] text-muted-foreground">
                  {formatDate(message.sent_at ?? message.updated_at)}
                </time>
              </div>
              <p
                className={`truncate text-sm ${message.is_read ? '' : 'font-semibold'}`}
              >
                {message.subject || '(No subject)'}
              </p>
              <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-muted-foreground">
                {message.preview || 'No message content'}
              </p>
              <div className="mt-2 flex items-center gap-1.5">
                {message.attachments.length > 0 && (
                  <Paperclip className="size-3 text-muted-foreground" />
                )}
                {message.labels.map((label) => (
                  <span
                    className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
                    key={label}
                  >
                    {label}
                  </span>
                ))}
                {message.delivery_status === 'failed' && (
                  <span className="text-[10px] font-semibold text-red-600">
                    Delivery failed
                  </span>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
      <Pagination
        page={page}
        pageSize={pageSize}
        setPage={setPage}
        setPageSize={setPageSize}
        total={total}
        totalPages={totalPages}
      />
    </section>
  )
}

function ReadingPane({
  message,
  isLoading,
  onClose,
  onReply,
  onStar,
  onArchive,
  onTrash,
}: {
  message?: MailMessage
  isLoading: boolean
  onClose: () => void
  onReply: () => void
  onStar: () => void
  onArchive: () => void
  onTrash: () => void
}) {
  if (isLoading)
    return (
      <div className="hidden flex-1 animate-pulse p-8 md:block">
        <div className="mb-5 h-7 w-2/3 rounded bg-muted" />
        <div className="mb-8 h-12 w-full rounded bg-muted" />
        <div className="space-y-3">
          <div className="h-3 rounded bg-muted" />
          <div className="h-3 rounded bg-muted" />
          <div className="h-3 w-3/4 rounded bg-muted" />
        </div>
      </div>
    )
  if (!message)
    return (
      <div className="hidden flex-1 place-items-center bg-background/40 md:grid">
        <EmptyState
          icon={Mail}
          title="Select a message"
          description="Choose a conversation to read it here."
        />
      </div>
    )
  return (
    <article className="fixed inset-0 z-30 flex min-w-0 flex-1 flex-col bg-background md:static md:z-auto">
      <div className="flex h-12 items-center gap-1 border-b bg-card px-3">
        <button
          aria-label="Back to message list"
          className="rounded-lg p-2 hover:bg-muted md:hidden"
          onClick={onClose}
          type="button"
        >
          <ChevronLeft className="size-4" />
        </button>
        <button
          aria-label="Archive message"
          className="rounded-lg p-2 hover:bg-muted"
          onClick={onArchive}
        >
          <Archive className="size-4" />
        </button>
        <button
          aria-label="Delete message"
          className="rounded-lg p-2 hover:bg-muted"
          onClick={onTrash}
        >
          <Trash2 className="size-4" />
        </button>
        <button
          aria-label="Star message"
          className="rounded-lg p-2 hover:bg-muted"
          onClick={onStar}
        >
          <Star
            className={`size-4 ${message.is_starred ? 'fill-amber-400 text-amber-500' : ''}`}
          />
        </button>
        <span className="mx-2 h-5 border-l" />
        <button
          className="rounded-lg px-3 py-1.5 text-xs font-semibold hover:bg-muted"
          onClick={onReply}
          type="button"
        >
          Reply
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-5 lg:p-8">
        <div className="mx-auto max-w-4xl">
          <h2 className="text-2xl font-semibold tracking-tight">
            {message.subject || '(No subject)'}
          </h2>
          <div className="mt-6 flex items-start gap-3 border-b pb-5">
            <div className="grid size-10 shrink-0 place-items-center rounded-full bg-primary/10 text-sm font-bold text-primary">
              {initials(message.from_name)}
            </div>
            <div className="min-w-0">
              <p className="font-semibold">{message.from_name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {message.from_email} · to{' '}
                {message.to_recipients.map((item) => item.email).join(', ')}
              </p>
            </div>
            <time className="ml-auto text-xs text-muted-foreground">
              {new Date(message.sent_at ?? message.created_at).toLocaleString()}
            </time>
          </div>
          {message.delivery_error && (
            <div className="mt-5 flex gap-3 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:bg-red-950/30 dark:text-red-100">
              <CircleAlert className="size-5 shrink-0" />
              {message.delivery_error}
            </div>
          )}
          <div
            className="prose prose-slate mt-7 max-w-none text-sm leading-7 dark:prose-invert"
            dangerouslySetInnerHTML={{
              __html:
                message.body_html ||
                `<p>${escapeHtml(message.body_text).replaceAll('\n', '<br>')}</p>`,
            }}
          />
          {message.attachments.length > 0 && (
            <div className="mt-8 border-t pt-5">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {message.attachments.length} attachment
                {message.attachments.length === 1 ? '' : 's'}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {message.attachments.map((attachment) => (
                  <a
                    className="flex items-center gap-3 rounded-xl border bg-card p-3 hover:border-primary/50"
                    href={attachment.url}
                    key={attachment.id}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <File className="size-5 text-primary" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {attachment.filename}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatBytes(attachment.size)}
                      </span>
                    </span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </article>
  )
}

function Composer({
  initial,
  onClose,
  onComplete,
}: {
  initial: MailDraft
  onClose: () => void
  onComplete: () => Promise<void>
}) {
  const { user } = useAuth()
  const [draft, setDraft] = useState(initial)
  const [to, setTo] = useState(
    initial.to_recipients.map((item) => item.email).join(', '),
  )
  const [showCopies, setShowCopies] = useState(false)
  const [cc, setCc] = useState('')
  const [bcc, setBcc] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [saving, setSaving] = useState(false)
  const [draftId, setDraftId] = useState<string | null>(null)
  const editor = useRef<HTMLDivElement>(null)
  const templates = useQuery({
    queryKey: ['mail-templates'],
    queryFn: mailApi.templates,
  })
  const signatures = useQuery({
    queryKey: ['mail-signatures'],
    queryFn: mailApi.signatures,
  })

  const payload = (): MailDraft => ({
    ...draft,
    to_recipients: recipients(to),
    cc_recipients: recipients(cc),
    bcc_recipients: recipients(bcc),
    body_html: editor.current?.innerHTML ?? draft.body_html,
    body_text: editor.current?.innerText ?? draft.body_text,
  })
  const save = async () => {
    setSaving(true)
    try {
      const message = draftId
        ? await mailApi.updateDraft(draftId, payload())
        : await mailApi.createDraft(payload())
      setDraftId(message.id)
      return message.id
    } finally {
      setSaving(false)
    }
  }
  const send = async (event: FormEvent) => {
    event.preventDefault()
    if (!recipients(to).length) {
      notify({
        tone: 'warning',
        title: 'Add a recipient',
        description: 'Enter at least one email address before sending.',
      })
      return
    }
    setSaving(true)
    try {
      const id = await save()
      for (const file of files) await mailApi.uploadAttachment(id, file)
      const result = await mailApi.send(id)
      if (result.delivery_status === 'failed')
        notify({
          tone: 'error',
          title: 'External delivery failed',
          description:
            result.delivery_error ?? 'Review Integration Center configuration.',
        })
      else
        notify({
          tone: 'success',
          title: 'Message sent',
          description: `Your message to ${recipients(to).length} recipient(s) was delivered.`,
        })
      await onComplete()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-end bg-black/30 p-0 backdrop-blur-sm sm:p-5">
      <form
        aria-label="Compose message"
        className="flex h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl border bg-card shadow-2xl sm:h-[720px] sm:max-h-[calc(100vh-2.5rem)] sm:max-w-3xl sm:rounded-2xl"
        onSubmit={send}
      >
        <div className="flex items-center gap-3 bg-primary px-4 py-3 text-primary-foreground">
          <PenLine className="size-4" />
          <h2 className="font-semibold">New message</h2>
          <span className="ml-auto text-xs opacity-80">
            {saving ? 'Saving…' : draftId ? 'Draft saved' : ''}
          </span>
          <button
            aria-label="Close composer"
            className="rounded p-1 hover:bg-white/15"
            onClick={onClose}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="border-b px-4">
          <ComposerAddress label="To" onChange={setTo} value={to}>
            <button
              className="text-xs font-semibold text-primary"
              onClick={() => setShowCopies((value) => !value)}
              type="button"
            >
              Cc/Bcc
            </button>
          </ComposerAddress>
          {showCopies && (
            <>
              <ComposerAddress label="Cc" onChange={setCc} value={cc} />
              <ComposerAddress label="Bcc" onChange={setBcc} value={bcc} />
            </>
          )}
          <input
            aria-label="Subject"
            className="h-11 w-full border-t bg-transparent text-sm outline-none"
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                subject: event.target.value,
              }))
            }
            placeholder="Subject"
            value={draft.subject}
          />
        </div>
        <div className="flex flex-wrap items-center gap-1 border-b px-3 py-2">
          {(
            [
              ['Bold', 'bold'],
              ['Italic', 'italic'],
              ['Bulleted list', 'insertUnorderedList'],
              ['Numbered list', 'insertOrderedList'],
            ] as const
          ).map(([label, command]) => (
            <button
              aria-label={label}
              className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold hover:bg-muted"
              key={command}
              onClick={() => document.execCommand(command)}
              type="button"
            >
              {label === 'Bold'
                ? 'B'
                : label === 'Italic'
                  ? 'I'
                  : label.startsWith('Bulleted')
                    ? '• List'
                    : '1. List'}
            </button>
          ))}
          <select
            aria-label="Insert template"
            className="ml-auto rounded-lg border bg-background px-2 py-1.5 text-xs"
            onChange={(event) => {
              const item = templates.data?.find(
                (value) => value.id === event.target.value,
              )
              if (item) applyTemplate(item, setDraft, editor)
            }}
            value=""
          >
            <option value="">Templates</option>
            {templates.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Insert signature"
            className="rounded-lg border bg-background px-2 py-1.5 text-xs"
            onChange={(event) => {
              const item = signatures.data?.find(
                (value) => value.id === event.target.value,
              )
              if (item && editor.current)
                editor.current.innerHTML += `<br>${item.body_html}`
            }}
            value=""
          >
            <option value="">Signatures</option>
            {signatures.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div
          aria-label="Message body"
          className="min-h-0 flex-1 overflow-y-auto p-5 text-sm leading-7 outline-none"
          contentEditable
          dangerouslySetInnerHTML={{ __html: draft.body_html }}
          ref={editor}
          role="textbox"
          suppressContentEditableWarning
        />
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 border-t px-4 py-2">
            {files.map((file) => (
              <span
                className="flex items-center gap-2 rounded-lg bg-muted px-2 py-1 text-xs"
                key={`${file.name}-${file.size}`}
              >
                <Paperclip className="size-3" />
                {file.name}
                <button
                  aria-label={`Remove ${file.name}`}
                  onClick={() =>
                    setFiles((current) =>
                      current.filter((item) => item !== file),
                    )
                  }
                  type="button"
                >
                  <X className="size-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 border-t px-4 py-3">
          <button
            className="flex h-10 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-60"
            disabled={saving}
            type="submit"
          >
            <Send className="size-4" />
            {saving ? 'Sending…' : 'Send'}
          </button>
          <label className="flex h-10 cursor-pointer items-center gap-2 rounded-xl border px-3 text-sm font-medium hover:bg-muted">
            <Paperclip className="size-4" />
            Attach
            <input
              className="sr-only"
              multiple
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setFiles(Array.from(event.target.files ?? []))
              }
              type="file"
            />
          </label>
          <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
            <input
              checked={draft.read_receipt_requested}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  read_receipt_requested: event.target.checked,
                }))
              }
              type="checkbox"
            />
            Request read receipt
          </label>
          <button
            className="h-10 rounded-xl border px-3 text-sm font-medium hover:bg-muted"
            disabled={saving}
            onClick={() => void save()}
            type="button"
          >
            Save draft
          </button>
        </div>
        <span className="sr-only">Sending as {user?.email}</span>
      </form>
    </div>
  )
}

function MailSettings({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'folders' | 'templates' | 'signatures'>(
    'folders',
  )
  const folders = useQuery({
    queryKey: ['mail-folders'],
    queryFn: mailApi.folders,
  })
  const templates = useQuery({
    queryKey: ['mail-templates'],
    queryFn: mailApi.templates,
  })
  const signatures = useQuery({
    queryKey: ['mail-signatures'],
    queryFn: mailApi.signatures,
  })
  const [name, setName] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const create = useMutation({
    mutationFn: async () => {
      if (tab === 'folders')
        return mailApi.createFolder({ name, color: '#64748b' })
      if (tab === 'templates')
        return mailApi.createTemplate({ name, subject, body_html: body })
      return mailApi.createSignature({
        name,
        body_html: body,
        is_default: false,
      })
    },
    onSuccess: async () => {
      setName('')
      setSubject('')
      setBody('')
      await queryClient.invalidateQueries({ queryKey: [`mail-${tab}`] })
    },
  })
  const items =
    tab === 'folders'
      ? folders.data?.filter((item) => !item.system)
      : tab === 'templates'
        ? templates.data
        : signatures.data
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-sm">
      <aside className="h-full w-full max-w-lg overflow-y-auto border-l bg-card p-6 shadow-2xl">
        <div className="flex items-center">
          <div>
            <h2 className="text-xl font-semibold">Mail settings</h2>
            <p className="text-sm text-muted-foreground">
              Manage your mailbox organization and reusable content.
            </p>
          </div>
          <button
            aria-label="Close mail settings"
            className="ml-auto rounded-lg p-2 hover:bg-muted"
            onClick={onClose}
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="mt-6 flex gap-1 rounded-xl bg-muted p-1">
          {(['folders', 'templates', 'signatures'] as const).map((value) => (
            <button
              className={`flex-1 rounded-lg px-2 py-2 text-xs font-semibold capitalize ${
                tab === value ? 'bg-card shadow-sm' : 'text-muted-foreground'
              }`}
              key={value}
              onClick={() => setTab(value)}
              type="button"
            >
              {value}
            </button>
          ))}
        </div>
        <div className="mt-6 space-y-2">
          {items?.map((item) => (
            <div className="rounded-xl border p-3" key={item.id}>
              <p className="text-sm font-semibold">{item.name}</p>
              {'subject' in item && (
                <p className="truncate text-xs text-muted-foreground">
                  {item.subject || 'No subject'}
                </p>
              )}
            </div>
          ))}
          {items?.length === 0 && (
            <p className="rounded-xl border border-dashed p-5 text-center text-sm text-muted-foreground">
              No custom {tab} yet.
            </p>
          )}
        </div>
        <form
          className="mt-8 space-y-3 border-t pt-6"
          onSubmit={(event) => {
            event.preventDefault()
            create.mutate()
          }}
        >
          <h3 className="font-semibold">Create {tab.slice(0, -1)}</h3>
          <input
            aria-label={`${tab} name`}
            className="h-10 w-full rounded-xl border bg-background px-3 text-sm"
            onChange={(event) => setName(event.target.value)}
            placeholder="Name"
            required
            value={name}
          />
          {tab === 'templates' && (
            <input
              aria-label="Template subject"
              className="h-10 w-full rounded-xl border bg-background px-3 text-sm"
              onChange={(event) => setSubject(event.target.value)}
              placeholder="Subject"
              value={subject}
            />
          )}
          {tab !== 'folders' && (
            <textarea
              aria-label={`${tab} content`}
              className="min-h-28 w-full rounded-xl border bg-background p-3 text-sm"
              onChange={(event) => setBody(event.target.value)}
              placeholder="HTML or text content"
              required
              value={body}
            />
          )}
          <button
            className="h-10 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-60"
            disabled={create.isPending}
            type="submit"
          >
            {create.isPending ? 'Creating…' : 'Create'}
          </button>
        </form>
      </aside>
    </div>
  )
}

function ComposerAddress({
  label,
  value,
  onChange,
  children,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  children?: ReactNode
}) {
  return (
    <label className="flex min-h-11 items-center gap-3 text-sm">
      <span className="w-8 shrink-0 text-xs font-medium text-muted-foreground">
        {label}
      </span>
      <input
        aria-label={`${label} recipients`}
        className="min-w-0 flex-1 bg-transparent outline-none"
        onChange={(event) => onChange(event.target.value)}
        placeholder="name@company.com, another@company.com"
        value={value}
      />
      {children}
    </label>
  )
}

function Pagination({
  page,
  pageSize,
  total,
  totalPages,
  setPage,
  setPageSize,
}: {
  page: number
  pageSize: number
  total: number
  totalPages: number
  setPage: (value: number) => void
  setPageSize: (value: number) => void
}) {
  return (
    <div className="flex items-center gap-1 border-t bg-card px-3 py-2 text-xs">
      <span className="hidden text-muted-foreground xl:inline">
        {total ? (page - 1) * pageSize + 1 : 0}–
        {Math.min(page * pageSize, total)} of {total}
      </span>
      <select
        aria-label="Messages per page"
        className="ml-auto rounded-lg border bg-background px-1 py-1"
        onChange={(event) => {
          setPageSize(Number(event.target.value))
          setPage(1)
        }}
        value={pageSize}
      >
        {[10, 25, 50, 100].map((value) => (
          <option key={value} value={value}>
            {value}
          </option>
        ))}
      </select>
      <button
        aria-label="First page"
        className="rounded p-1.5 hover:bg-muted disabled:opacity-40"
        disabled={page === 1}
        onClick={() => setPage(1)}
        type="button"
      >
        <span className="text-[10px]">First</span>
      </button>
      <button
        aria-label="Previous page"
        className="rounded p-1.5 hover:bg-muted disabled:opacity-40"
        disabled={page === 1}
        onClick={() => setPage(page - 1)}
        type="button"
      >
        <ChevronLeft className="size-4" />
      </button>
      <span className="min-w-12 text-center">
        {page}/{totalPages}
      </span>
      <button
        aria-label="Next page"
        className="rounded p-1.5 hover:bg-muted disabled:opacity-40"
        disabled={page >= totalPages}
        onClick={() => setPage(page + 1)}
        type="button"
      >
        <ChevronRight className="size-4" />
      </button>
      <button
        aria-label="Last page"
        className="rounded p-1.5 hover:bg-muted disabled:opacity-40"
        disabled={page >= totalPages}
        onClick={() => setPage(totalPages)}
        type="button"
      >
        <span className="text-[10px]">Last</span>
      </button>
    </div>
  )
}

function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof Mail
  title: string
  description: string
}) {
  return (
    <div className="grid min-h-64 place-items-center p-8 text-center">
      <div>
        <div className="mx-auto mb-3 grid size-12 place-items-center rounded-2xl bg-muted text-muted-foreground">
          <Icon className="size-5" />
        </div>
        <p className="font-semibold">{title}</p>
        <p className="mt-1 max-w-xs text-sm text-muted-foreground">
          {description}
        </p>
      </div>
    </div>
  )
}

function recipients(value: string) {
  return value
    .split(/[;,]/)
    .map((email) => email.trim())
    .filter(Boolean)
    .map((email) => ({ email }))
}

function applyTemplate(
  item: MailTemplate,
  setDraft: Dispatch<SetStateAction<MailDraft>>,
  editor: RefObject<HTMLDivElement | null>,
) {
  setDraft((current) => ({ ...current, subject: item.subject }))
  if (editor.current) editor.current.innerHTML = item.body_html
}

function formatDate(value: string) {
  const date = new Date(value)
  const today = new Date()
  return date.toDateString() === today.toDateString()
    ? date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function initials(value: string) {
  return (
    value
      .split(/\s+/)
      .map((item) => item[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || 'MH'
  )
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}
