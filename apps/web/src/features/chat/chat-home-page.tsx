import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  Archive,
  ChevronRight,
  Hash,
  MessageCircle,
  Plus,
  Search,
  Users,
} from 'lucide-react'
import { useState } from 'react'

import { chatApi, type Conversation } from '@/features/chat/api'
import { organizationApi } from '@/features/organizations/api'

export function ChatHomePage({
  view = 'home',
}: {
  view?: 'home' | 'channels' | 'archived' | 'new'
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const dashboard = useQuery({
    queryKey: ['chat-dashboard'],
    queryFn: chatApi.dashboard,
  })
  const archived = useQuery({
    queryKey: ['conversations', true],
    queryFn: () => chatApi.conversations(true),
    enabled: view === 'archived',
  })
  const workspaces = useQuery({
    queryKey: ['workspaces'],
    queryFn: organizationApi.workspaces,
  })
  const teams = useQuery({
    queryKey: ['teams'],
    queryFn: organizationApi.teams,
  })
  const members = useQuery({
    queryKey: ['members'],
    queryFn: organizationApi.members,
  })
  const [name, setName] = useState('')
  const [type, setType] = useState('workspace')
  const [channelKind, setChannelKind] = useState<
    'standard' | 'private' | 'shared'
  >('standard')
  const [teamId, setTeamId] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const create = async () => {
    const workspaceId = workspaces.data?.[0]?.id
    if (!workspaceId) return setError('Create or join a workspace first.')
    if (type !== 'direct' && !name.trim())
      return setError('Enter a conversation name.')
    if (type === 'direct' && selected.length !== 1)
      return setError('Choose one person for a direct message.')
    if (type.includes('team') && !teamId)
      return setError('Choose the team this channel belongs to.')
    setCreating(true)
    setError('')
    try {
      const conversation = await chatApi.create({
        workspace_id: workspaceId,
        type,
        name: name || null,
        member_ids: selected,
        visibility: type.includes('private') ? 'private' : 'members',
        channel_kind: channelKind,
        team_id: type.includes('team') ? teamId || null : null,
      })
      await queryClient.invalidateQueries({ queryKey: ['chat-dashboard'] })
      await navigate({
        to: '/chat/$conversationId',
        params: { conversationId: conversation.id },
      })
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'Conversation could not be created.',
      )
    } finally {
      setCreating(false)
    }
  }
  const base =
    view === 'archived'
      ? (archived.data ?? [])
      : view === 'channels'
        ? (dashboard.data?.recent_conversations.filter(
            (item) => item.type !== 'direct',
          ) ?? [])
        : (dashboard.data?.recent_conversations ?? [])
  const displayed = base.filter((conversation) =>
    `${conversation.name ?? ''} ${conversation.last_message?.body ?? ''}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  )
  if (dashboard.isLoading && view !== 'new')
    return (
      <div
        aria-label="Loading Chat"
        aria-live="polite"
        className="space-y-3 p-8"
        role="status"
      >
        {[1, 2, 3, 4].map((item) => (
          <div className="h-20 animate-pulse rounded-xl bg-muted" key={item} />
        ))}
      </div>
    )
  if (dashboard.isError && view !== 'new')
    return (
      <div
        className="grid min-h-[60vh] place-items-center p-8 text-center"
        role="alert"
      >
        <div>
          <h1 className="text-xl font-semibold">Chat could not connect</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Check the API connection and retry.
          </p>
          <button
            className="mt-4 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            onClick={() => void dashboard.refetch()}
            type="button"
          >
            Retry
          </button>
        </div>
      </div>
    )

  if (view === 'new')
    return (
      <div className="mx-auto max-w-4xl p-5 sm:p-8">
        <header>
          <Link className="text-sm font-semibold text-primary" to="/chat">
            ← Back to Chat
          </Link>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight">
            Start a conversation
          </h1>
          <p className="mt-2 text-muted-foreground">
            Choose the right space, then add the people who should participate.
          </p>
        </header>
        <section className="mt-7 space-y-5 rounded-2xl border bg-card p-6 shadow-sm">
          <label className="block text-sm font-medium">
            Conversation type
            <select
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              onChange={(event) => {
                setType(event.target.value)
                setSelected([])
              }}
              value={type}
            >
              <option value="direct">Direct message</option>
              <option value="private_group">Group conversation</option>
              <option value="public_team">Public team channel</option>
              <option value="private_team">Private team channel</option>
              <option value="workspace">Workspace channel</option>
              <option value="announcement">Organization announcements</option>
            </select>
          </label>
          {type !== 'direct' && (
            <>
              <label className="block text-sm font-medium">
                Name
                <input
                  className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) => setName(event.target.value)}
                  placeholder="e.g. Product launch"
                  value={name}
                />
              </label>
              {type.includes('team') && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block text-sm font-medium">
                    Team
                    <select
                      className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                      onChange={(event) => setTeamId(event.target.value)}
                      value={teamId}
                    >
                      <option value="">Choose a team</option>
                      {teams.data?.map((team) => (
                        <option key={team.id} value={team.id}>
                          {team.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-sm font-medium">
                    Channel access
                    <select
                      className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                      onChange={(event) =>
                        setChannelKind(
                          event.target.value as
                            'standard' | 'private' | 'shared',
                        )
                      }
                      value={channelKind}
                    >
                      <option value="standard">Standard</option>
                      <option value="private">Private</option>
                      <option value="shared">Shared</option>
                    </select>
                  </label>
                </div>
              )}
            </>
          )}
          <fieldset>
            <legend className="text-sm font-medium">Members</legend>
            <div className="mt-2 grid max-h-72 gap-2 overflow-y-auto sm:grid-cols-2">
              {members.data?.map((member) => {
                const active = selected.includes(member.id)
                return (
                  <button
                    aria-pressed={active}
                    className={`rounded-xl border p-3 text-left text-sm transition ${active ? 'border-primary bg-primary/5' : 'hover:bg-muted'}`}
                    key={member.id}
                    onClick={() =>
                      setSelected(
                        active
                          ? selected.filter((id) => id !== member.id)
                          : type === 'direct'
                            ? [member.id]
                            : [...selected, member.id],
                      )
                    }
                    type="button"
                  >
                    <span className="block font-semibold">
                      {member.display_name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {member.email}
                    </span>
                  </button>
                )
              })}
            </div>
          </fieldset>
          {error && (
            <p className="text-sm text-red-500" role="alert">
              {error}
            </p>
          )}
          <button
            className="h-11 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={creating}
            onClick={() => void create()}
            type="button"
          >
            {creating ? 'Creating…' : 'Create conversation'}
          </button>
        </section>
      </div>
    )

  return (
    <div className="flex min-h-[calc(100vh-6.25rem)]">
      <aside className="hidden w-72 shrink-0 border-r bg-card/45 p-4 lg:block">
        <Link
          className="flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground"
          to="/chat/new"
        >
          <Plus className="size-4" />
          New message
        </Link>
        <nav className="mt-5 space-y-1" aria-label="Chat navigation">
          <Link
            activeOptions={{ exact: true }}
            activeProps={{ className: 'bg-muted text-foreground' }}
            className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted"
            to="/chat"
          >
            <MessageCircle className="size-4" />
            Recent
          </Link>
          <Link
            activeProps={{ className: 'bg-muted text-foreground' }}
            className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted"
            to="/chat/channels"
          >
            <Hash className="size-4" />
            Teams & channels
          </Link>
          <Link
            activeProps={{ className: 'bg-muted text-foreground' }}
            className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted"
            to="/chat/archived"
          >
            <Archive className="size-4" />
            Archived
          </Link>
        </nav>
        <p className="mt-7 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Teams
        </p>
        <div className="mt-2 space-y-1">
          {teams.data?.map((team) => (
            <div className="rounded-xl px-3 py-2 text-sm" key={team.id}>
              <p className="flex items-center gap-2 font-semibold">
                <Users className="size-4 text-primary" />
                {team.name}
              </p>
              <p className="mt-1 pl-6 text-xs text-muted-foreground">
                {displayed.filter((item) => item.team_id === team.id).length}{' '}
                channels
              </p>
            </div>
          ))}
          {!teams.data?.length && (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              No teams yet.
            </p>
          )}
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-5 sm:p-8">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-primary">Conversations</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">
              {view === 'channels'
                ? 'Teams and channels'
                : view === 'archived'
                  ? 'Archived'
                  : 'Chat'}
            </h1>
            <p className="mt-2 text-muted-foreground">
              {dashboard.data?.unread_messages ?? 0} unread ·{' '}
              {dashboard.data?.online_members ?? 0} people online
            </p>
          </div>
          <Link
            className="flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground lg:hidden"
            to="/chat/new"
          >
            <Plus className="size-4" />
            New
          </Link>
        </header>
        <div className="relative mt-6">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            aria-label="Filter conversations"
            className="h-11 w-full rounded-xl border bg-card pl-10 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search conversations and messages"
            value={search}
          />
        </div>
        <section className="mt-4 overflow-hidden rounded-2xl border bg-card shadow-sm">
          {displayed.map((conversation) => (
            <ConversationRow
              conversation={conversation}
              key={conversation.id}
            />
          ))}
          {!displayed.length && (
            <div className="p-12 text-center">
              <MessageCircle className="mx-auto size-8 text-muted-foreground" />
              <h2 className="mt-3 font-semibold">
                {search ? 'No matching conversations' : 'No conversations yet'}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {search
                  ? 'Try a different search.'
                  : 'Start a focused conversation or create a channel.'}
              </p>
              {!search && (
                <Link
                  className="mt-4 inline-flex text-sm font-semibold text-primary"
                  to="/chat/new"
                >
                  Start a conversation
                </Link>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

function ConversationRow({ conversation }: { conversation: Conversation }) {
  return (
    <Link
      className="flex items-center gap-4 border-b p-4 transition last:border-b-0 hover:bg-muted/45"
      params={{ conversationId: conversation.id }}
      to="/chat/$conversationId"
    >
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
        {conversation.type === 'direct' ? (
          <MessageCircle className="size-5" />
        ) : (
          <Hash className="size-5" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate font-semibold">
            {conversation.name || 'Direct conversation'}
          </p>
          <span className="text-xs capitalize text-muted-foreground">
            {conversation.type.replaceAll('_', ' ')}
          </span>
        </div>
        <p className="mt-1 truncate text-sm text-muted-foreground">
          {conversation.last_message?.body ||
            conversation.description ||
            'No messages yet'}
        </p>
      </div>
      <div className="text-right">
        {conversation.unread_count > 0 && (
          <span className="rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
            {conversation.unread_count}
          </span>
        )}
        <p className="mt-2 text-xs text-muted-foreground">
          {conversation.member_count} members
        </p>
      </div>
      <ChevronRight className="size-4 text-muted-foreground" />
    </Link>
  )
}
