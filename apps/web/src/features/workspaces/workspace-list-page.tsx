import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Archive,
  Boxes,
  Building2,
  CheckSquare,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { organizationApi } from '@/features/organizations/api'

export function WorkspaceListPage() {
  const client = useQueryClient()
  const [search, setSearch] = useState('')
  const [scope, setScope] = useState<'active' | 'archived' | 'all'>('active')
  const [selected, setSelected] = useState<string[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: '',
    slug: '',
    description: '',
    classification: 'internal',
    visibility: 'members',
  })
  const workspaces = useQuery({
    queryKey: ['workspaces', search, scope],
    queryFn: () =>
      organizationApi.searchWorkspaces({
        search: search || undefined,
        archived: scope === 'all' ? undefined : scope === 'archived',
      }),
  })
  const templates = useQuery({
    queryKey: ['workspace-templates'],
    queryFn: organizationApi.workspaceTemplates,
  })
  const allSelected = useMemo(
    () =>
      Boolean(workspaces.data?.length) &&
      workspaces.data?.every((workspace) => selected.includes(workspace.id)),
    [selected, workspaces.data],
  )

  async function create() {
    if (!form.name.trim() || !form.slug.trim()) return
    setSaving(true)
    try {
      await organizationApi.createWorkspace(form)
      setForm({
        name: '',
        slug: '',
        description: '',
        classification: 'internal',
        visibility: 'members',
      })
      setShowForm(false)
      await client.invalidateQueries({ queryKey: ['workspaces'] })
    } finally {
      setSaving(false)
    }
  }

  async function bulk(action: 'archive' | 'restore') {
    if (!selected.length) return
    await organizationApi.bulkWorkspaceLifecycle(selected, action)
    setSelected([])
    await client.invalidateQueries({ queryKey: ['workspaces'] })
  }

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-8">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Administration</p>
          <h1 className="mt-1 text-3xl font-semibold">Workspaces</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Govern collaboration boundaries, access, data residency, and
            lifecycle across your organization.
          </p>
        </div>
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 font-semibold text-primary-foreground shadow-sm"
          onClick={() => setShowForm((visible) => !visible)}
          type="button"
        >
          <Plus className="size-4" />
          New workspace
        </button>
      </header>

      <section className="mt-6 grid gap-4 sm:grid-cols-3">
        <Summary
          icon={Building2}
          label="Visible workspaces"
          value={workspaces.data?.length ?? 0}
        />
        <Summary
          icon={ShieldCheck}
          label="Governance templates"
          value={templates.data?.length ?? 0}
        />
        <Summary
          icon={Users}
          label="Selected for action"
          value={selected.length}
        />
      </section>

      {showForm && (
        <section className="mt-5 rounded-2xl border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Create a governed workspace</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Ownership is assigned to you and can be transferred later.
              </p>
            </div>
            <Boxes className="size-6 text-primary" />
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <Field label="Name">
              <input
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value })
                }
                placeholder="Finance Operations"
                value={form.name}
              />
            </Field>
            <Field label="Slug">
              <input
                onChange={(event) =>
                  setForm({ ...form, slug: event.target.value })
                }
                placeholder="finance-operations"
                value={form.slug}
              />
            </Field>
            <Field label="Classification">
              <select
                onChange={(event) =>
                  setForm({ ...form, classification: event.target.value })
                }
                value={form.classification}
              >
                <option value="internal">Internal</option>
                <option value="confidential">Confidential</option>
                <option value="restricted">Restricted</option>
              </select>
            </Field>
            <Field label="Visibility">
              <select
                onChange={(event) =>
                  setForm({ ...form, visibility: event.target.value })
                }
                value={form.visibility}
              >
                <option value="members">Members</option>
                <option value="private">Private</option>
                <option value="organization">Organization</option>
              </select>
            </Field>
            <button
              className="mt-6 h-11 rounded-xl bg-primary px-5 font-semibold text-primary-foreground disabled:opacity-50"
              disabled={saving || !form.name || !form.slug}
              onClick={() => void create()}
              type="button"
            >
              {saving ? 'Creating…' : 'Create workspace'}
            </button>
          </div>
        </section>
      )}

      <section className="mt-6 overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="flex flex-col gap-3 border-b p-4 lg:flex-row lg:items-center">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Search workspaces</span>
            <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
            <input
              className="h-10 w-full rounded-xl border bg-background pl-9 pr-3"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by workspace name or slug"
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
          {selected.length > 0 && (
            <div className="flex gap-2">
              <button
                className="inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-semibold"
                onClick={() => void bulk('archive')}
                type="button"
              >
                <Archive className="size-4" /> Archive
              </button>
              <button
                className="inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-semibold"
                onClick={() => void bulk('restore')}
                type="button"
              >
                <RotateCcw className="size-4" /> Restore
              </button>
            </div>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="w-12 p-4">
                  <input
                    aria-label="Select all workspaces"
                    checked={allSelected}
                    onChange={() =>
                      setSelected(
                        allSelected
                          ? []
                          : (workspaces.data?.map(({ id }) => id) ?? []),
                      )
                    }
                    type="checkbox"
                  />
                </th>
                <th className="p-4">Workspace</th>
                <th className="p-4">Classification</th>
                <th className="p-4">Visibility</th>
                <th className="p-4">Region</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {workspaces.data?.map((workspace) => (
                <tr className="hover:bg-muted/30" key={workspace.id}>
                  <td className="p-4">
                    <input
                      aria-label={`Select ${workspace.name}`}
                      checked={selected.includes(workspace.id)}
                      onChange={() =>
                        setSelected((current) =>
                          current.includes(workspace.id)
                            ? current.filter((id) => id !== workspace.id)
                            : [...current, workspace.id],
                        )
                      }
                      type="checkbox"
                    />
                  </td>
                  <td className="p-4">
                    <Link
                      className="flex items-center gap-3 font-semibold hover:text-primary"
                      params={{ workspaceId: workspace.id }}
                      to="/workspaces/$workspaceId"
                    >
                      <span
                        className="grid size-10 place-items-center rounded-xl text-white"
                        style={{
                          backgroundColor: workspace.brand_color ?? '#2563eb',
                        }}
                      >
                        <Building2 className="size-5" />
                      </span>
                      <span>
                        {workspace.name}
                        <span className="block text-xs font-normal text-muted-foreground">
                          {workspace.slug}
                        </span>
                      </span>
                    </Link>
                  </td>
                  <td className="p-4 capitalize">{workspace.classification}</td>
                  <td className="p-4 capitalize">{workspace.visibility}</td>
                  <td className="p-4">
                    {workspace.data_region ?? 'Inherited'}
                  </td>
                  <td className="p-4">
                    <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
                      {workspace.archived_at ? 'Archived' : 'Active'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!workspaces.isLoading && workspaces.data?.length === 0 && (
          <div className="p-12 text-center">
            <CheckSquare className="mx-auto size-8 text-muted-foreground" />
            <h2 className="mt-3 font-semibold">No matching workspaces</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Adjust the search or lifecycle filter.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}

function Summary({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Building2
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

function Field({
  children,
  label,
}: {
  children: React.ReactElement<{ className?: string }>
  label: string
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <span className="[&>*]:mt-2 [&>*]:h-11 [&>*]:w-full [&>*]:rounded-xl [&>*]:border [&>*]:bg-background [&>*]:px-3">
        {children}
      </span>
    </label>
  )
}
