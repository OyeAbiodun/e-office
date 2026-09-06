import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  History,
  KeyRound,
  Plus,
  Search,
  ShieldCheck,
  UserRoundCog,
  Users,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { useConfirmation } from '@/components/feedback/confirmation'
import { organizationApi } from '@/features/organizations/api'
import { teamsApi } from '@/features/teams/api'
import {
  type ManagedUser,
  type UserInput,
  userAdminApi,
} from '@/features/users/api'

const emptyForm: UserInput = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  alternative_phone: '',
  job_title: '',
  department: '',
  department_id: null,
  manager_id: null,
  employee_number: '',
  employment_status: 'active',
  employment_type: 'permanent',
  employment_start_date: null,
  employment_confirmation_date: null,
  effective_date: null,
  employment_change_reason: '',
  workspace_id: null,
  team_id: null,
  role_ids: [],
  send_welcome_email: true,
}

export function UserManagementPage() {
  const client = useQueryClient()
  const confirm = useConfirmation()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [roleId, setRoleId] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [employmentStatus, setEmploymentStatus] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<string[]>([])
  const [editing, setEditing] = useState<ManagedUser | 'new' | null>(null)
  const [form, setForm] = useState<UserInput>(emptyForm)
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(
    null,
  )
  const users = useQuery({
    queryKey: [
      'admin-users',
      search,
      status,
      roleId,
      departmentId,
      employmentStatus,
      page,
    ],
    queryFn: () =>
      userAdminApi.employees({
        search,
        status,
        role_id: roleId,
        department_id: departmentId,
        employment_status: employmentStatus,
        page,
        page_size: 25,
      }),
  })
  const managerCandidates = useQuery({
    queryKey: ['employee-manager-candidates'],
    queryFn: () =>
      userAdminApi.employees({
        status: 'active',
        employment_status: 'active',
        page: 1,
        page_size: 100,
      }),
  })
  const roles = useQuery({
    queryKey: ['roles'],
    queryFn: userAdminApi.roles,
  })
  const workspaces = useQuery({
    queryKey: ['workspaces'],
    queryFn: organizationApi.workspaces,
  })
  const teams = useQuery({
    queryKey: ['teams', 'user-admin'],
    queryFn: () => teamsApi.list({ archived: false }),
  })
  const units = useQuery({
    queryKey: ['organization-units'],
    queryFn: organizationApi.organizationUnits,
  })
  const history = useQuery({
    queryKey: ['employment-history', editing === 'new' ? null : editing?.id],
    queryFn: () => userAdminApi.employmentHistory((editing as ManagedUser).id),
    enabled: Boolean(editing && editing !== 'new'),
  })
  const save = useMutation({
    mutationFn: () =>
      editing === 'new'
        ? userAdminApi.create(form)
        : userAdminApi.update(editing!.id, form),
    onSuccess: async () => {
      const historyUserId = editing !== 'new' ? editing?.id : null
      setEditing(null)
      setForm(emptyForm)
      await Promise.all([
        client.invalidateQueries({ queryKey: ['admin-users'] }),
        ...(historyUserId
          ? [
              client.invalidateQueries({
                queryKey: ['employment-history', historyUserId],
              }),
            ]
          : []),
      ])
    },
  })
  const userRows = useMemo(() => users.data?.items ?? [], [users.data])
  const stats = useMemo(() => {
    const rows = userRows
    return {
      total: users.data?.total ?? 0,
      active: rows.filter((item) => item.status === 'active').length,
      disabled: rows.filter((item) => item.status === 'suspended').length,
      reset: rows.filter((item) => item.force_password_change).length,
    }
  }, [userRows, users.data?.total])

  function resetPage() {
    setPage(1)
    setSelected([])
  }

  function open(user?: ManagedUser) {
    setTemporaryPassword(null)
    setEditing(user ?? 'new')
    setForm(
      user
        ? {
            first_name: user.first_name,
            last_name: user.last_name,
            email: user.email,
            phone: user.phone ?? '',
            alternative_phone: user.alternative_phone ?? '',
            job_title: user.job_title ?? '',
            department: user.department ?? '',
            department_id: user.department_id,
            manager_id: user.manager_id,
            employee_number: user.employee_number ?? '',
            employment_status: user.employment_status,
            employment_type: user.employment_type,
            employment_start_date: user.employment_start_date,
            employment_confirmation_date: user.employment_confirmation_date,
            employment_end_date: user.employment_end_date,
            effective_date: null,
            employment_change_reason: '',
            workspace_id: user.workspace_id,
            team_id: user.team_id,
            role_ids: user.roles.map((role) => role.id),
          }
        : emptyForm,
    )
  }

  async function lifecycle(user: ManagedUser, action: string) {
    if (action === 'activate') await userAdminApi.activate(user.id)
    if (action === 'disable') await userAdminApi.disable(user.id)
    if (action === 'delete') await userAdminApi.remove(user.id)
    if (action === 'restore') await userAdminApi.restore(user.id)
    if (action === 'reset') {
      const response = await userAdminApi.resetPassword(user.id)
      setTemporaryPassword(response.temporary_password)
    }
    if (action === 'terminate') {
      const approved = await confirm({
        title: `Terminate ${user.display_name}?`,
        description:
          'This suspends the account and records an effective-dated employment history entry. It can be reversed by rehiring the employee.',
        confirmLabel: 'Terminate employee',
        tone: 'danger',
      })
      if (!approved) return
      await userAdminApi.terminate(user.id, {
        effective_date: new Date().toISOString().slice(0, 10),
        disable_account: true,
      })
    }
    if (action === 'rehire')
      await userAdminApi.rehire(user.id, {
        effective_date: new Date().toISOString().slice(0, 10),
      })
    await client.invalidateQueries({ queryKey: ['admin-users'] })
  }

  async function bulk(action: string) {
    if (!selected.length) return
    await userAdminApi.bulk(selected, action)
    setSelected([])
    await client.invalidateQueries({ queryKey: ['admin-users'] })
  }

  return (
    <div className="space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">
            User administration
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Users</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Create accounts, assign access, and keep your meeting directory
            ready.
          </p>
        </div>
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 font-semibold text-primary-foreground"
          onClick={() => open()}
          type="button"
        >
          <Plus className="size-4" /> Create user
        </button>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {(
          [
            ['Total users', stats.total, Users],
            ['Active', stats.active, CheckCircle2],
            ['Disabled', stats.disabled, UserRoundCog],
            ['Password change due', stats.reset, KeyRound],
          ] as Array<[string, number, typeof Users]>
        ).map(([label, value, Icon]) => (
          <article
            className="rounded-2xl border bg-card p-5"
            key={String(label)}
          >
            <Icon className="size-5 text-primary" />
            <p className="mt-4 text-2xl font-semibold">{String(value)}</p>
            <p className="text-sm text-muted-foreground">{String(label)}</p>
          </article>
        ))}
      </section>

      <section className="overflow-hidden rounded-2xl border bg-card">
        <div className="flex flex-col gap-3 border-b p-4 lg:flex-row">
          <label className="relative flex-1">
            <span className="sr-only">Search users</span>
            <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
            <input
              aria-label="Search users"
              className="h-10 w-full rounded-xl border bg-background pl-9 pr-3"
              onChange={(event) => {
                setSearch(event.target.value)
                resetPage()
              }}
              placeholder="Search name or email"
              value={search}
            />
          </label>
          <select
            aria-label="Filter user status"
            className="h-10 rounded-xl border bg-background px-3"
            onChange={(event) => {
              setStatus(event.target.value)
              resetPage()
            }}
            value={status}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="suspended">Disabled</option>
            <option value="invited">Invited</option>
          </select>
          <select
            aria-label="Filter user role"
            className="h-10 rounded-xl border bg-background px-3"
            onChange={(event) => {
              setRoleId(event.target.value)
              resetPage()
            }}
            value={roleId}
          >
            <option value="">All roles</option>
            {roles.data?.map((role) => (
              <option key={role.id} value={role.id}>
                {role.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter employee department"
            className="h-10 rounded-xl border bg-background px-3"
            onChange={(event) => {
              setDepartmentId(event.target.value)
              resetPage()
            }}
            value={departmentId}
          >
            <option value="">All departments</option>
            {units.data
              ?.filter((unit) => unit.unit_type === 'department')
              .map((unit) => (
                <option key={unit.id} value={unit.id}>
                  {unit.name}
                </option>
              ))}
          </select>
          <select
            aria-label="Filter employment status"
            className="h-10 rounded-xl border bg-background px-3"
            onChange={(event) => {
              setEmploymentStatus(event.target.value)
              resetPage()
            }}
            value={employmentStatus}
          >
            <option value="">All employment states</option>
            <option value="active">Active</option>
            <option value="probation">Probation</option>
            <option value="on_leave">On leave</option>
            <option value="suspended">Suspended</option>
            <option value="terminated">Terminated</option>
          </select>
        </div>
        {selected.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b bg-primary/5 px-4 py-3 text-sm">
            <strong>{selected.length} selected</strong>
            {['activate', 'disable', 'delete', 'restore'].map((action) => (
              <button
                className="rounded-lg border bg-background px-3 py-1.5 capitalize"
                key={action}
                onClick={() => void bulk(action)}
                type="button"
              >
                {action}
              </button>
            ))}
          </div>
        )}
        <div className="divide-y">
          {userRows.map((user) => (
            <article
              className="grid gap-3 p-4 md:grid-cols-[auto_1fr_1fr_auto] md:items-center"
              key={user.id}
            >
              <input
                aria-label={`Select ${user.display_name}`}
                checked={selected.includes(user.id)}
                onChange={(event) =>
                  setSelected((current) =>
                    event.target.checked
                      ? [...current, user.id]
                      : current.filter((id) => id !== user.id),
                  )
                }
                type="checkbox"
              />
              <div>
                <button
                  className="font-semibold hover:text-primary"
                  onClick={() => open(user)}
                  type="button"
                >
                  {user.display_name}
                </button>
                <p className="text-sm text-muted-foreground">{user.email}</p>
              </div>
              <div className="text-sm">
                <p>{user.job_title || 'No job title'}</p>
                <p className="text-muted-foreground">
                  {user.department || 'No department'} · {user.employment_type}{' '}
                  · {user.roles.map((role) => role.name).join(', ')}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    user.status === 'active'
                      ? 'bg-emerald-500/10 text-emerald-700'
                      : 'bg-amber-500/10 text-amber-700'
                  }`}
                >
                  {user.employment_status === 'terminated'
                    ? 'terminated'
                    : user.status === 'suspended'
                      ? 'disabled'
                      : user.employment_status}
                </span>
                <select
                  aria-label={`Actions for ${user.display_name}`}
                  className="h-9 rounded-lg border bg-background px-2 text-sm"
                  onChange={(event) => {
                    const action = event.target.value
                    event.target.value = ''
                    if (action) void lifecycle(user, action)
                  }}
                  defaultValue=""
                >
                  <option value="">Actions</option>
                  <option value="reset">Reset password</option>
                  {user.status === 'active' ? (
                    <option value="disable">Disable</option>
                  ) : (
                    <option value="activate">Activate</option>
                  )}
                  {user.employment_status === 'terminated' ? (
                    <option value="rehire">Rehire employee</option>
                  ) : (
                    <option value="terminate">Terminate employment</option>
                  )}
                  <option value="delete">Delete</option>
                  <option value="restore">Restore</option>
                </select>
              </div>
            </article>
          ))}
          {!users.isLoading && !userRows.length && (
            <div className="p-12 text-center">
              <Users className="mx-auto size-8 text-muted-foreground" />
              <h2 className="mt-3 font-semibold">
                No users match these filters
              </h2>
            </div>
          )}
        </div>
        <footer className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
          <span>
            Page {users.data?.page ?? 1} of {users.data?.total_pages ?? 1} ·{' '}
            {users.data?.total ?? 0} users
          </span>
          <div className="flex gap-2">
            <button
              aria-label="Previous user page"
              className="grid size-9 place-items-center rounded-lg border disabled:opacity-40"
              disabled={!users.data || users.data.page <= 1}
              onClick={() => {
                setPage((current) => Math.max(1, current - 1))
                setSelected([])
              }}
              type="button"
            >
              <ChevronLeft className="size-4" />
            </button>
            <button
              aria-label="Next user page"
              className="grid size-9 place-items-center rounded-lg border disabled:opacity-40"
              disabled={
                !users.data || users.data.page >= users.data.total_pages
              }
              onClick={() => {
                setPage((current) => current + 1)
                setSelected([])
              }}
              type="button"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </footer>
      </section>

      {editing && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-4">
          <section
            aria-label={editing === 'new' ? 'Create user' : 'Edit user'}
            className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border bg-background shadow-2xl"
            role="dialog"
          >
            <header className="flex items-center justify-between border-b p-5">
              <div>
                <h2 className="text-xl font-semibold">
                  {editing === 'new' ? 'Create user' : 'Edit user'}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Identity, directory context, role, and meeting access.
                </p>
              </div>
              <button
                aria-label="Close user editor"
                onClick={() => setEditing(null)}
                type="button"
              >
                <X className="size-5" />
              </button>
            </header>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              {(
                [
                  ['First name', 'first_name'],
                  ['Last name', 'last_name'],
                  ['Email', 'email'],
                  ['Phone', 'phone'],
                  ['Alternative phone', 'alternative_phone'],
                  ['Job title', 'job_title'],
                ] as Array<[string, keyof UserInput]>
              ).map(([label, key]) => (
                <label className="space-y-1.5 text-sm" key={key}>
                  <span className="font-medium">{label}</span>
                  <input
                    className="h-11 w-full rounded-xl border bg-background px-3"
                    onChange={(event) =>
                      setForm({ ...form, [key]: event.target.value })
                    }
                    type={key === 'email' ? 'email' : 'text'}
                    value={String(form[key as keyof UserInput] ?? '')}
                  />
                </label>
              ))}
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Department</span>
                <select
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) => {
                    const unit = units.data?.find(
                      (item) => item.id === event.target.value,
                    )
                    setForm({
                      ...form,
                      department_id: event.target.value || null,
                      department: unit?.name ?? '',
                    })
                  }}
                  value={form.department_id ?? ''}
                >
                  <option value="">No department</option>
                  {units.data
                    ?.filter((unit) => unit.unit_type === 'department')
                    .map((unit) => (
                      <option key={unit.id} value={unit.id}>
                        {unit.name}
                      </option>
                    ))}
                </select>
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Manager</span>
                <select
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setForm({ ...form, manager_id: event.target.value || null })
                  }
                  value={form.manager_id ?? ''}
                >
                  <option value="">No manager assigned</option>
                  {managerCandidates.data?.items
                    .filter(
                      (candidate) =>
                        candidate.id !==
                        (editing === 'new' ? null : editing?.id),
                    )
                    .map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.display_name}
                      </option>
                    ))}
                </select>
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Employee number</span>
                <input
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setForm({ ...form, employee_number: event.target.value })
                  }
                  placeholder="EMP-0001"
                  value={form.employee_number ?? ''}
                />
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Employment status</span>
                <select
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setForm({
                      ...form,
                      employment_status: event.target
                        .value as UserInput['employment_status'],
                    })
                  }
                  value={form.employment_status ?? 'active'}
                >
                  <option value="active">Active</option>
                  <option value="probation">Probation</option>
                  <option value="on_leave">On leave</option>
                  <option value="suspended">Suspended</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Employment type</span>
                <select
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setForm({
                      ...form,
                      employment_type: event.target
                        .value as UserInput['employment_type'],
                    })
                  }
                  value={form.employment_type ?? 'permanent'}
                >
                  <option value="permanent">Permanent</option>
                  <option value="contract">Contract</option>
                  <option value="temporary">Temporary</option>
                  <option value="intern">Intern</option>
                  <option value="consultant">Consultant</option>
                </select>
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Start date</span>
                <input
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setForm({
                      ...form,
                      employment_start_date: event.target.value || null,
                    })
                  }
                  type="date"
                  value={form.employment_start_date ?? ''}
                />
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Confirmation date</span>
                <input
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setForm({
                      ...form,
                      employment_confirmation_date: event.target.value || null,
                    })
                  }
                  type="date"
                  value={form.employment_confirmation_date ?? ''}
                />
              </label>
              {editing !== 'new' && (
                <>
                  <label className="space-y-1.5 text-sm">
                    <span className="font-medium">Effective date</span>
                    <input
                      className="h-11 w-full rounded-xl border bg-background px-3"
                      onChange={(event) =>
                        setForm({
                          ...form,
                          effective_date: event.target.value || null,
                        })
                      }
                      type="date"
                      value={form.effective_date ?? ''}
                    />
                  </label>
                  <label className="space-y-1.5 text-sm">
                    <span className="font-medium">Change reason</span>
                    <input
                      className="h-11 w-full rounded-xl border bg-background px-3"
                      onChange={(event) =>
                        setForm({
                          ...form,
                          employment_change_reason: event.target.value,
                        })
                      }
                      placeholder="Optional context for this change"
                      value={form.employment_change_reason ?? ''}
                    />
                  </label>
                </>
              )}
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Workspace</span>
                <select
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setForm({
                      ...form,
                      workspace_id: event.target.value || null,
                    })
                  }
                  value={form.workspace_id ?? ''}
                >
                  <option value="">No workspace</option>
                  {workspaces.data?.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">Team</span>
                <select
                  className="h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setForm({ ...form, team_id: event.target.value || null })
                  }
                  value={form.team_id ?? ''}
                >
                  <option value="">No team</option>
                  {teams.data?.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name}
                    </option>
                  ))}
                </select>
              </label>
              <fieldset className="space-y-2 sm:col-span-2">
                <legend className="text-sm font-medium">Roles</legend>
                <div className="grid gap-2 sm:grid-cols-3">
                  {roles.data?.map((role) => (
                    <label
                      className="flex items-center gap-2 rounded-xl border p-3 text-sm"
                      key={role.id}
                    >
                      <input
                        checked={form.role_ids.includes(role.id)}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            role_ids: event.target.checked
                              ? [...form.role_ids, role.id]
                              : form.role_ids.filter((id) => id !== role.id),
                          })
                        }
                        type="checkbox"
                      />
                      <ShieldCheck className="size-4 text-primary" />
                      {role.name}
                    </label>
                  ))}
                </div>
              </fieldset>
              {editing === 'new' && (
                <label className="flex items-start gap-3 rounded-xl border p-3 text-sm sm:col-span-2">
                  <input
                    checked={form.send_welcome_email !== false}
                    className="mt-1"
                    onChange={(event) =>
                      setForm({
                        ...form,
                        send_welcome_email: event.target.checked,
                      })
                    }
                    type="checkbox"
                  />
                  <span>
                    <span className="block font-medium">
                      Send account-ready email
                    </span>
                    <span className="block text-muted-foreground">
                      Sends the temporary-password and first-sign-in
                      instructions to this user.
                    </span>
                  </span>
                </label>
              )}
              {editing !== 'new' && (
                <section className="rounded-2xl border bg-muted/30 p-4 sm:col-span-2">
                  <div className="flex items-center gap-2">
                    <History className="size-4 text-primary" />
                    <h3 className="font-semibold">Employment history</h3>
                  </div>
                  {history.isLoading ? (
                    <p className="mt-3 text-sm text-muted-foreground">
                      Loading history…
                    </p>
                  ) : history.data?.items.length ? (
                    <ol className="mt-3 space-y-3">
                      {history.data.items.slice(0, 5).map((entry) => (
                        <li className="flex gap-3 text-sm" key={entry.id}>
                          <Building2 className="mt-0.5 size-4 shrink-0 text-primary" />
                          <div>
                            <p className="font-medium capitalize">
                              {entry.change_type
                                .replaceAll('_', ' ')
                                .replace(/\b\w/g, (letter) =>
                                  letter.toUpperCase(),
                                )}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Effective {entry.effective_date}
                              {entry.reason ? ` · ${entry.reason}` : ''}
                              {' · Recorded '}
                              {new Date(entry.created_at).toLocaleString()}
                            </p>
                            {Object.keys(entry.new_values).length > 0 && (
                              <p className="mt-1 text-xs text-muted-foreground">
                                Changed:{' '}
                                {Object.keys(entry.new_values).join(', ')}
                              </p>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">
                      Employment changes will be recorded here.
                    </p>
                  )}
                </section>
              )}
            </div>
            <footer className="flex justify-end gap-3 border-t p-5">
              <button
                className="h-11 rounded-xl border px-4"
                onClick={() => setEditing(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="h-11 rounded-xl bg-primary px-5 font-semibold text-primary-foreground disabled:opacity-50"
                disabled={
                  !form.first_name ||
                  !form.email ||
                  !form.role_ids.length ||
                  save.isPending
                }
                onClick={() => save.mutate()}
                type="button"
              >
                {save.isPending ? 'Saving…' : 'Save user'}
              </button>
            </footer>
          </section>
        </div>
      )}

      {temporaryPassword && (
        <div className="fixed bottom-5 right-5 max-w-md rounded-2xl border bg-card p-5 shadow-2xl">
          <p className="font-semibold">Temporary password created</p>
          <code className="mt-2 block rounded-lg bg-muted p-3">
            {temporaryPassword}
          </code>
          <p className="mt-2 text-xs text-muted-foreground">
            Share securely. The user must change it at next sign-in.
          </p>
        </div>
      )}
    </div>
  )
}
