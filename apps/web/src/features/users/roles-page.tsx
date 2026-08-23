import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  ChevronDown,
  ChevronsDown,
  ChevronsUp,
  CircleAlert,
  KeyRound,
  LockKeyhole,
  Search,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { useConfirmation } from '@/components/feedback/confirmation'
import { type Permission, type Role, userAdminApi } from '@/features/users/api'

const roleDisplayName = (name: string) =>
  name === 'Admin' ? 'Organization Admin' : name

export function RolesPage() {
  const client = useQueryClient()
  const confirm = useConfirmation()
  const roles = useQuery({ queryKey: ['roles'], queryFn: userAdminApi.roles })
  const permissions = useQuery({
    queryKey: ['permissions'],
    queryFn: userAdminApi.permissions,
  })
  const [expandedRoles, setExpandedRoles] = useState<Set<string>>(new Set())
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [drafts, setDrafts] = useState<Record<string, string[]>>({})
  const [search, setSearch] = useState('')
  useEffect(() => {
    if (!roles.data) return
    setDrafts((current) => {
      const next = { ...current }
      for (const role of roles.data)
        if (!next[role.id])
          next[role.id] = role.permissions.map((permission) => permission.id)
      return next
    })
  }, [roles.data])
  const grouped = useMemo(() => {
    const groups = new Map<string, Permission[]>()
    for (const permission of permissions.data ?? []) {
      const current = groups.get(permission.resource) ?? []
      groups.set(permission.resource, [...current, permission])
    }
    return [...groups.entries()]
  }, [permissions.data])
  const updateRole = useMutation({
    mutationFn: ({
      role,
      permissionIds,
    }: {
      role: Role
      permissionIds: string[]
    }) =>
      userAdminApi.updateRole(role.id, {
        permission_ids: permissionIds,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['roles'] }),
  })

  const toggleRole = (roleId: string) =>
    setExpandedRoles((current) => {
      const next = new Set(current)
      if (next.has(roleId)) next.delete(roleId)
      else next.add(roleId)
      return next
    })
  const toggleGroup = (key: string) =>
    setExpandedGroups((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  const setPermission = (
    roleId: string,
    permissionId: string,
    enabled: boolean,
  ) =>
    setDrafts((current) => {
      const selected = current[roleId] ?? []
      return {
        ...current,
        [roleId]: enabled
          ? [...new Set([...selected, permissionId])]
          : selected.filter((id) => id !== permissionId),
      }
    })
  const setGroup = (
    roleId: string,
    permissionRows: Permission[],
    enabled: boolean,
  ) =>
    setDrafts((current) => {
      const selected = current[roleId] ?? []
      const ids = new Set(permissionRows.map((permission) => permission.id))
      return {
        ...current,
        [roleId]: enabled
          ? [...new Set([...selected, ...ids])]
          : selected.filter((id) => !ids.has(id)),
      }
    })
  const save = async (role: Role) => {
    const approved = await confirm({
      title: `Update ${roleDisplayName(role.name)} permissions?`,
      description:
        'Permission changes immediately affect navigation and API access for every user assigned to this role.',
      confirmLabel: 'Update permissions',
      tone: 'primary',
    })
    if (approved)
      updateRole.mutate({
        role,
        permissionIds: drafts[role.id] ?? [],
      })
  }
  const expandAll = () => {
    setExpandedRoles(new Set((roles.data ?? []).map((role) => role.id)))
    setExpandedGroups(
      new Set(
        (roles.data ?? []).flatMap((role) =>
          grouped.map(([resource]) => `${role.id}:${resource}`),
        ),
      ),
    )
  }
  const collapseAll = () => {
    setExpandedRoles(new Set())
    setExpandedGroups(new Set())
  }
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-5 sm:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Access control</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Roles & permissions
          </h1>
          <p className="mt-2 max-w-3xl text-muted-foreground">
            Define permission policies with focused, expandable groups. Menu
            visibility and API authorization update from the same source.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="flex items-center gap-2 rounded-xl border bg-card px-3 py-2 text-sm font-semibold"
            onClick={expandAll}
            type="button"
          >
            <ChevronsDown className="size-4" />
            Expand all
          </button>
          <button
            className="flex items-center gap-2 rounded-xl border bg-card px-3 py-2 text-sm font-semibold"
            onClick={collapseAll}
            type="button"
          >
            <ChevronsUp className="size-4" />
            Collapse all
          </button>
        </div>
      </header>
      <section className="grid gap-4 sm:grid-cols-3">
        <Metric
          icon={ShieldCheck}
          label="Defined roles"
          value={roles.data?.length ?? 0}
        />
        <Metric
          icon={KeyRound}
          label="Available permissions"
          value={permissions.data?.length ?? 0}
        />
        <Metric icon={Users} label="Permission groups" value={grouped.length} />
      </section>
      <label className="relative block">
        <Search className="absolute left-3 top-3.5 size-4 text-muted-foreground" />
        <input
          aria-label="Search permissions"
          className="h-11 w-full rounded-xl border bg-card pl-10 pr-3 text-sm"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search permissions by name, action, resource, or description"
          value={search}
        />
      </label>
      {roles.isLoading || permissions.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }, (_, index) => (
            <div
              className="h-20 animate-pulse rounded-2xl bg-muted"
              key={index}
            />
          ))}
        </div>
      ) : roles.isError || permissions.isError ? (
        <div
          className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6 text-red-600"
          role="alert"
        >
          Roles and permissions could not be loaded.
        </div>
      ) : (
        <section className="space-y-3">
          {roles.data?.map((role) => {
            const expanded = expandedRoles.has(role.id)
            const selected = drafts[role.id] ?? []
            const changed =
              [...selected].sort().join(',') !==
              role.permissions
                .map((permission) => permission.id)
                .sort()
                .join(',')
            return (
              <article
                className={`overflow-hidden rounded-2xl border bg-card transition ${expanded ? 'border-primary/30 shadow-md' : ''}`}
                key={role.id}
              >
                <button
                  aria-expanded={expanded}
                  className="flex w-full items-center gap-4 p-4 text-left sm:p-5"
                  onClick={() => toggleRole(role.id)}
                  type="button"
                >
                  <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                    <ShieldCheck className="size-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2 font-semibold">
                      {roleDisplayName(role.name)}
                      {role.system_role && (
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                          Default
                        </span>
                      )}
                    </span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {selected.length} of {permissions.data?.length ?? 0}{' '}
                      permissions enabled
                    </span>
                  </span>
                  {changed && (
                    <span className="hidden rounded-full bg-amber-500/10 px-2 py-1 text-[11px] font-semibold text-amber-700 sm:block">
                      Unsaved changes
                    </span>
                  )}
                  <ChevronDown
                    className={`size-5 transition ${expanded ? 'rotate-180' : ''}`}
                  />
                </button>
                {expanded && (
                  <div className="border-t p-4 sm:p-5">
                    <div className="flex flex-col gap-3 rounded-xl bg-muted/40 p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="font-semibold">
                          {roleDisplayName(role.name)} policy
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {role.description ||
                            'Organization role permission policy.'}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="rounded-lg border bg-background px-3 py-2 text-xs font-semibold"
                          onClick={() =>
                            setGroup(role.id, permissions.data ?? [], true)
                          }
                          type="button"
                        >
                          Enable all
                        </button>
                        <button
                          className="rounded-lg border bg-background px-3 py-2 text-xs font-semibold"
                          onClick={() =>
                            setGroup(role.id, permissions.data ?? [], false)
                          }
                          type="button"
                        >
                          Disable all
                        </button>
                        <button
                          className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-50"
                          disabled={!changed || updateRole.isPending}
                          onClick={() => void save(role)}
                          type="button"
                        >
                          {updateRole.isPending &&
                          updateRole.variables?.role.id === role.id
                            ? 'Saving…'
                            : 'Save changes'}
                        </button>
                      </div>
                    </div>
                    <div className="mt-4 space-y-3">
                      {grouped.map(([resource, rows]) => {
                        const matching = rows.filter((permission) =>
                          `${permission.name} ${permission.action} ${permission.description ?? ''}`
                            .toLowerCase()
                            .includes(search.toLowerCase()),
                        )
                        if (search && !matching.length) return null
                        const visibleRows = search ? matching : rows
                        const groupKey = `${role.id}:${resource}`
                        const groupExpanded =
                          Boolean(search) || expandedGroups.has(groupKey)
                        const selectedCount = rows.filter((permission) =>
                          selected.includes(permission.id),
                        ).length
                        return (
                          <section
                            className="overflow-hidden rounded-xl border"
                            key={resource}
                          >
                            <div className="flex items-center gap-3 p-3">
                              <button
                                aria-expanded={groupExpanded}
                                className="flex min-w-0 flex-1 items-center gap-3 text-left"
                                onClick={() => toggleGroup(groupKey)}
                                type="button"
                              >
                                <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
                                  <LockKeyhole className="size-4" />
                                </span>
                                <span className="min-w-0 flex-1">
                                  <span className="block font-semibold capitalize">
                                    {resource.replaceAll('_', ' ')}
                                  </span>
                                  <span className="text-xs text-muted-foreground">
                                    {selectedCount} of {rows.length} enabled
                                  </span>
                                </span>
                                <ChevronDown
                                  className={`size-4 transition ${groupExpanded ? 'rotate-180' : ''}`}
                                />
                              </button>
                              <button
                                className="hidden rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold sm:block"
                                onClick={() =>
                                  setGroup(
                                    role.id,
                                    rows,
                                    selectedCount !== rows.length,
                                  )
                                }
                                type="button"
                              >
                                {selectedCount === rows.length
                                  ? 'Disable group'
                                  : 'Enable group'}
                              </button>
                            </div>
                            {groupExpanded && (
                              <div className="grid gap-2 border-t bg-muted/20 p-3 md:grid-cols-2">
                                {visibleRows.map((permission) => (
                                  <PermissionToggle
                                    checked={selected.includes(permission.id)}
                                    dependency={
                                      permission.action !== 'view' &&
                                      rows.some(
                                        (candidate) =>
                                          candidate.action === 'view',
                                      )
                                        ? `${resource}.view`
                                        : undefined
                                    }
                                    key={permission.id}
                                    onChange={(checked) =>
                                      setPermission(
                                        role.id,
                                        permission.id,
                                        checked,
                                      )
                                    }
                                    permission={permission}
                                  />
                                ))}
                              </div>
                            )}
                          </section>
                        )
                      })}
                    </div>
                  </div>
                )}
              </article>
            )
          })}
        </section>
      )}
    </div>
  )
}

function PermissionToggle({
  permission,
  checked,
  onChange,
  dependency,
}: {
  permission: Permission
  checked: boolean
  onChange: (checked: boolean) => void
  dependency?: string
}) {
  return (
    <article className="flex items-start gap-3 rounded-xl bg-card p-3">
      <button
        aria-label={`${checked ? 'Disable' : 'Enable'} ${permission.name}`}
        aria-pressed={checked}
        className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition ${checked ? 'bg-primary' : 'bg-muted'}`}
        onClick={() => onChange(!checked)}
        type="button"
      >
        <span
          className={`absolute top-1 size-4 rounded-full bg-white shadow transition ${checked ? 'left-6' : 'left-1'}`}
        />
      </button>
      <div className="min-w-0">
        <p className="text-sm font-semibold capitalize">
          {permission.action.replaceAll('_', ' ')}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          {permission.description || permission.name}
        </p>
        {dependency && (
          <p className="mt-2 flex items-center gap-1 text-[10px] font-medium text-amber-700">
            <CircleAlert className="size-3" />
            Depends on {dependency}
          </p>
        )}
      </div>
      {checked && (
        <Check className="ml-auto size-4 shrink-0 text-emerald-600" />
      )}
    </article>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof ShieldCheck
  label: string
  value: number
}) {
  return (
    <article className="flex items-center gap-4 rounded-2xl border bg-card p-5">
      <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
        <Icon className="size-5" />
      </span>
      <div>
        <p className="text-xl font-semibold">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </article>
  )
}
