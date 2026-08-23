import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import {
  Activity,
  AppWindow,
  Archive,
  ArrowLeft,
  Building2,
  CalendarDays,
  FileText,
  Hash,
  MessagesSquare,
  RotateCcw,
  Save,
  ShieldCheck,
  Users,
  Video,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { organizationApi } from '@/features/organizations/api'

type Section =
  'overview' | 'members' | 'governance' | 'integrations' | 'activity'

export function WorkspaceDetailPage() {
  const { workspaceId } = useParams({ strict: false }) as {
    workspaceId: string
  }
  const client = useQueryClient()
  const [section, setSection] = useState<Section>('overview')
  const overview = useQuery({
    queryKey: ['workspace-overview', workspaceId],
    queryFn: () => organizationApi.workspaceOverview(workspaceId),
  })
  const members = useQuery({
    queryKey: ['workspace-members', workspaceId],
    queryFn: () => organizationApi.workspaceMembers(workspaceId),
  })
  const integrations = useQuery({
    queryKey: ['workspace-integrations', workspaceId],
    queryFn: () => organizationApi.workspaceIntegrations(workspaceId),
  })

  if (overview.isLoading)
    return (
      <div className="mx-auto max-w-7xl space-y-5 p-8">
        <div className="h-36 animate-pulse rounded-3xl bg-muted" />
        <div className="h-72 animate-pulse rounded-3xl bg-muted" />
      </div>
    )
  if (!overview.data)
    return (
      <div className="grid min-h-[60vh] place-items-center p-8" role="alert">
        <div className="text-center">
          <h1 className="text-xl font-semibold">Workspace unavailable</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            It may have been removed or you may not have access.
          </p>
          <Link
            className="mt-4 inline-block text-sm font-semibold text-primary"
            to="/workspaces"
          >
            Return to workspaces
          </Link>
        </div>
      </div>
    )

  const workspace = overview.data.workspace
  async function lifecycle() {
    if (workspace.archived_at)
      await organizationApi.restoreWorkspace(workspaceId)
    else await organizationApi.archiveWorkspace(workspaceId)
    await client.invalidateQueries({
      queryKey: ['workspace-overview', workspaceId],
    })
  }

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-8">
      <Link
        className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground"
        to="/workspaces"
      >
        <ArrowLeft className="size-4" /> All workspaces
      </Link>
      <header className="mt-4 overflow-hidden rounded-3xl border bg-card shadow-sm">
        <div
          className="h-2"
          style={{ background: workspace.brand_color ?? '#2563eb' }}
        />
        <div className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
          <span
            className="grid size-16 place-items-center rounded-2xl text-white shadow-lg"
            style={{ background: workspace.brand_color ?? '#2563eb' }}
          >
            <Building2 className="size-8" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold sm:text-3xl">
                {workspace.name}
              </h1>
              <Badge>{workspace.archived_at ? 'Archived' : 'Active'}</Badge>
              <Badge>{workspace.classification}</Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {workspace.description ?? 'No workspace description'} ·{' '}
              {workspace.visibility} ·{' '}
              {workspace.data_region ?? 'Organization data region'}
            </p>
          </div>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-sm font-semibold hover:bg-muted"
            onClick={() => void lifecycle()}
            type="button"
          >
            {workspace.archived_at ? (
              <RotateCcw className="size-4" />
            ) : (
              <Archive className="size-4" />
            )}
            {workspace.archived_at ? 'Restore workspace' : 'Archive workspace'}
          </button>
        </div>
      </header>

      <nav
        aria-label="Workspace administration"
        className="mt-5 flex gap-1 overflow-x-auto rounded-2xl border bg-card p-1.5"
      >
        {(
          [
            ['overview', 'Overview'],
            ['members', 'Members & administrators'],
            ['governance', 'Settings & policies'],
            ['integrations', 'Apps & integrations'],
            ['activity', 'Activity & audit'],
          ] as Array<[Section, string]>
        ).map(([id, label]) => (
          <button
            aria-current={section === id ? 'page' : undefined}
            className={`shrink-0 rounded-xl px-3 py-2 text-sm font-medium ${
              section === id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
            key={id}
            onClick={() => setSection(id)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="mt-5">
        {section === 'overview' && <Overview data={overview.data} />}
        {section === 'members' && <Members data={members.data ?? []} />}
        {section === 'governance' && <Governance workspace={workspace} />}
        {section === 'integrations' && (
          <Integrations
            data={integrations.data ?? []}
            workspaceId={workspaceId}
          />
        )}
        {section === 'activity' && <ActivityAudit data={overview.data} />}
      </main>
    </div>
  )
}

function Overview({
  data,
}: {
  data: Awaited<ReturnType<typeof organizationApi.workspaceOverview>>
}) {
  const metrics = [
    ['Teams', data.team_count, Users],
    ['Members', data.member_count, Users],
    ['Channels', data.channel_count, Hash],
    ['Meetings', data.meeting_count, Video],
    ['Calendars', data.calendar_count, CalendarDays],
    ['Files', data.file_count, FileText],
    ['Apps', data.app_count, AppWindow],
    ['Storage', formatBytes(data.storage_bytes), MessagesSquare],
  ] as const
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map(([label, value, Icon]) => (
          <article
            className="rounded-2xl border bg-card p-5 shadow-sm"
            key={label}
          >
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-muted-foreground">
                {label}
              </p>
              <Icon className="size-5 text-primary" />
            </div>
            <p className="mt-4 text-3xl font-semibold">{value}</p>
          </article>
        ))}
      </section>
      <section className="rounded-2xl border bg-card p-5 shadow-sm">
        <h2 className="font-semibold">Workspace health</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Live operational footprint across collaboration services.
        </p>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <Health label="Administrators" value={data.administrator_count} />
          <Health label="Recent activity" value={data.recent_activity.length} />
          <Health label="Audit records" value={data.audit_history.length} />
        </div>
      </section>
    </div>
  )
}

function Members({
  data,
}: {
  data: Awaited<ReturnType<typeof organizationApi.workspaceMembers>>
}) {
  return (
    <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      <header className="border-b p-5">
        <h2 className="font-semibold">Workspace access</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {data.length} people have explicit access. Owners and administrators
          can govern this workspace.
        </p>
      </header>
      <div className="divide-y">
        {data.map((member) => (
          <div className="flex items-center gap-4 p-5" key={member.id}>
            <span className="grid size-11 place-items-center rounded-full bg-primary/10 font-semibold text-primary">
              {member.display_name.charAt(0)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{member.display_name}</p>
              <p className="truncate text-sm text-muted-foreground">
                {member.email}
              </p>
            </div>
            <Badge>{member.role}</Badge>
          </div>
        ))}
      </div>
    </section>
  )
}

function Governance({
  workspace,
}: {
  workspace: Awaited<ReturnType<typeof organizationApi.workspace>>
}) {
  const client = useQueryClient()
  const [form, setForm] = useState({
    name: workspace.name,
    description: workspace.description ?? '',
    brand_color: workspace.brand_color ?? '#2563eb',
    classification: workspace.classification,
    visibility: workspace.visibility,
    data_region: workspace.data_region ?? '',
  })
  const [saved, setSaved] = useState(false)
  useEffect(() => setSaved(false), [form])
  async function save() {
    await organizationApi.updateWorkspace(workspace.id, {
      ...form,
      data_region: form.data_region || null,
      settings: {
        working_hours: {},
        calendar_preferences: {},
        meeting_defaults: {},
        chat_defaults: {},
        governance: { external_sharing: false, guest_access: false },
        retention: { policy: 'organization_default' },
        permissions: { creation: 'administrators' },
        integrations: {},
      },
    })
    setSaved(true)
    await client.invalidateQueries({
      queryKey: ['workspace-overview', workspace.id],
    })
  }
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold">Branding, governance, and policies</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Workspace controls inherit organization defaults unless explicitly
            configured.
          </p>
        </div>
        <ShieldCheck className="size-6 text-primary" />
      </div>
      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <Input
          label="Workspace name"
          value={form.name}
          onChange={(name) => setForm({ ...form, name })}
        />
        <Input
          label="Brand color"
          type="color"
          value={form.brand_color}
          onChange={(brand_color) => setForm({ ...form, brand_color })}
        />
        <Input
          label="Description"
          value={form.description}
          onChange={(description) => setForm({ ...form, description })}
        />
        <Input
          label="Data region"
          value={form.data_region}
          onChange={(data_region) => setForm({ ...form, data_region })}
        />
        <Select
          label="Classification"
          options={['internal', 'confidential', 'restricted']}
          value={form.classification}
          onChange={(classification) => setForm({ ...form, classification })}
        />
        <Select
          label="Visibility"
          options={['members', 'private', 'organization']}
          value={form.visibility}
          onChange={(visibility) => setForm({ ...form, visibility })}
        />
      </div>
      <button
        className="mt-6 inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 font-semibold text-primary-foreground"
        onClick={() => void save()}
        type="button"
      >
        <Save className="size-4" /> {saved ? 'Settings saved' : 'Save settings'}
      </button>
    </section>
  )
}

function Integrations({
  data,
  workspaceId,
}: {
  data: Awaited<ReturnType<typeof organizationApi.workspaceIntegrations>>
  workspaceId: string
}) {
  const client = useQueryClient()
  async function connect(provider: string, displayName: string) {
    await organizationApi.updateWorkspaceIntegration(workspaceId, {
      provider,
      display_name: displayName,
      enabled: true,
      configuration: {},
    })
    await client.invalidateQueries({
      queryKey: ['workspace-integrations', workspaceId],
    })
    await client.invalidateQueries({
      queryKey: ['workspace-overview', workspaceId],
    })
  }
  const catalog: Array<[string, string]> = [
    ['sharepoint', 'SharePoint'],
    ['microsoft-365', 'Microsoft 365'],
    ['power-bi', 'Power BI'],
  ]
  return (
    <section className="grid gap-4 md:grid-cols-3">
      {catalog.map(([provider, name]) => {
        const installed = data.find((item) => item.provider === provider)
        return (
          <article
            className="rounded-2xl border bg-card p-5 shadow-sm"
            key={provider}
          >
            <span className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
              <AppWindow className="size-5" />
            </span>
            <h2 className="mt-4 font-semibold">{name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Workspace-scoped connection with organization policy enforcement.
            </p>
            <button
              className="mt-5 h-10 rounded-xl border px-4 text-sm font-semibold disabled:opacity-60"
              disabled={Boolean(installed?.enabled)}
              onClick={() => void connect(provider, name)}
              type="button"
            >
              {installed?.enabled ? 'Connected' : 'Connect'}
            </button>
          </article>
        )
      })}
    </section>
  )
}

function ActivityAudit({
  data,
}: {
  data: Awaited<ReturnType<typeof organizationApi.workspaceOverview>>
}) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Timeline
        empty="No workspace activity has been recorded."
        items={data.recent_activity.map((item) => ({
          id: item.id,
          label: item.event_type,
          time: item.occurred_at,
        }))}
        title="Workspace activity"
      />
      <Timeline
        empty="No compliance audit records have been recorded."
        items={data.audit_history.map((item) => ({
          id: item.id,
          label: item.action,
          time: item.created_at,
        }))}
        title="Immutable audit history"
      />
    </div>
  )
}

function Timeline({
  empty,
  items,
  title,
}: {
  empty: string
  items: Array<{ id: string; label: string; time: string }>
  title: string
}) {
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm">
      <h2 className="font-semibold">{title}</h2>
      <div className="mt-4 space-y-4">
        {items.map((item) => (
          <div className="flex gap-3" key={item.id}>
            <span className="mt-0.5 grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
              <Activity className="size-4" />
            </span>
            <div>
              <p className="text-sm font-medium">
                {item.label.replaceAll('.', ' ')}
              </p>
              <p className="text-xs text-muted-foreground">
                {new Date(item.time).toLocaleString()}
              </p>
            </div>
          </div>
        ))}
        {!items.length && (
          <p className="text-sm text-muted-foreground">{empty}</p>
        )}
      </div>
    </section>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border bg-muted/40 px-2.5 py-1 text-xs font-semibold capitalize">
      {children}
    </span>
  )
}

function Health({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-muted/50 p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  )
}

function Input({
  label,
  onChange,
  type = 'text',
  value,
}: {
  label: string
  onChange: (value: string) => void
  type?: string
  value: string
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <input
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
        onChange={(event) => onChange(event.target.value)}
        type={type}
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
    <label className="text-sm font-medium">
      {label}
      <select
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 capitalize"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option}>{option}</option>
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
