import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Activity,
  Building2,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileClock,
  Globe2,
  Pencil,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Trash2,
  UserCog,
  Users,
  Workflow,
} from 'lucide-react'
import { useState } from 'react'

import {
  organizationApi,
  type DepartmentDetail,
  type OrganizationUnit,
} from '@/features/organizations/api'

type Section =
  'overview' | 'structure' | 'policies' | 'administrators' | 'audit'

const sections: Array<{ id: Section; label: string; icon: typeof Building2 }> =
  [
    { id: 'overview', label: 'Overview', icon: Building2 },
    { id: 'structure', label: 'Structure', icon: Workflow },
    { id: 'policies', label: 'Policies', icon: ShieldCheck },
    { id: 'administrators', label: 'Administrators', icon: UserCog },
    { id: 'audit', label: 'Audit history', icon: FileClock },
  ]

export function OrganizationPage() {
  const [section, setSection] = useState<Section>('overview')
  const overview = useQuery({
    queryKey: ['organization-overview'],
    queryFn: organizationApi.organizationOverview,
  })
  const units = useQuery({
    queryKey: ['organization-units'],
    queryFn: organizationApi.organizationUnits,
  })
  const policies = useQuery({
    queryKey: ['organization-policies'],
    queryFn: organizationApi.organizationPolicies,
  })

  if (overview.isLoading)
    return (
      <div
        className="mx-auto max-w-7xl space-y-5 p-5 sm:p-8"
        aria-label="Loading organization"
      >
        <div className="h-32 animate-pulse rounded-3xl bg-muted" />
        <div className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div
              className="h-28 animate-pulse rounded-2xl bg-muted"
              key={item}
            />
          ))}
        </div>
      </div>
    )

  if (overview.isError || !overview.data)
    return (
      <div
        className="grid min-h-[60vh] place-items-center p-8 text-center"
        role="alert"
      >
        <div>
          <h1 className="text-xl font-semibold">
            Organization administration is unavailable
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Your data remains safe. Retry when the connection is restored.
          </p>
          <button
            className="mt-4 rounded-xl bg-primary px-4 py-2 font-semibold text-primary-foreground"
            onClick={() => void overview.refetch()}
            type="button"
          >
            Retry
          </button>
        </div>
      </div>
    )

  const organization = overview.data.organization
  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-8">
      <header className="overflow-hidden rounded-3xl border bg-card shadow-sm">
        <div
          className="h-2"
          style={{ backgroundColor: organization.brand_color }}
        />
        <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:p-7">
          <span
            className="grid size-16 shrink-0 place-items-center rounded-2xl text-white shadow-lg"
            style={{ backgroundColor: organization.brand_color }}
          >
            <Building2 className="size-8" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-2xl font-semibold sm:text-3xl">
                {organization.name}
              </h1>
              <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold capitalize text-emerald-700 dark:text-emerald-300">
                {organization.status}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {organization.slug} · {organization.timezone} ·{' '}
              {organization.default_language.toUpperCase()}
            </p>
          </div>
          <Link
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-sm font-semibold hover:bg-muted"
            to="/organization/settings"
          >
            <Settings className="size-4" />
            Organization settings
          </Link>
        </div>
      </header>

      <nav
        aria-label="Organization administration"
        className="mt-5 flex gap-1 overflow-x-auto rounded-2xl border bg-card p-1.5"
      >
        {sections.map(({ id, label, icon: Icon }) => (
          <button
            aria-current={section === id ? 'page' : undefined}
            className={`flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium ${
              section === id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
            key={id}
            onClick={() => setSection(id)}
            type="button"
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </nav>

      <main className="mt-5">
        {section === 'overview' && <Overview overview={overview.data} />}
        {section === 'structure' && <Structure units={units.data ?? []} />}
        {section === 'policies' && <Policies policies={policies.data ?? {}} />}
        {section === 'administrators' && (
          <Administrators administrators={overview.data.administrators} />
        )}
        {section === 'audit' && (
          <AuditHistory
            activity={overview.data.recent_activity}
            audits={overview.data.audit_history}
          />
        )}
      </main>
    </div>
  )
}

function Overview({
  overview,
}: {
  overview: Awaited<ReturnType<typeof organizationApi.organizationOverview>>
}) {
  const metrics = [
    [
      'Members',
      overview.member_count,
      `${overview.active_member_count} active`,
      Users,
    ],
    [
      'Workspaces',
      overview.workspace_count,
      'Collaborative environments',
      Globe2,
    ],
    ['Teams', overview.team_count, 'Cross-functional groups', Workflow],
    [
      'Invitations',
      overview.pending_invitation_count,
      'Awaiting response',
      ChevronRight,
    ],
  ] as const
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(([label, value, detail, Icon]) => (
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
            <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
          </article>
        ))}
      </section>
      <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        <section className="rounded-2xl border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">Organization structure</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Departments and operating locations across the tenant.
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <StructureMetric
              label="Departments"
              value={overview.department_count}
            />
            <StructureMetric label="Branches" value={overview.branch_count} />
            <StructureMetric
              label="Locations"
              value={overview.location_count}
            />
          </div>
        </section>
        <section className="rounded-2xl border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">Recent administration activity</h2>
          <div className="mt-4 space-y-3">
            {overview.recent_activity.slice(0, 4).map((item) => (
              <div className="flex gap-3" key={item.id}>
                <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
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
            {overview.recent_activity.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Administration activity will appear here.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

function Structure({ units }: { units: OrganizationUnit[] }) {
  const client = useQueryClient()
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [description, setDescription] = useState('')
  const [type, setType] = useState<OrganizationUnit['unit_type']>('department')
  const [managerId, setManagerId] = useState('')
  const [unitStatus, setUnitStatus] = useState<'active' | 'inactive'>('active')
  const [editing, setEditing] = useState<OrganizationUnit | null>(null)
  const [selectedDepartment, setSelectedDepartment] = useState<string | null>(
    null,
  )
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'active' | 'inactive' | ''>(
    '',
  )
  const [sort, setSort] = useState<'name' | 'created_at'>('name')
  const [direction, setDirection] = useState<'asc' | 'desc'>('asc')
  const [page, setPage] = useState(1)
  const [saving, setSaving] = useState(false)
  const members = useQuery({
    queryKey: ['organization-members'],
    queryFn: organizationApi.members,
  })
  const departments = useQuery({
    queryKey: [
      'organization-departments',
      search,
      statusFilter,
      sort,
      direction,
      page,
    ],
    queryFn: () =>
      organizationApi.departments({
        search,
        status: statusFilter || undefined,
        sort,
        direction,
        page,
        page_size: 10,
      }),
  })
  const detail = useQuery({
    queryKey: ['department-detail', selectedDepartment],
    queryFn: () => organizationApi.departmentDetail(selectedDepartment!),
    enabled: Boolean(selectedDepartment),
  })
  const resetForm = () => {
    setName('')
    setCode('')
    setDescription('')
    setType('department')
    setManagerId('')
    setUnitStatus('active')
    setEditing(null)
  }
  const edit = (unit: OrganizationUnit) => {
    setEditing(unit)
    setName(unit.name)
    setCode(unit.code ?? '')
    setDescription(unit.description ?? '')
    setType(unit.unit_type)
    setManagerId(unit.manager_id ?? '')
    setUnitStatus(unit.status)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const save = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      const body = {
        name: name.trim(),
        code: code.trim() || null,
        description: description.trim() || null,
        unit_type: type,
        manager_id: managerId || null,
        status: unitStatus,
        address: {},
        working_hours: {},
      }
      if (editing)
        await organizationApi.updateOrganizationUnit(editing.id, body)
      else await organizationApi.createOrganizationUnit(body)
      resetForm()
      await Promise.all([
        client.invalidateQueries({ queryKey: ['organization-units'] }),
        client.invalidateQueries({ queryKey: ['organization-overview'] }),
        client.invalidateQueries({ queryKey: ['organization-departments'] }),
        client.invalidateQueries({ queryKey: ['department-detail'] }),
      ])
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
      <section className="rounded-2xl border bg-card p-5 shadow-sm">
        <h2 className="font-semibold">
          {editing ? `Edit ${editing.name}` : 'Add organization unit'}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Model a department, branch, or physical location.
        </p>
        <div className="mt-5 space-y-4">
          <label className="block text-sm font-medium">
            Unit type
            <select
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              onChange={(event) =>
                setType(event.target.value as OrganizationUnit['unit_type'])
              }
              value={type}
            >
              <option value="department">Department</option>
              <option value="branch">Branch</option>
              <option value="location">Location</option>
            </select>
          </label>
          <label className="block text-sm font-medium">
            Name
            <input
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              onChange={(event) => setName(event.target.value)}
              placeholder="Product Engineering"
              value={name}
            />
          </label>
          <label className="block text-sm font-medium">
            Code
            <input
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              onChange={(event) => setCode(event.target.value)}
              placeholder="ENG"
              value={code}
            />
          </label>
          <label className="block text-sm font-medium">
            Description
            <textarea
              className="mt-2 min-h-20 w-full rounded-xl border bg-background px-3 py-2"
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Purpose and scope for this unit"
              value={description}
            />
          </label>
          <label className="block text-sm font-medium">
            Department manager
            <select
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              onChange={(event) => setManagerId(event.target.value)}
              value={managerId}
            >
              <option value="">Assign later</option>
              {members.data?.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium">
            Lifecycle state
            <select
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              onChange={(event) =>
                setUnitStatus(event.target.value as 'active' | 'inactive')
              }
              value={unitStatus}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
          <div className="flex gap-2">
            {editing && (
              <button
                className="h-11 rounded-xl border px-4 text-sm font-semibold"
                onClick={resetForm}
                type="button"
              >
                Cancel
              </button>
            )}
            <button
              className="flex h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-primary font-semibold text-primary-foreground disabled:opacity-50"
              disabled={saving || !name.trim()}
              onClick={() => void save()}
              type="button"
            >
              <Plus className="size-4" />
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Add unit'}
            </button>
          </div>
        </div>
      </section>
      <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
        <header className="border-b p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold">Department directory</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {departments.data?.total ?? 0} departments · server-filtered
              </p>
            </div>
            <span className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
              {units.filter((unit) => unit.unit_type !== 'department').length}{' '}
              other units
            </span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" />
              <input
                aria-label="Search departments"
                className="h-10 w-full rounded-xl border bg-background pl-9 pr-3 text-sm"
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPage(1)
                }}
                placeholder="Search name or code"
                value={search}
              />
            </label>
            <select
              aria-label="Filter department status"
              className="h-10 rounded-xl border bg-background px-3 text-sm"
              onChange={(event) => {
                setStatusFilter(
                  event.target.value as 'active' | 'inactive' | '',
                )
                setPage(1)
              }}
              value={statusFilter}
            >
              <option value="">All states</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            <select
              aria-label="Sort departments"
              className="h-10 rounded-xl border bg-background px-3 text-sm"
              onChange={(event) => {
                setSort(event.target.value as 'name' | 'created_at')
                setPage(1)
              }}
              value={sort}
            >
              <option value="name">Name</option>
              <option value="created_at">Recently created</option>
            </select>
            <button
              aria-label="Reverse department sort"
              className="h-10 rounded-xl border px-3 text-sm font-medium"
              onClick={() => setDirection(direction === 'asc' ? 'desc' : 'asc')}
              type="button"
            >
              {direction === 'asc' ? 'A–Z' : 'Z–A'}
            </button>
          </div>
        </header>
        <div className="divide-y">
          {departments.data?.items.map((unit) => (
            <div className="flex items-center gap-4 p-4 sm:px-5" key={unit.id}>
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                <Building2 className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{unit.name}</p>
                <p className="text-xs capitalize text-muted-foreground">
                  Department{unit.code ? ` · ${unit.code}` : ''}
                </p>
                {unit.manager_id && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Manager:{' '}
                    {members.data?.find(
                      (member) => member.id === unit.manager_id,
                    )?.display_name ?? 'Assigned member'}
                  </p>
                )}
              </div>
              <span
                className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
                  unit.status === 'active'
                    ? 'bg-emerald-500/10 text-emerald-700'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {unit.status}
              </span>
              <div className="flex items-center gap-1">
                <button
                  aria-label={`View ${unit.name}`}
                  className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
                  onClick={() => setSelectedDepartment(unit.id)}
                  type="button"
                >
                  <Eye className="size-4" />
                </button>
                <button
                  aria-label={`Edit ${unit.name}`}
                  className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
                  onClick={() => edit(unit)}
                  type="button"
                >
                  <Pencil className="size-4" />
                </button>
                <button
                  aria-label={`Archive ${unit.name}`}
                  className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-red-500/10 hover:text-red-500"
                  onClick={() =>
                    void organizationApi
                      .deleteOrganizationUnit(unit.id)
                      .then(async () => {
                        await Promise.all([
                          client.invalidateQueries({
                            queryKey: ['organization-units'],
                          }),
                          client.invalidateQueries({
                            queryKey: ['organization-overview'],
                          }),
                          client.invalidateQueries({
                            queryKey: ['organization-departments'],
                          }),
                          client.invalidateQueries({
                            queryKey: ['department-detail'],
                          }),
                        ])
                      })
                  }
                  type="button"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            </div>
          ))}
          {departments.isLoading && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              Loading departments…
            </div>
          )}
          {!departments.isLoading && departments.data?.items.length === 0 && (
            <div className="p-10 text-center">
              <Building2 className="mx-auto size-8 text-muted-foreground" />
              <h3 className="mt-3 font-semibold">No departments found</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Adjust the filters or add a department to get started.
              </p>
            </div>
          )}
        </div>
        <footer className="flex items-center justify-between border-t p-4 text-sm text-muted-foreground">
          <span>
            Page {departments.data?.page ?? 1} of{' '}
            {departments.data?.total_pages ?? 1}
          </span>
          <div className="flex gap-2">
            <button
              aria-label="Previous department page"
              className="grid size-9 place-items-center rounded-lg border disabled:opacity-40"
              disabled={!departments.data || departments.data.page <= 1}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              type="button"
            >
              <ChevronLeft className="size-4" />
            </button>
            <button
              aria-label="Next department page"
              className="grid size-9 place-items-center rounded-lg border disabled:opacity-40"
              disabled={
                !departments.data ||
                departments.data.page >= departments.data.total_pages
              }
              onClick={() => setPage((current) => current + 1)}
              type="button"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </footer>
      </section>
      {selectedDepartment && (
        <DepartmentPanel
          detail={detail.data}
          loading={detail.isLoading}
          onClose={() => setSelectedDepartment(null)}
        />
      )}
    </div>
  )
}

function DepartmentPanel({
  detail,
  loading,
  onClose,
}: {
  detail: DepartmentDetail | undefined
  loading: boolean
  onClose: () => void
}) {
  return (
    <section
      aria-label="Department details"
      className="rounded-2xl border bg-card p-5 shadow-sm xl:col-span-2"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-primary">
            Department overview
          </p>
          <h2 className="mt-1 text-xl font-semibold">
            {detail?.name ?? 'Loading department…'}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {detail?.description || 'No description has been added.'}
          </p>
        </div>
        <button
          className="rounded-xl border px-3 py-2 text-sm font-medium"
          onClick={onClose}
          type="button"
        >
          Close
        </button>
      </div>
      {loading ? (
        <p className="mt-5 text-sm text-muted-foreground">
          Loading live metrics…
        </p>
      ) : detail ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <StructureMetric label="Employees" value={detail.employee_count} />
          <StructureMetric label="Teams" value={detail.team_count} />
          <div className="rounded-xl bg-muted/45 p-4">
            <p className="text-sm font-semibold">
              {detail.manager_name ?? 'Unassigned'}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Department manager
            </p>
          </div>
        </div>
      ) : (
        <p className="mt-5 text-sm text-destructive">
          Department details could not be loaded.
        </p>
      )}
    </section>
  )
}

function Policies({
  policies,
}: {
  policies: Record<string, Record<string, unknown>>
}) {
  const client = useQueryClient()
  const labels: Record<string, string> = {
    security: 'Security policies',
    meeting: 'Meeting policies',
    chat: 'Chat policies',
    storage: 'Storage policies',
    ai: 'AI policies',
    notification: 'Notification policies',
  }
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Object.entries(policies).map(([category, values]) => {
        const enabled = values.enabled !== false
        return (
          <article
            className="rounded-2xl border bg-card p-5 shadow-sm"
            key={category}
          >
            <div className="flex items-start justify-between gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
                <ShieldCheck className="size-5" />
              </span>
              <button
                aria-label={`${enabled ? 'Disable' : 'Enable'} ${labels[category]}`}
                aria-pressed={enabled}
                className={`relative h-6 w-11 rounded-full transition ${
                  enabled ? 'bg-primary' : 'bg-muted'
                }`}
                onClick={() =>
                  void organizationApi
                    .updateOrganizationPolicy(category, {
                      ...values,
                      enabled: !enabled,
                    })
                    .then(() =>
                      client.invalidateQueries({
                        queryKey: ['organization-policies'],
                      }),
                    )
                }
                type="button"
              >
                <span
                  className={`absolute top-1 size-4 rounded-full bg-white transition ${
                    enabled ? 'left-6' : 'left-1'
                  }`}
                />
              </button>
            </div>
            <h2 className="mt-4 font-semibold">
              {labels[category] ?? category}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Organization-wide defaults with auditable enforcement.
            </p>
            <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {enabled ? 'Enabled' : 'Disabled'} ·{' '}
              {String(values.enforcement ?? 'organization_default').replaceAll(
                '_',
                ' ',
              )}
            </p>
          </article>
        )
      })}
    </section>
  )
}

function Administrators({
  administrators,
}: {
  administrators: Array<{
    id: string
    display_name: string
    email: string
    role: string
  }>
}) {
  return (
    <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      <header className="border-b p-5">
        <h2 className="font-semibold">Organization administrators</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Identities with tenant-wide administrative authority.
        </p>
      </header>
      <div className="divide-y">
        {administrators.map((administrator) => (
          <div className="flex items-center gap-4 p-5" key={administrator.id}>
            <span className="grid size-11 place-items-center rounded-full bg-primary/10 font-semibold text-primary">
              {administrator.display_name.charAt(0)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">
                {administrator.display_name}
              </p>
              <p className="truncate text-sm text-muted-foreground">
                {administrator.email}
              </p>
            </div>
            <span className="rounded-full border px-3 py-1 text-xs font-semibold">
              {administrator.role}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

function AuditHistory({
  activity,
  audits,
}: {
  activity: Array<{
    id: string
    event_type: string
    subject_type: string
    occurred_at: string
  }>
  audits: Array<{
    id: string
    action: string
    resource: string
    created_at: string
  }>
}) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Timeline
        empty="No compliance audit records have been captured."
        items={audits.map((item) => ({
          id: item.id,
          title: item.action,
          detail: item.resource,
          time: item.created_at,
        }))}
        title="Immutable security audit"
      />
      <Timeline
        empty="No user activity has been captured."
        items={activity.map((item) => ({
          id: item.id,
          title: item.event_type.replaceAll('.', ' '),
          detail: item.subject_type,
          time: item.occurred_at,
        }))}
        title="Organization activity"
      />
    </div>
  )
}

function Timeline({
  title,
  empty,
  items,
}: {
  title: string
  empty: string
  items: Array<{ id: string; title: string; detail: string; time: string }>
}) {
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm">
      <h2 className="font-semibold">{title}</h2>
      <div className="mt-5 space-y-4">
        {items.map((item) => (
          <div className="flex gap-3" key={item.id}>
            <span className="mt-1 size-2 shrink-0 rounded-full bg-primary" />
            <div>
              <p className="text-sm font-medium capitalize">{item.title}</p>
              <p className="text-xs capitalize text-muted-foreground">
                {item.detail} · {new Date(item.time).toLocaleString()}
              </p>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-sm text-muted-foreground">{empty}</p>
        )}
      </div>
    </section>
  )
}

function StructureMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-muted/45 p-4">
      <p className="text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  )
}
