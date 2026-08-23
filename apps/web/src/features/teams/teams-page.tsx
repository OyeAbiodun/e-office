import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Archive, Plus, Search, ShieldCheck, Users } from 'lucide-react'
import { useState } from 'react'

import { organizationApi } from '@/features/organizations/api'
import { teamsApi } from '@/features/teams/api'

export function TeamsPage() {
  const client = useQueryClient()
  const [search, setSearch] = useState('')
  const [scope, setScope] = useState<'active' | 'archived' | 'all'>('active')
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    name: '',
    slug: '',
    workspace_id: '',
    description: '',
    visibility: 'public',
    classification: 'internal',
    color: '#2563eb',
  })
  const teams = useQuery({
    queryKey: ['teams', search, scope],
    queryFn: () =>
      teamsApi.list({
        search: search || undefined,
        archived: scope === 'all' ? undefined : scope === 'archived',
      }),
  })
  const workspaces = useQuery({
    queryKey: ['workspaces'],
    queryFn: organizationApi.workspaces,
  })

  async function create() {
    const workspaceId = form.workspace_id || workspaces.data?.[0]?.id
    if (!form.name || !form.slug || !workspaceId) return
    await teamsApi.create({ ...form, workspace_id: workspaceId })
    setShowCreate(false)
    setForm({ ...form, name: '', slug: '', description: '' })
    await client.invalidateQueries({ queryKey: ['teams'] })
  }

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-8">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Collaboration</p>
          <h1 className="mt-1 text-3xl font-semibold">Teams</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Govern people, channels, meetings, knowledge, and apps inside each
            workspace.
          </p>
        </div>
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 font-semibold text-primary-foreground"
          onClick={() => setShowCreate((value) => !value)}
          type="button"
        >
          <Plus className="size-4" /> New team
        </button>
      </header>

      <section className="mt-6 grid gap-4 sm:grid-cols-3">
        <Metric
          label="Visible teams"
          value={teams.data?.length ?? 0}
          icon={Users}
        />
        <Metric
          label="Private teams"
          value={
            teams.data?.filter(({ visibility }) => visibility === 'private')
              .length ?? 0
          }
          icon={ShieldCheck}
        />
        <Metric
          label="Archived"
          value={
            teams.data?.filter(({ archived_at }) => archived_at).length ?? 0
          }
          icon={Archive}
        />
      </section>

      {showCreate && (
        <section className="mt-5 rounded-2xl border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">Create a collaboration team</h2>
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Input
              label="Team name"
              value={form.name}
              onChange={(name) => setForm({ ...form, name })}
            />
            <Input
              label="Slug"
              value={form.slug}
              onChange={(slug) => setForm({ ...form, slug })}
            />
            <label className="text-sm font-medium">
              Workspace
              <select
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                onChange={(event) =>
                  setForm({ ...form, workspace_id: event.target.value })
                }
                value={form.workspace_id}
              >
                <option value="">Choose workspace</option>
                {workspaces.data
                  ?.filter(({ archived_at }) => !archived_at)
                  .map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name}
                    </option>
                  ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Privacy
              <select
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                onChange={(event) =>
                  setForm({ ...form, visibility: event.target.value })
                }
                value={form.visibility}
              >
                <option value="public">Public</option>
                <option value="private">Private</option>
              </select>
            </label>
          </div>
          <button
            className="mt-5 h-11 rounded-xl bg-primary px-5 font-semibold text-primary-foreground disabled:opacity-50"
            disabled={!form.name || !form.slug}
            onClick={() => void create()}
            type="button"
          >
            Create team
          </button>
        </section>
      )}

      <section className="mt-6 overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="flex flex-col gap-3 border-b p-4 sm:flex-row">
          <label className="relative flex-1">
            <span className="sr-only">Search teams</span>
            <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
            <input
              className="h-10 w-full rounded-xl border bg-background pl-9 pr-3"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search teams"
              value={search}
            />
          </label>
          <div className="flex gap-1 rounded-xl bg-muted p-1">
            {(['active', 'archived', 'all'] as const).map((value) => (
              <button
                className={`rounded-lg px-3 py-1.5 text-sm font-medium capitalize ${
                  scope === value
                    ? 'bg-card shadow-sm'
                    : 'text-muted-foreground'
                }`}
                key={value}
                onClick={() => setScope(value)}
                type="button"
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3">
          {teams.data?.map((team) => (
            <Link
              className="group rounded-2xl border bg-background p-5 transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
              key={team.id}
              params={{ teamId: team.id }}
              to="/teams/$teamId"
            >
              <div className="flex items-start justify-between">
                <span
                  className="grid size-12 place-items-center rounded-2xl text-white"
                  style={{ background: team.color }}
                >
                  <Users className="size-6" />
                </span>
                <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-semibold capitalize">
                  {team.archived_at ? 'archived' : team.visibility}
                </span>
              </div>
              <h2 className="mt-5 font-semibold group-hover:text-primary">
                {team.name}
              </h2>
              <p className="mt-1 line-clamp-2 min-h-10 text-sm text-muted-foreground">
                {team.description ?? 'A focused collaboration space.'}
              </p>
              <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {team.classification}
              </p>
            </Link>
          ))}
        </div>
        {!teams.isLoading && teams.data?.length === 0 && (
          <div className="p-12 text-center">
            <Users className="mx-auto size-8 text-muted-foreground" />
            <h2 className="mt-3 font-semibold">No matching teams</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Adjust the search or lifecycle filter.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Users
  label: string
  value: number
}) {
  return (
    <article className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <Icon className="size-5 text-primary" />
      </div>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
    </article>
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
    <label className="text-sm font-medium">
      {label}
      <input
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  )
}
