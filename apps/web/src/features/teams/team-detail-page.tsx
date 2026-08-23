import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import {
  Activity,
  AppWindow,
  Archive,
  ArrowLeft,
  CalendarDays,
  FileText,
  Hash,
  Heart,
  Megaphone,
  MoreHorizontal,
  NotebookPen,
  Pin,
  Plus,
  RotateCcw,
  Save,
  Search,
  ShieldCheck,
  Users,
  Video,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  teamsApi,
  type TeamChannel,
  type TeamOverview,
} from '@/features/teams/api'

type Section =
  | 'posts'
  | 'channels'
  | 'calendar'
  | 'meetings'
  | 'files'
  | 'wiki'
  | 'notes'
  | 'apps'
  | 'members'
  | 'activity'
  | 'settings'

const navigation: Array<[Section, string]> = [
  ['posts', 'Posts'],
  ['channels', 'Channels'],
  ['calendar', 'Calendar'],
  ['meetings', 'Meetings'],
  ['files', 'Files'],
  ['wiki', 'Wiki'],
  ['notes', 'Notes'],
  ['apps', 'Apps'],
  ['members', 'Members'],
  ['activity', 'Activity'],
  ['settings', 'Settings'],
]

export function TeamDetailPage() {
  const { teamId } = useParams({ strict: false }) as { teamId: string }
  const client = useQueryClient()
  const [section, setSection] = useState<Section>('posts')
  const overview = useQuery({
    queryKey: ['team-overview', teamId],
    queryFn: () => teamsApi.overview(teamId),
  })
  const members = useQuery({
    queryKey: ['team-members', teamId],
    queryFn: () => teamsApi.members(teamId),
  })
  const channels = useQuery({
    queryKey: ['team-channels', teamId],
    queryFn: () => teamsApi.channels(teamId),
  })
  const integrations = useQuery({
    queryKey: ['team-integrations', teamId],
    queryFn: () => teamsApi.integrations(teamId),
  })
  const wikis = useQuery({
    queryKey: ['team-documents', teamId, 'wiki'],
    queryFn: () => teamsApi.documents(teamId, 'wiki'),
  })
  const notes = useQuery({
    queryKey: ['team-documents', teamId, 'note'],
    queryFn: () => teamsApi.documents(teamId, 'note'),
  })
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (!event.altKey) return
      const index = Number(event.key) - 1
      const target = navigation[index]
      if (target) {
        event.preventDefault()
        setSection(target[0])
      }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [])

  if (overview.isLoading)
    return (
      <div className="mx-auto max-w-[1500px] space-y-5 p-8">
        <div className="h-40 animate-pulse rounded-3xl bg-muted" />
        <div className="h-96 animate-pulse rounded-3xl bg-muted" />
      </div>
    )
  if (!overview.data)
    return (
      <div
        className="grid min-h-[60vh] place-items-center text-center"
        role="alert"
      >
        <div>
          <h1 className="text-xl font-semibold">Team unavailable</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            The Team could not be found in your organization.
          </p>
          <Link
            className="mt-4 inline-block font-semibold text-primary"
            to="/teams"
          >
            Return to Teams
          </Link>
        </div>
      </div>
    )

  const team = overview.data.team
  async function lifecycle() {
    if (team.archived_at) await teamsApi.restore(teamId)
    else await teamsApi.archive(teamId)
    await client.invalidateQueries({ queryKey: ['team-overview', teamId] })
  }

  return (
    <div className="mx-auto max-w-[1500px] p-3 sm:p-6">
      <Link
        className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground"
        to="/teams"
      >
        <ArrowLeft className="size-4" /> All Teams
      </Link>
      <header className="relative mt-4 overflow-hidden rounded-3xl border bg-card shadow-sm">
        <div
          className="h-24 bg-gradient-to-r from-primary/30 to-primary/5"
          style={
            team.banner_url
              ? {
                  backgroundImage: `url(${team.banner_url})`,
                  backgroundPosition: 'center',
                  backgroundSize: 'cover',
                }
              : undefined
          }
        />
        <div className="flex flex-col gap-4 p-5 pt-0 sm:flex-row sm:items-end">
          <span
            className="-mt-8 grid size-20 shrink-0 place-items-center rounded-2xl border-4 border-card text-white shadow-lg"
            style={{ background: team.color }}
          >
            {team.avatar_url ? (
              <img
                alt=""
                className="size-full rounded-xl object-cover"
                src={team.avatar_url}
              />
            ) : (
              <Users className="size-9" />
            )}
          </span>
          <div className="min-w-0 flex-1 pt-3">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold sm:text-3xl">
                {team.name}
              </h1>
              <Badge>{team.archived_at ? 'Archived' : team.visibility}</Badge>
              <Badge>{team.classification}</Badge>
            </div>
            <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
              {team.description ??
                'A focused collaboration space for this workspace.'}
            </p>
          </div>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-sm font-semibold hover:bg-muted"
            onClick={() => void lifecycle()}
            type="button"
          >
            {team.archived_at ? (
              <RotateCcw className="size-4" />
            ) : (
              <Archive className="size-4" />
            )}
            {team.archived_at ? 'Restore Team' : 'Archive Team'}
          </button>
        </div>
      </header>

      <nav
        aria-label="Team navigation"
        className="mt-4 flex gap-1 overflow-x-auto rounded-2xl border bg-card p-1.5"
      >
        {navigation.map(([id, label], index) => (
          <button
            aria-current={section === id ? 'page' : undefined}
            className={`shrink-0 rounded-xl px-3 py-2 text-sm font-medium transition ${
              section === id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
            key={id}
            onClick={() => setSection(id)}
            title={`Alt+${index + 1}`}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <main className="min-w-0">
          {section === 'posts' && <Posts data={overview.data} />}
          {section === 'channels' && (
            <Channels channels={channels.data ?? []} teamId={teamId} />
          )}
          {section === 'calendar' && <Calendar data={overview.data} />}
          {section === 'meetings' && <Meetings data={overview.data} />}
          {section === 'files' && <Files data={overview.data} />}
          {section === 'wiki' && (
            <Documents data={wikis.data ?? []} teamId={teamId} type="wiki" />
          )}
          {section === 'notes' && (
            <Documents data={notes.data ?? []} teamId={teamId} type="note" />
          )}
          {section === 'apps' && (
            <Apps data={integrations.data ?? []} teamId={teamId} />
          )}
          {section === 'members' && (
            <Members data={members.data ?? []} teamId={teamId} />
          )}
          {section === 'activity' && <ActivityFeed data={overview.data} />}
          {section === 'settings' && <TeamSettings data={overview.data} />}
        </main>
        <TeamInformation data={overview.data} />
      </div>
    </div>
  )
}

function Posts({ data }: { data: TeamOverview }) {
  return (
    <Panel
      title="Recent conversations"
      subtitle="The latest active channels in this Team."
    >
      <div className="divide-y">
        {data.recent_conversations.map((conversation) => (
          <Link
            className="flex items-center gap-4 py-4 hover:text-primary"
            key={conversation.id}
            params={{ conversationId: conversation.id }}
            to="/chat/$conversationId"
          >
            <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
              {conversation.channel_kind === 'announcement' ? (
                <Megaphone className="size-5" />
              ) : (
                <Hash className="size-5" />
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">
                {conversation.name}
              </span>
              <span className="text-xs capitalize text-muted-foreground">
                {conversation.channel_kind} ·{' '}
                {new Date(conversation.updated_at).toLocaleString()}
              </span>
            </span>
          </Link>
        ))}
        {!data.recent_conversations.length && (
          <Empty
            icon={Hash}
            title="No conversations yet"
            detail="Create the first Team channel."
          />
        )}
      </div>
    </Panel>
  )
}

function Channels({
  channels,
  teamId,
}: {
  channels: TeamChannel[]
  teamId: string
}) {
  const client = useQueryClient()
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('')
  const [lifecycle, setLifecycle] = useState('active')
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    name: '',
    description: '',
    channel_kind: 'standard',
    visibility: 'members',
    moderation_enabled: false,
    read_only: false,
  })
  const displayed = channels.filter(
    (channel) =>
      channel.name.toLowerCase().includes(search.toLowerCase()) &&
      (!kind || channel.channel_kind === kind) &&
      (lifecycle === 'all' ||
        (lifecycle === 'archived'
          ? Boolean(channel.archived_at)
          : !channel.archived_at)),
  )
  async function create() {
    await teamsApi.createChannel(teamId, {
      ...form,
      read_only: form.channel_kind === 'read_only' || form.read_only,
    })
    setShowCreate(false)
    setForm({ ...form, name: '', description: '' })
    await client.invalidateQueries({ queryKey: ['team-channels', teamId] })
    await client.invalidateQueries({ queryKey: ['team-overview', teamId] })
  }
  async function preference(channel: TeamChannel, type: 'favorite' | 'pinned') {
    await teamsApi.channelPreference(teamId, channel.id, {
      [type]: !channel[type],
    })
    await client.invalidateQueries({ queryKey: ['team-channels', teamId] })
  }
  async function archive(channel: TeamChannel) {
    await teamsApi.channelLifecycle(
      teamId,
      channel.id,
      channel.archived_at ? 'restore' : 'archive',
    )
    await client.invalidateQueries({ queryKey: ['team-channels', teamId] })
    await client.invalidateQueries({ queryKey: ['team-overview', teamId] })
  }
  return (
    <Panel
      title="Channel management"
      subtitle="Moderate, organize, and analyze Team conversations."
    >
      <div className="flex flex-col gap-3 border-b pb-4 sm:flex-row">
        <label className="relative flex-1">
          <span className="sr-only">Search channels</span>
          <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
          <input
            className="h-10 w-full rounded-xl border bg-background pl-9 pr-3"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search channels"
            value={search}
          />
        </label>
        <select
          aria-label="Filter channels"
          className="h-10 rounded-xl border bg-background px-3 text-sm"
          onChange={(event) => setKind(event.target.value)}
          value={kind}
        >
          <option value="">All types</option>
          <option value="standard">Standard</option>
          <option value="private">Private</option>
          <option value="announcement">Announcement</option>
          <option value="read_only">Read-only</option>
        </select>
        <select
          aria-label="Filter channel lifecycle"
          className="h-10 rounded-xl border bg-background px-3 text-sm"
          onChange={(event) => setLifecycle(event.target.value)}
          value={lifecycle}
        >
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="all">All lifecycle states</option>
        </select>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground"
          onClick={() => setShowCreate((value) => !value)}
          type="button"
        >
          <Plus className="size-4" /> New channel
        </button>
      </div>
      {showCreate && (
        <div className="my-4 grid gap-3 rounded-xl bg-muted/40 p-4 sm:grid-cols-3">
          <Input
            label="Channel name"
            value={form.name}
            onChange={(name) => setForm({ ...form, name })}
          />
          <Select
            label="Type"
            options={['standard', 'private', 'announcement', 'read_only']}
            value={form.channel_kind}
            onChange={(channel_kind) => setForm({ ...form, channel_kind })}
          />
          <button
            className="mt-6 h-11 rounded-xl bg-primary font-semibold text-primary-foreground disabled:opacity-50"
            disabled={!form.name}
            onClick={() => void create()}
            type="button"
          >
            Create channel
          </button>
        </div>
      )}
      <div className="divide-y">
        {displayed.map((channel) => (
          <div className="flex items-center gap-3 py-4" key={channel.id}>
            <Link
              className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary"
              params={{ conversationId: channel.id }}
              to="/chat/$conversationId"
            >
              {channel.channel_kind === 'announcement' ? (
                <Megaphone className="size-5" />
              ) : (
                <Hash className="size-5" />
              )}
            </Link>
            <div className="min-w-0 flex-1">
              <Link
                className="font-medium hover:text-primary"
                params={{ conversationId: channel.id }}
                to="/chat/$conversationId"
              >
                {channel.name}
              </Link>
              <p className="text-xs capitalize text-muted-foreground">
                {channel.channel_kind} · {channel.message_count} messages ·{' '}
                {channel.member_count} members
              </p>
            </div>
            {channel.moderation_enabled && <Badge>Moderated</Badge>}
            <button
              aria-label={`${channel.favorite ? 'Unfavorite' : 'Favorite'} ${channel.name}`}
              className="grid size-9 place-items-center rounded-lg hover:bg-muted"
              onClick={() => void preference(channel, 'favorite')}
              type="button"
            >
              <Heart
                className={`size-4 ${channel.favorite ? 'fill-current text-primary' : ''}`}
              />
            </button>
            <button
              aria-label={`${channel.pinned ? 'Unpin' : 'Pin'} ${channel.name}`}
              className="grid size-9 place-items-center rounded-lg hover:bg-muted"
              onClick={() => void preference(channel, 'pinned')}
              type="button"
            >
              <Pin
                className={`size-4 ${channel.pinned ? 'fill-current text-primary' : ''}`}
              />
            </button>
            <details className="relative">
              <summary
                aria-label={`Channel actions for ${channel.name}`}
                className="grid size-9 cursor-pointer list-none place-items-center rounded-lg hover:bg-muted"
              >
                <MoreHorizontal className="size-4" />
              </summary>
              <div className="absolute right-0 z-20 mt-1 w-40 rounded-xl border bg-popover p-1 shadow-xl">
                <button
                  className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-muted"
                  onClick={() => void archive(channel)}
                  type="button"
                >
                  {channel.archived_at ? 'Restore channel' : 'Archive channel'}
                </button>
              </div>
            </details>
          </div>
        ))}
        {!displayed.length && (
          <Empty
            icon={Hash}
            title="No matching channels"
            detail="Adjust the filters or create one."
          />
        )}
      </div>
    </Panel>
  )
}

function Calendar({ data }: { data: TeamOverview }) {
  return (
    <Panel
      title="Team calendar"
      subtitle="Live calendar and meeting schedule for this Team."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Stat
          label="Team calendars"
          value={data.calendar_count}
          icon={CalendarDays}
        />
        <Stat
          label="Upcoming meetings"
          value={data.upcoming_meeting_count}
          icon={Video}
        />
      </div>
      <Link
        className="mt-5 inline-flex h-10 items-center rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground"
        to="/calendar"
      >
        Open calendar
      </Link>
    </Panel>
  )
}

function Meetings({ data }: { data: TeamOverview }) {
  return (
    <Panel
      title="Team meetings"
      subtitle="Upcoming collaboration sessions from persisted data."
    >
      <div className="divide-y">
        {data.upcoming_meetings.map((meeting) => (
          <Link
            className="flex items-center gap-4 py-4 hover:text-primary"
            key={meeting.id}
            params={{ meetingId: meeting.id }}
            to="/meetings/$meetingId"
          >
            <Video className="size-5 text-primary" />
            <span className="flex-1">
              <span className="block font-medium">{meeting.title}</span>
              <span className="text-xs text-muted-foreground">
                {new Date(meeting.start_datetime).toLocaleString()}
              </span>
            </span>
            <Badge>{meeting.status}</Badge>
          </Link>
        ))}
        {!data.upcoming_meetings.length && (
          <Empty
            icon={Video}
            title="No upcoming meetings"
            detail="Schedule from MeetingHQ Calendar."
          />
        )}
      </div>
    </Panel>
  )
}

function Files({ data }: { data: TeamOverview }) {
  return (
    <Panel
      title="Team files"
      subtitle="Files shared through Team channels and meeting artifacts."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Stat label="Shared files" value={data.file_count} icon={FileText} />
        <Stat
          label="Storage used"
          value={formatBytes(data.storage_bytes)}
          icon={Archive}
        />
      </div>
      <p className="mt-5 rounded-xl bg-muted/50 p-4 text-sm text-muted-foreground">
        Files remain tenant-isolated and inherit Team channel permissions.
      </p>
    </Panel>
  )
}

function Documents({
  data,
  teamId,
  type,
}: {
  data: Awaited<ReturnType<typeof teamsApi.documents>>
  teamId: string
  type: 'wiki' | 'note'
}) {
  const client = useQueryClient()
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  async function create() {
    if (!title.trim()) return
    await teamsApi.createDocument(teamId, {
      document_type: type,
      title,
      content,
    })
    setTitle('')
    setContent('')
    await client.invalidateQueries({
      queryKey: ['team-documents', teamId, type],
    })
    await client.invalidateQueries({ queryKey: ['team-overview', teamId] })
  }
  return (
    <Panel
      title={type === 'wiki' ? 'Team Wiki' : 'Team Notes'}
      subtitle="Durable, searchable knowledge owned by this Team."
    >
      <div className="grid gap-3 rounded-xl bg-muted/40 p-4">
        <Input label="Title" value={title} onChange={setTitle} />
        <label className="text-sm font-medium">
          Content
          <textarea
            className="mt-2 min-h-24 w-full rounded-xl border bg-background p-3"
            onChange={(event) => setContent(event.target.value)}
            value={content}
          />
        </label>
        <button
          className="h-10 justify-self-start rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={!title}
          onClick={() => void create()}
          type="button"
        >
          Add {type}
        </button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {data.map((document) => (
          <article className="rounded-xl border p-4" key={document.id}>
            <NotebookPen className="size-5 text-primary" />
            <h3 className="mt-3 font-semibold">{document.title}</h3>
            <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">
              {document.content || 'No content'}
            </p>
          </article>
        ))}
      </div>
    </Panel>
  )
}

function Apps({
  data,
  teamId,
}: {
  data: Awaited<ReturnType<typeof teamsApi.integrations>>
  teamId: string
}) {
  const client = useQueryClient()
  const catalog: Array<[string, string]> = [
    ['planner', 'Planner'],
    ['power-bi', 'Power BI'],
    ['sharepoint', 'SharePoint'],
  ]
  async function connect(provider: string, displayName: string) {
    await teamsApi.updateIntegration(teamId, {
      provider,
      display_name: displayName,
      enabled: true,
      configuration: {},
    })
    await client.invalidateQueries({ queryKey: ['team-integrations', teamId] })
    await client.invalidateQueries({ queryKey: ['team-overview', teamId] })
  }
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {catalog.map(([provider, name]) => {
        const installed = data.some(
          (item) => item.provider === provider && item.enabled,
        )
        return (
          <article
            className="rounded-2xl border bg-card p-5 shadow-sm"
            key={provider}
          >
            <AppWindow className="size-8 text-primary" />
            <h2 className="mt-4 font-semibold">{name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Team-scoped integration governed by organization policy.
            </p>
            <button
              className="mt-5 h-10 rounded-xl border px-4 text-sm font-semibold disabled:opacity-60"
              disabled={installed}
              onClick={() => void connect(provider, name)}
              type="button"
            >
              {installed ? 'Connected' : 'Connect'}
            </button>
          </article>
        )
      })}
    </div>
  )
}

function Members({
  data,
  teamId,
}: {
  data: Awaited<ReturnType<typeof teamsApi.members>>
  teamId: string
}) {
  const client = useQueryClient()
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const displayed = data.filter(
    (member) =>
      `${member.display_name} ${member.email}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (!role || member.role === role),
  )
  async function bulk(action: string) {
    await teamsApi.bulkMembers(teamId, selected, action)
    setSelected([])
    await client.invalidateQueries({ queryKey: ['team-members', teamId] })
  }
  return (
    <Panel
      title="Team members"
      subtitle="Owners, administrators, members, presence, and permissions."
    >
      <div className="flex flex-col gap-3 border-b pb-4 sm:flex-row">
        <Input label="Search members" value={search} onChange={setSearch} />
        <Select
          label="Role filter"
          options={['', 'owner', 'manager', 'member']}
          value={role}
          onChange={setRole}
        />
        {selected.length > 0 && (
          <button
            className="mt-6 h-11 rounded-xl border px-4 text-sm font-semibold"
            onClick={() => void bulk('make_manager')}
            type="button"
          >
            Make administrators
          </button>
        )}
      </div>
      <div className="divide-y">
        {displayed.map((member) => (
          <div className="flex items-center gap-4 py-4" key={member.id}>
            <input
              aria-label={`Select ${member.display_name}`}
              checked={selected.includes(member.user_id)}
              disabled={member.role === 'owner'}
              onChange={() =>
                setSelected((current) =>
                  current.includes(member.user_id)
                    ? current.filter((id) => id !== member.user_id)
                    : [...current, member.user_id],
                )
              }
              type="checkbox"
            />
            <span className="relative grid size-11 place-items-center rounded-full bg-primary/10 font-semibold text-primary">
              {member.display_name.charAt(0)}
              <span className="absolute bottom-0 right-0 size-3 rounded-full border-2 border-card bg-emerald-500" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{member.display_name}</p>
              <p className="truncate text-sm text-muted-foreground">
                {member.email}
              </p>
            </div>
            <div className="text-right">
              <Badge>
                {member.role === 'manager' ? 'administrator' : member.role}
              </Badge>
              <p className="mt-1 text-xs text-muted-foreground">
                Active recently
              </p>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ActivityFeed({ data }: { data: TeamOverview }) {
  return (
    <Panel
      title="Team activity"
      subtitle="Operational events across this Team's workspace."
    >
      <div className="space-y-4">
        {data.recent_activity.map((item) => (
          <div className="flex gap-3" key={item.id}>
            <span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary">
              <Activity className="size-4" />
            </span>
            <div>
              <p className="text-sm font-medium">
                {item.event_type.replaceAll('.', ' ')}
              </p>
              <p className="text-xs text-muted-foreground">
                {new Date(item.occurred_at).toLocaleString()}
              </p>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function TeamSettings({ data }: { data: TeamOverview }) {
  const client = useQueryClient()
  const team = data.team
  const [saved, setSaved] = useState(false)
  const [form, setForm] = useState({
    name: team.name,
    description: team.description ?? '',
    color: team.color,
    avatar_url: team.avatar_url ?? '',
    banner_url: team.banner_url ?? '',
    classification: team.classification,
    visibility: team.visibility,
  })
  async function save() {
    await teamsApi.update(team.id, {
      ...form,
      avatar_url: form.avatar_url || null,
      banner_url: form.banner_url || null,
      settings: {
        policies: { guest_access: false, external_sharing: false },
        permissions: { channel_creation: 'administrators' },
        notifications: { default: 'mentions' },
      },
    })
    setSaved(true)
    await client.invalidateQueries({ queryKey: ['team-overview', team.id] })
  }
  return (
    <Panel
      title="Team settings"
      subtitle="Profile, branding, governance, permissions, and notifications."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Team name"
          value={form.name}
          onChange={(name) => setForm({ ...form, name })}
        />
        <Input
          label="Description"
          value={form.description}
          onChange={(description) => setForm({ ...form, description })}
        />
        <Input
          label="Avatar URL"
          value={form.avatar_url}
          onChange={(avatar_url) => setForm({ ...form, avatar_url })}
        />
        <Input
          label="Banner URL"
          value={form.banner_url}
          onChange={(banner_url) => setForm({ ...form, banner_url })}
        />
        <Input
          label="Brand color"
          value={form.color}
          onChange={(color) => setForm({ ...form, color })}
        />
        <Select
          label="Classification"
          options={['internal', 'confidential', 'restricted']}
          value={form.classification}
          onChange={(classification) => setForm({ ...form, classification })}
        />
        <Select
          label="Privacy"
          options={['public', 'private']}
          value={form.visibility}
          onChange={(visibility) =>
            setForm({ ...form, visibility: visibility as 'public' | 'private' })
          }
        />
      </div>
      <button
        className="mt-6 inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 font-semibold text-primary-foreground"
        onClick={() => void save()}
        type="button"
      >
        <Save className="size-4" /> {saved ? 'Settings saved' : 'Save settings'}
      </button>
    </Panel>
  )
}

function TeamInformation({ data }: { data: TeamOverview }) {
  return (
    <aside className="h-fit rounded-2xl border bg-card p-5 shadow-sm xl:sticky xl:top-20">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Team health</h2>
        <ShieldCheck className="size-5 text-primary" />
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-emerald-500"
          style={{ width: `${data.health_score}%` }}
        />
      </div>
      <p className="mt-2 text-2xl font-semibold">{data.health_score}%</p>
      <div className="mt-5 grid grid-cols-2 gap-3">
        <Mini label="Members" value={data.member_count} />
        <Mini label="Active" value={data.active_member_count} />
        <Mini label="Channels" value={data.channel_count} />
        <Mini label="Actions" value={data.open_action_count} />
        <Mini label="Files" value={data.file_count} />
        <Mini label="Apps" value={data.app_count} />
      </div>
      <p className="mt-5 text-xs text-muted-foreground">
        Keyboard: Alt+1 through Alt+9 switches primary Team sections.
      </p>
    </aside>
  )
}

function Panel({
  children,
  subtitle,
  title,
}: {
  children: React.ReactNode
  subtitle: string
  title: string
}) {
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      <div className="mt-5">{children}</div>
    </section>
  )
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Users
  label: string
  value: number | string
}) {
  return (
    <article className="rounded-xl border p-4">
      <Icon className="size-5 text-primary" />
      <p className="mt-3 text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </article>
  )
}

function Mini({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-muted/50 p-3 text-center">
      <p className="text-xl font-semibold">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border bg-muted/50 px-2.5 py-1 text-xs font-semibold capitalize">
      {children}
    </span>
  )
}

function Empty({
  detail,
  icon: Icon,
  title,
}: {
  detail: string
  icon: typeof Users
  title: string
}) {
  return (
    <div className="p-8 text-center">
      <Icon className="mx-auto size-8 text-muted-foreground" />
      <h3 className="mt-3 font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
    </div>
  )
}

function Input({
  label,
  onChange,
  value,
}: {
  label: string
  onChange: (value: string) => void
  value: string
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  )
}

function Select({
  label,
  onChange,
  options,
  value,
}: {
  label: string
  onChange: (value: string) => void
  options: string[]
  value: string
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <select
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 capitalize"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option || 'All roles'}
          </option>
        ))}
      </select>
    </label>
  )
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}
