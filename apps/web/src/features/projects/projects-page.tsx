import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { FolderKanban, Plus, Search } from 'lucide-react'
import { type FormEvent, type ReactNode, useMemo, useState } from 'react'

import { projectsApi } from './api'
import { useAuth } from '@/features/auth/auth-store'
import { tasksApi } from '@/features/tasks/api'

const label = (value: string) =>
  value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

export function ProjectsPage() {
  const { user } = useAuth()
  const permissions = new Set(user?.permissions ?? [])
  const client = useQueryClient()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [health, setHealth] = useState('')
  const [priority, setPriority] = useState('')
  const [archived, setArchived] = useState(false)
  const [pageSize, setPageSize] = useState(25)
  const [page, setPage] = useState(1)
  const [showCreate, setShowCreate] = useState(false)
  const filters = useMemo(
    () => ({
      search,
      status,
      health,
      priority,
      archived,
      page,
      page_size: pageSize,
    }),
    [archived, health, page, pageSize, priority, search, status],
  )
  const projects = useQuery({
    queryKey: ['projects', filters],
    queryFn: () => projectsApi.list(filters),
  })
  const people = useQuery({
    queryKey: ['project-people'],
    queryFn: tasksApi.assignees,
    enabled: showCreate,
  })
  const create = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: () => {
      setShowCreate(false)
      void client.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  return (
    <main className="w-full space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Work management</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Projects
          </h1>
          <p className="mt-2 max-w-3xl text-muted-foreground">
            Coordinate outcomes, milestones, people and canonical OfficeFlow
            tasks in one place.
          </p>
        </div>
        {permissions.has('projects.create') && (
          <button
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 font-semibold text-primary-foreground"
            onClick={() => setShowCreate(true)}
          >
            <Plus size={18} /> New project
          </button>
        )}
      </header>

      <section
        className="grid gap-3 sm:grid-cols-3"
        aria-label="Project portfolio summary"
      >
        <Metric label="Visible projects" value={projects.data?.total ?? 0} />
        <Metric
          label="At risk"
          value={
            (projects.data?.items ?? []).filter(
              (item) => item.health === 'at_risk',
            ).length
          }
        />
        <Metric
          label="Overdue tasks"
          value={(projects.data?.items ?? []).reduce(
            (sum, item) => sum + item.overdue_task_count,
            0,
          )}
        />
      </section>

      <section className="rounded-2xl border bg-card shadow-sm">
        <div className="flex flex-col gap-3 border-b p-4 lg:flex-row lg:items-center">
          <label className="relative flex-1">
            <span className="sr-only">Search projects</span>
            <Search
              className="absolute left-3 top-3 text-muted-foreground"
              size={18}
            />
            <input
              className="min-h-11 w-full rounded-xl border bg-background pl-10 pr-3"
              placeholder="Search by project name or code"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
            />
          </label>
          <select
            aria-label="Filter project status"
            className="min-h-11 rounded-xl border bg-background px-3"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            {[
              'draft',
              'planned',
              'active',
              'on_hold',
              'completed',
              'cancelled',
            ].map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter project priority"
            className="min-h-11 rounded-xl border bg-background px-3"
            value={priority}
            onChange={(event) => {
              setPriority(event.target.value)
              setPage(1)
            }}
          >
            <option value="">All priorities</option>
            {['low', 'normal', 'high', 'urgent'].map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
          <label className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-3 text-sm">
            <input
              checked={archived}
              onChange={(event) => {
                setArchived(event.target.checked)
                setPage(1)
              }}
              type="checkbox"
            />
            Archived
          </label>
          <select
            aria-label="Filter project health"
            className="min-h-11 rounded-xl border bg-background px-3"
            value={health}
            onChange={(event) => setHealth(event.target.value)}
          >
            <option value="">All health</option>
            {['on_track', 'at_risk', 'off_track', 'completed'].map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </div>

        {projects.isLoading ? (
          <div className="space-y-3 p-5" aria-label="Loading projects">
            {[1, 2, 3].map((row) => (
              <div
                key={row}
                className="h-20 animate-pulse rounded-xl bg-muted"
              />
            ))}
          </div>
        ) : projects.isError ? (
          <div className="p-8 text-center" role="alert">
            <p>Projects could not be loaded.</p>
            <button
              className="mt-3 text-primary underline"
              onClick={() => void projects.refetch()}
            >
              Try again
            </button>
          </div>
        ) : !projects.data?.items.length ? (
          <div className="flex flex-col items-center gap-3 p-12 text-center">
            <FolderKanban className="text-muted-foreground" size={38} />
            <h2 className="text-lg font-semibold">
              No projects match this view
            </h2>
            <p className="text-sm text-muted-foreground">
              Create a project or clear the filters to begin.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] text-left text-sm">
              <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                <tr>
                  {[
                    'Project',
                    'Manager',
                    'Status',
                    'Health',
                    'Progress',
                    'Target',
                    'Attention',
                    '',
                  ].map((column) => (
                    <th key={column} className="px-4 py-3">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {projects.data.items.map((project) => (
                  <tr key={project.id} className="hover:bg-muted/30">
                    <td className="px-4 py-4">
                      <strong className="block">{project.name}</strong>
                      <small className="text-muted-foreground">
                        {project.project_code}
                      </small>
                    </td>
                    <td className="px-4 py-4">
                      {project.manager_name ?? 'Unassigned'}
                    </td>
                    <td className="px-4 py-4">
                      <Badge value={project.status} />
                    </td>
                    <td className="px-4 py-4">
                      <Badge value={project.health} />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-2 w-28 overflow-hidden rounded-full bg-muted">
                        <span
                          className="block h-full bg-primary"
                          style={{ width: `${project.progress}%` }}
                        />
                      </div>
                      <small>{project.progress}%</small>
                    </td>
                    <td className="px-4 py-4">
                      {project.target_end_date ?? 'Not set'}
                    </td>
                    <td className="px-4 py-4">
                      {project.overdue_task_count
                        ? `${project.overdue_task_count} overdue`
                        : 'On schedule'}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <Link
                        className="font-semibold text-primary hover:underline"
                        to="/projects/$projectId"
                        params={{ projectId: project.id }}
                      >
                        Open project
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {projects.data && (
          <div className="flex items-center justify-between border-t p-4">
            <button
              disabled={page === 1}
              onClick={() => setPage((value) => value - 1)}
            >
              Previous
            </button>
            <span>
              Page {page} of {projects.data?.total_pages}
            </span>
            <div className="flex items-center gap-3">
              <label className="text-sm">
                Page size{' '}
                <select
                  aria-label="Project page size"
                  className="rounded-lg border bg-background px-2 py-1.5"
                  value={pageSize}
                  onChange={(event) => {
                    setPageSize(Number(event.target.value))
                    setPage(1)
                  }}
                >
                  {[10, 25, 50, 100].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <button
                disabled={page >= (projects.data?.total_pages ?? 1)}
                onClick={() => setPage((value) => value + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>

      {showCreate && (
        <CreateProjectDialog
          people={people.data ?? []}
          pending={create.isPending}
          error={create.error}
          onClose={() => setShowCreate(false)}
          onSubmit={(body) => create.mutate(body)}
        />
      )}
    </main>
  )
}

function CreateProjectDialog({
  people,
  pending,
  error,
  onClose,
  onSubmit,
}: {
  people: Awaited<ReturnType<typeof tasksApi.assignees>>
  pending: boolean
  error: Error | null
  onClose: () => void
  onSubmit: (body: Record<string, unknown>) => void
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    onSubmit({
      name: data.get('name'),
      description: data.get('description') || null,
      project_manager_id: data.get('project_manager_id'),
      start_date: data.get('start_date') || null,
      target_end_date: data.get('target_end_date') || null,
      priority: data.get('priority'),
      visibility: data.get('visibility'),
    })
  }
  return (
    <Dialog title="Create project" onClose={onClose}>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={submit}>
        <Field label="Project name">
          <input name="name" required maxLength={240} />
        </Field>
        <Field label="Project manager">
          <select name="project_manager_id" required>
            <option value="">Select manager</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.display_name}
                {person.job_title ? ` · ${person.job_title}` : ''}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Start date">
          <input name="start_date" type="date" />
        </Field>
        <Field label="Target end">
          <input name="target_end_date" type="date" />
        </Field>
        <Field label="Priority">
          <select name="priority" defaultValue="normal">
            {['low', 'normal', 'high', 'urgent'].map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Visibility">
          <select name="visibility" defaultValue="members">
            <option value="members">Project members</option>
            <option value="department">Department</option>
            <option value="organization">Organization</option>
          </select>
        </Field>
        <Field label="Description" wide>
          <textarea name="description" rows={4} />
        </Field>
        {error && (
          <p className="text-sm text-destructive sm:col-span-2" role="alert">
            {error.message}
          </p>
        )}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <button
            type="button"
            className="rounded-xl border px-4 py-2.5"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            disabled={pending}
            className="rounded-xl bg-primary px-4 py-2.5 font-semibold text-primary-foreground"
          >
            {pending ? 'Creating…' : 'Create project'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}

export function Dialog({
  title,
  children,
  onClose,
}: {
  title: string
  children: ReactNode
  onClose: () => void
}) {
  return (
    <div
      className="fixed inset-0 z-[70] grid place-items-center bg-black/55 p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-dialog-title"
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border bg-background p-5 shadow-2xl"
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 id="project-dialog-title" className="text-xl font-semibold">
            {title}
          </h2>
          <button
            aria-label="Close dialog"
            className="rounded-lg p-2 hover:bg-muted"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        {children}
      </section>
    </div>
  )
}

export function Field({
  label: fieldLabel,
  children,
  wide = false,
}: {
  label: string
  children: ReactNode
  wide?: boolean
}) {
  return (
    <label
      className={`grid gap-1.5 text-sm font-medium ${wide ? 'sm:col-span-2' : ''}`}
    >
      {fieldLabel}
      <span className="contents [&_input]:min-h-11 [&_input]:rounded-xl [&_input]:border [&_input]:bg-background [&_input]:px-3 [&_select]:min-h-11 [&_select]:rounded-xl [&_select]:border [&_select]:bg-background [&_select]:px-3 [&_textarea]:rounded-xl [&_textarea]:border [&_textarea]:bg-background [&_textarea]:p-3">
        {children}
      </span>
    </label>
  )
}

function Metric({
  label: metricLabel,
  value,
}: {
  label: string
  value: number
}) {
  return (
    <article className="rounded-2xl border bg-card p-4">
      <strong className="text-2xl">{value}</strong>
      <p className="text-sm text-muted-foreground">{metricLabel}</p>
    </article>
  )
}
export function Badge({ value }: { value: string }) {
  return (
    <span
      className="inline-flex rounded-full border bg-muted/50 px-2.5 py-1 text-xs font-semibold"
      aria-label={label(value)}
    >
      {label(value)}
    </span>
  )
}
