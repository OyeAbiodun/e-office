import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import {
  AtSign,
  Bookmark,
  Bold,
  Check,
  Code2,
  Copy,
  Ellipsis,
  Hash,
  Italic,
  List,
  PanelRightClose,
  PanelRightOpen,
  Pin,
  Send,
  Smile,
  Trash2,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { chatApi, type ChatMessage } from '@/features/chat/api'

type SidePanel = 'details' | 'pins' | null

export function ConversationPage({ thread = false }: { thread?: boolean }) {
  const params = useParams({ strict: false }) as {
    conversationId: string
    messageId?: string
  }
  const { conversationId, messageId } = params
  const queryClient = useQueryClient()
  const conversation = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: () => chatApi.get(conversationId),
  })
  const messages = useQuery({
    queryKey: ['messages', conversationId, messageId],
    queryFn: () =>
      chatApi.messages(conversationId, thread ? messageId : undefined),
  })
  const pins = useQuery({
    queryKey: ['conversation-pins', conversationId],
    queryFn: () => chatApi.pins(conversationId),
  })
  const tabs = useQuery({
    queryKey: ['channel-tabs', conversationId],
    queryFn: () => chatApi.tabs(conversationId),
    enabled: Boolean(conversation.data?.team_id),
  })
  const draft = useQuery({
    queryKey: ['message-draft', conversationId],
    queryFn: () => chatApi.draft(conversationId),
  })
  const [body, setBody] = useState('')
  const [draftReady, setDraftReady] = useState(false)
  const [typingUsers, setTypingUsers] = useState<string[]>([])
  const [sidePanel, setSidePanel] = useState<SidePanel>(null)
  const [emojiOpen, setEmojiOpen] = useState(false)
  const [sending, setSending] = useState(false)
  const [connection, setConnection] = useState<
    'connecting' | 'connected' | 'offline'
  >('connecting')
  const socketRef = useRef<WebSocket | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const typingTimer = useRef<number | null>(null)
  const draftTimer = useRef<number | null>(null)
  const lastTypingSentAt = useRef(0)
  const messageKey = ['messages', conversationId, messageId] as const

  useEffect(() => {
    if (!draft.isSuccess || draftReady) return
    setBody(draft.data?.body ?? '')
    setDraftReady(true)
  }, [draft.data, draft.isSuccess, draftReady])

  useEffect(() => {
    const socket = chatApi.socket(conversationId)
    socketRef.current = socket
    if (!socket) {
      setConnection('offline')
      return
    }
    socket.onopen = () => setConnection('connected')
    socket.onclose = () => setConnection('offline')
    socket.onerror = () => setConnection('offline')
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(String(event.data)) as {
          type?: string
          data?: { user_id?: string; active?: boolean }
        }
        if (payload.type === 'typing' && payload.data?.user_id) {
          setTypingUsers((current) =>
            payload.data?.active
              ? [...new Set([...current, payload.data.user_id as string])]
              : current.filter((id) => id !== payload.data?.user_id),
          )
        } else {
          void queryClient.invalidateQueries({
            queryKey: ['messages', conversationId],
          })
          void queryClient.invalidateQueries({ queryKey: ['chat-dashboard'] })
        }
      } catch {
        void queryClient.invalidateQueries({
          queryKey: ['messages', conversationId],
        })
      }
    }
    return () => socket.close()
  }, [conversationId, queryClient])

  const replaceOptimistic = (localId: string, message: ChatMessage) => {
    queryClient.setQueryData<{
      items: ChatMessage[]
      next_cursor: string | null
      has_more: boolean
    }>(messageKey, (current) =>
      current
        ? {
            ...current,
            items: current.items.map((item) =>
              item.id === localId
                ? {
                    ...item,
                    ...message,
                    body: message.body ?? item.body,
                    sender_name: message.sender_name ?? item.sender_name,
                    reactions: message.reactions ?? item.reactions,
                    attachments: message.attachments ?? item.attachments,
                  }
                : item,
            ),
          }
        : current,
    )
  }
  const send = async (retry?: ChatMessage) => {
    if ((!retry && !body.trim()) || sending) return
    const content = retry?.body ?? body.trim()
    const clientMessageId = retry?.id.startsWith('optimistic-')
      ? retry.id.replace('optimistic-', '')
      : crypto.randomUUID()
    const localId = retry?.id ?? `optimistic-${clientMessageId}`
    const payload = {
      body: content,
      parent_message_id: thread ? messageId : null,
      message_type: 'rich_text',
      client_message_id: clientMessageId,
    }
    if (!retry) {
      const optimistic: ChatMessage = {
        id: localId,
        conversation_id: conversationId,
        sender_id: 'current-user',
        sender_name: 'You',
        parent_message_id: thread ? messageId ?? null : null,
        message_type: 'rich_text',
        body: content,
        edited: false,
        edited_at: null,
        deleted_at: null,
        created_at: new Date().toISOString(),
        reactions: [],
        attachments: [],
        thread: null,
        delivery_status: 'sending',
        optimistic_state: 'sending',
      }
      queryClient.setQueryData<{
        items: ChatMessage[]
        next_cursor: string | null
        has_more: boolean
      }>(messageKey, (current) =>
        current ? { ...current, items: [...current.items, optimistic] } : current,
      )
    }
    if (!retry) setBody('')
    setSending(true)
    try {
      // The REST endpoint is the authoritative idempotent write path. The
      // WebSocket remains a receive/typing transport, avoiding API+socket
      // duplicate sends and allowing retry to reuse the same client id.
      const authoritative = await chatApi.send(conversationId, payload)
      replaceOptimistic(localId, authoritative)
      queryClient.setQueryData(['message-draft', conversationId], null)
      setDraftReady(true)
      await queryClient.invalidateQueries({ queryKey: ['chat-dashboard'] })
    } catch {
      queryClient.setQueryData<{
        items: ChatMessage[]
        next_cursor: string | null
        has_more: boolean
      }>(messageKey, (current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.id === localId
                  ? { ...item, delivery_status: 'failed', optimistic_state: 'failed' }
                  : item,
              ),
            }
          : current,
      )
    } finally {
      setSending(false)
    }
  }
  const typingChanged = (value: string) => {
    setBody(value)
    if (draftTimer.current) window.clearTimeout(draftTimer.current)
    draftTimer.current = window.setTimeout(() => {
      void chatApi.saveDraft(conversationId, value)
    }, 600)
    const now = Date.now()
    if (now - lastTypingSentAt.current > 900) {
      socketRef.current?.send(
        JSON.stringify({ type: 'typing', data: { active: true } }),
      )
      lastTypingSentAt.current = now
    }
    if (typingTimer.current) window.clearTimeout(typingTimer.current)
    typingTimer.current = window.setTimeout(
      () =>
        socketRef.current?.send(
          JSON.stringify({ type: 'typing', data: { active: false } }),
        ),
      1500,
    )
  }
  const insert = (prefix: string, suffix = prefix) => {
    const input = textareaRef.current
    if (!input) return
    const start = input.selectionStart
    const end = input.selectionEnd
    const selection = body.slice(start, end)
    const value = `${body.slice(0, start)}${prefix}${selection}${suffix}${body.slice(end)}`
    setBody(value)
    window.setTimeout(() => {
      input.focus()
      input.setSelectionRange(start + prefix.length, end + prefix.length)
    }, 0)
  }

  if (conversation.isLoading || messages.isLoading)
    return (
      <div
        aria-label="Loading conversation"
        aria-live="polite"
        className="space-y-4 p-6"
        role="status"
      >
        {[1, 2, 3, 4].map((item) => (
          <div className="h-20 animate-pulse rounded-xl bg-muted" key={item} />
        ))}
      </div>
    )
  if (conversation.isError || messages.isError || !conversation.data)
    return (
      <div
        className="grid min-h-[65vh] place-items-center p-8 text-center"
        role="alert"
      >
        <div>
          <h1 className="text-xl font-semibold">Conversation unavailable</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            It may have been removed or your connection was interrupted.
          </p>
          <button
            className="mt-4 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            onClick={() =>
              void Promise.all([conversation.refetch(), messages.refetch()])
            }
            type="button"
          >
            Retry
          </button>
        </div>
      </div>
    )

  return (
    <div className="flex h-[calc(100vh-6.25rem)] min-h-[560px]">
      <aside className="hidden w-64 shrink-0 border-r bg-card/55 xl:block">
        <div className="p-4">
          <Link className="text-sm font-semibold text-primary" to="/chat">
            ← All conversations
          </Link>
          <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Current
          </p>
          <div className="mt-2 flex items-center gap-2 rounded-xl bg-primary/10 px-3 py-2.5 text-sm font-semibold text-primary">
            <Hash className="size-4" />
            <span className="truncate">
              {conversation.data.name || 'Direct conversation'}
            </span>
          </div>
          <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Explore
          </p>
          <Link
            className="mt-2 flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted"
            to="/chat/channels"
          >
            <Hash className="size-4" />
            Teams & channels
          </Link>
          <Link
            className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted"
            to="/chat/archived"
          >
            <Pin className="size-4" />
            Archived
          </Link>
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b px-4 sm:px-5">
          <div className="min-w-0">
            <h1 className="truncate font-semibold">
              {thread
                ? 'Thread'
                : conversation.data.name || 'Direct conversation'}
            </h1>
            <p className="text-xs text-muted-foreground">
              {conversation.data.member_count} members ·{' '}
              <span
                className={connection === 'connected' ? 'text-emerald-500' : ''}
              >
                {connection}
              </span>
            </p>
          </div>
          <div className="flex gap-1">
            <button
              aria-label="Pinned messages"
              aria-pressed={sidePanel === 'pins'}
              className="grid size-9 place-items-center rounded-lg hover:bg-muted"
              onClick={() => setSidePanel(sidePanel === 'pins' ? null : 'pins')}
              type="button"
            >
              <Pin className="size-4" />
            </button>
            <button
              aria-label="Conversation details"
              aria-pressed={sidePanel === 'details'}
              className="grid size-9 place-items-center rounded-lg hover:bg-muted"
              onClick={() =>
                setSidePanel(sidePanel === 'details' ? null : 'details')
              }
              type="button"
            >
              <Users className="size-4" />
            </button>
            <button
              aria-label={
                sidePanel
                  ? 'Close collaboration panel'
                  : 'Open collaboration panel'
              }
              className="hidden size-9 place-items-center rounded-lg hover:bg-muted sm:grid"
              onClick={() => setSidePanel(sidePanel ? null : 'details')}
              type="button"
            >
              {sidePanel ? (
                <PanelRightClose className="size-4" />
              ) : (
                <PanelRightOpen className="size-4" />
              )}
            </button>
          </div>
        </header>
        {tabs.data && tabs.data.length > 0 && !thread && (
          <nav
            aria-label="Channel tabs"
            className="flex shrink-0 gap-1 overflow-x-auto border-b px-3 py-2"
          >
            {tabs.data.map((tab, index) => (
              <button
                aria-current={index === 0 ? 'page' : undefined}
                className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${
                  index === 0
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted'
                }`}
                key={tab.id}
                title={`${tab.name} channel workspace`}
                type="button"
              >
                {tab.name}
              </button>
            ))}
          </nav>
        )}
        {connection === 'offline' && (
          <div
            className="bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-700 dark:text-amber-300"
            role="status"
          >
            Realtime connection is offline. Messages will use the API until you
            reconnect.
          </div>
        )}
        <section
          aria-label="Messages"
          aria-live="polite"
          className="flex-1 space-y-1 overflow-y-auto p-3 sm:p-6"
        >
          {messages.data?.items.length === 0 && (
            <div className="grid h-full place-items-center text-center">
              <div>
                <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary/10 text-primary">
                  <Hash className="size-7" />
                </span>
                <h2 className="mt-4 text-xl font-semibold">
                  Start the conversation
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Share an update, ask a question, or add a code block.
                </p>
              </div>
            </div>
          )}
          {messages.data?.items.map((message) => (
            <MessageRow
              conversationId={conversationId}
              key={message.id}
              message={message}
              onChanged={async () => {
                await queryClient.invalidateQueries({
                  queryKey: ['messages', conversationId],
                })
                await queryClient.invalidateQueries({
                  queryKey: ['conversation-pins', conversationId],
                })
              }}
              onRetry={
                message.optimistic_state === 'failed'
                  ? () => void send(message)
                  : undefined
              }
            />
          ))}
          {typingUsers.length > 0 && (
            <p
              className="px-12 py-2 text-xs text-muted-foreground"
              role="status"
            >
              {typingUsers.length === 1
                ? '1 person is typing…'
                : `${typingUsers.length} people are typing…`}
            </p>
          )}
        </section>
        <Composer
          body={body}
          conversationName={conversation.data.name || 'conversation'}
          emojiOpen={emojiOpen}
          insert={insert}
          onBody={typingChanged}
          onEmoji={() => setEmojiOpen((value) => !value)}
          onSend={() => void send()}
          sending={sending}
          textareaRef={textareaRef}
        />
      </main>
      {sidePanel && (
        <aside className="fixed inset-y-0 right-0 z-40 w-[min(90vw,360px)] border-l bg-card p-5 shadow-2xl sm:static sm:z-auto sm:w-80 sm:shadow-none">
          <header className="flex items-center">
            <h2 className="font-semibold">
              {sidePanel === 'pins'
                ? 'Pinned messages'
                : 'Conversation details'}
            </h2>
            <button
              aria-label="Close collaboration panel"
              className="ml-auto rounded-lg p-2 hover:bg-muted"
              onClick={() => setSidePanel(null)}
              type="button"
            >
              <X className="size-4" />
            </button>
          </header>
          {sidePanel === 'details' && (
            <div className="mt-6 space-y-4">
              <div className="grid size-14 place-items-center rounded-2xl bg-primary/10 text-primary">
                <Hash className="size-7" />
              </div>
              <div>
                <p className="font-semibold">
                  {conversation.data.name || 'Direct conversation'}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {conversation.data.description ||
                    'Focused collaboration space'}
                </p>
              </div>
              <dl className="space-y-3 rounded-xl border p-4 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Members</dt>
                  <dd>{conversation.data.member_count}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Type</dt>
                  <dd className="capitalize">
                    {conversation.data.type.replaceAll('_', ' ')}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Visibility</dt>
                  <dd className="capitalize">{conversation.data.visibility}</dd>
                </div>
              </dl>
            </div>
          )}
          {sidePanel === 'pins' && (
            <div className="mt-5 space-y-3">
              {pins.isLoading && (
                <div className="h-20 animate-pulse rounded-xl bg-muted" />
              )}
              {pins.data?.map((pin, index) => (
                <article
                  className="rounded-xl border p-4 text-sm"
                  key={String(pin.id ?? index)}
                >
                  <p>
                    {String(pin.body ?? pin.message_body ?? 'Pinned message')}
                  </p>
                </article>
              ))}
              {!pins.isLoading && !pins.data?.length && (
                <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                  No messages have been pinned.
                </p>
              )}
            </div>
          )}
        </aside>
      )}
    </div>
  )
}

function Composer({
  body,
  conversationName,
  emojiOpen,
  insert,
  onBody,
  onEmoji,
  onSend,
  sending,
  textareaRef,
}: {
  body: string
  conversationName: string
  emojiOpen: boolean
  insert: (prefix: string, suffix?: string) => void
  onBody: (value: string) => void
  onEmoji: () => void
  onSend: () => void
  sending: boolean
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
}) {
  const controls = [
    { icon: Bold, label: 'Bold', action: () => insert('**') },
    { icon: Italic, label: 'Italic', action: () => insert('_') },
    {
      icon: Code2,
      label: 'Code block',
      action: () => insert('```\n', '\n```'),
    },
    { icon: List, label: 'List', action: () => insert('- ', '') },
    { icon: AtSign, label: 'Mention', action: () => insert('@', '') },
  ]
  return (
    <footer className="shrink-0 border-t bg-card p-3 sm:p-4">
      <div className="relative rounded-2xl border bg-background shadow-sm focus-within:ring-2 focus-within:ring-primary/40">
        <div className="flex gap-1 border-b p-2">
          {controls.map(({ icon: Icon, label, action }) => (
            <button
              aria-label={label}
              className="grid size-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
              key={label}
              onClick={action}
              type="button"
            >
              <Icon className="size-4" />
            </button>
          ))}
        </div>
        <textarea
          aria-label="Message composer"
          className="min-h-20 w-full resize-none bg-transparent p-3 text-sm outline-none"
          onChange={(event) => onBody(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onSend()
            }
          }}
          placeholder={`Message ${conversationName}`}
          ref={textareaRef}
          value={body}
        />
        <div className="flex items-center justify-between px-2 pb-2">
          <div className="relative">
            <button
              aria-expanded={emojiOpen}
              aria-label="Emoji picker"
              className="grid size-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted"
              onClick={onEmoji}
              type="button"
            >
              <Smile className="size-4" />
            </button>
            {emojiOpen && (
              <div className="absolute bottom-10 left-0 flex rounded-xl border bg-card p-2 shadow-xl">
                {['👍', '❤️', '🎉', '😂', '🚀', '✅'].map((emoji) => (
                  <button
                    aria-label={`Insert ${emoji}`}
                    className="grid size-9 place-items-center rounded-lg text-lg hover:bg-muted"
                    key={emoji}
                    onClick={() => {
                      insert(emoji, '')
                      onEmoji()
                    }}
                    type="button"
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            aria-label="Send message"
            className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground disabled:opacity-40"
            disabled={!body.trim() || sending}
            onClick={onSend}
            type="button"
          >
            {sending ? (
              <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              <Send className="size-4" />
            )}
          </button>
        </div>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Enter to send · Shift + Enter for a new line
      </p>
    </footer>
  )
}

function MessageRow({
  message,
  conversationId,
  onChanged,
  onRetry,
}: {
  message: ChatMessage
  conversationId: string
  onChanged: () => Promise<void>
  onRetry?: () => void
}) {
  const [menu, setMenu] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editBody, setEditBody] = useState(message.body)
  const update = async () => {
    if (!editBody.trim()) return
    await chatApi.edit(message.id, editBody.trim())
    setEditing(false)
    await onChanged()
  }
  return (
    <article className="group relative flex gap-3 rounded-xl px-2 py-3 hover:bg-muted/50">
      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-sm font-semibold text-primary">
        {(message.sender_name || 'You').charAt(0)}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <p className="text-sm font-semibold">{message.sender_name || 'You'}</p>
          <time className="text-xs text-muted-foreground">
            {new Date(message.created_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </time>
          {message.optimistic_state === 'sending' && (
            <span className="text-xs text-muted-foreground">Sending…</span>
          )}
          {message.optimistic_state === 'failed' && (
            <button
              className="text-xs font-semibold text-destructive underline"
              onClick={onRetry}
              type="button"
            >
              Not sent · Retry
            </button>
          )}
          {message.edited && (
            <span className="text-xs text-muted-foreground">(edited)</span>
          )}
        </div>
        {editing ? (
          <div className="mt-2 flex gap-2">
            <textarea
              aria-label="Edit message"
              className="min-h-20 flex-1 rounded-xl border bg-background p-3 text-sm"
              onChange={(event) => setEditBody(event.target.value)}
              value={editBody}
            />
            <div className="space-y-1">
              <button
                aria-label="Save edited message"
                className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground"
                onClick={() => void update()}
                type="button"
              >
                <Check className="size-4" />
              </button>
              <button
                aria-label="Cancel editing"
                className="grid size-9 place-items-center rounded-lg border"
                onClick={() => setEditing(false)}
                type="button"
              >
                <X className="size-4" />
              </button>
            </div>
          </div>
        ) : (
          <RichMessage
            deleted={Boolean(message.deleted_at)}
            value={message.body}
          />
        )}
        <div className="mt-2 flex flex-wrap gap-1">
          {(message.reactions ?? []).map((reaction) => (
            <span
              className="rounded-full border bg-background px-2 py-0.5 text-xs"
              key={reaction.id}
            >
              {reaction.emoji}
            </span>
          ))}
          {!message.deleted_at && (
            <button
              aria-label="React with thumbs up"
              className="rounded-full border px-2 py-0.5 text-xs opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
              onClick={() =>
                void chatApi.react(message.id, '👍').then(onChanged)
              }
              type="button"
            >
              + 👍
            </button>
          )}
        </div>
        {message.thread && (
          <Link
            className="mt-2 inline-block text-xs font-medium text-primary"
            params={{ conversationId, messageId: message.id }}
            to="/chat/$conversationId/thread/$messageId"
          >
            {message.thread.reply_count} replies · Open thread
          </Link>
        )}
      </div>
      {!message.deleted_at && (
        <div className="absolute right-2 top-2">
          <button
            aria-expanded={menu}
            aria-label="Message actions"
            className="grid size-8 place-items-center rounded-lg border bg-card opacity-100 shadow-sm sm:opacity-0 sm:group-hover:opacity-100"
            onClick={() => setMenu((value) => !value)}
            type="button"
          >
            <Ellipsis className="size-4" />
          </button>
          {menu && (
            <div className="absolute right-0 top-9 z-20 w-44 rounded-xl border bg-card p-1 shadow-xl">
              <button
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-muted"
                onClick={() => {
                  setEditing(true)
                  setMenu(false)
                }}
                type="button"
              >
                <Code2 className="size-4" />
                Edit
              </button>
              <button
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-muted"
                onClick={() =>
                  void navigator.clipboard
                    .writeText(message.body)
                    .then(() => setMenu(false))
                }
                type="button"
              >
                <Copy className="size-4" />
                Copy
              </button>
              <button
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-muted"
                onClick={() =>
                  void chatApi.pin(message.id).then(() => {
                    setMenu(false)
                    return onChanged()
                  })
                }
                type="button"
              >
                <Pin className="size-4" />
                Pin
              </button>
              <button
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-muted"
                onClick={() =>
                  void chatApi.saveMessage(message.id).then(() => {
                    setMenu(false)
                  })
                }
                type="button"
              >
                <Bookmark className="size-4" />
                Save for later
              </button>
              <button
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-500 hover:bg-muted"
                onClick={() => {
                  void chatApi.remove(message.id).then(onChanged)
                  setMenu(false)
                }}
                type="button"
              >
                <Trash2 className="size-4" />
                Delete
              </button>
            </div>
          )}
        </div>
      )}
    </article>
  )
}

function RichMessage({ value, deleted }: { value: string; deleted: boolean }) {
  if (deleted)
    return (
      <p className="mt-1 text-sm italic text-muted-foreground">
        Message deleted
      </p>
    )
  if (value.startsWith('```') && value.endsWith('```'))
    return (
      <pre className="mt-2 overflow-x-auto rounded-xl bg-muted p-3 text-sm">
        <code>{value.slice(3, -3).trim()}</code>
      </pre>
    )
  const parts = value.split(/(\*\*[^*]+\*\*)/g)
  return (
    <p className="mt-1 whitespace-pre-wrap text-sm leading-6">
      {parts.map((part, index) =>
        part.startsWith('**') && part.endsWith('**') ? (
          <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>
        ) : (
          part
        ),
      )}
    </p>
  )
}
