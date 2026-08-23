import { useQuery } from '@tanstack/react-query'
import { Navigate } from '@tanstack/react-router'
import {
  Download,
  FileClock,
  Filter,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  auditApi,
  type AuditFilters,
  type AuditRecord,
} from '@/features/audit/api'
import { useAuth } from '@/features/auth/auth-store'

export function AuditCenterPage() {
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [action, setAction] = useState('')
  const [selected, setSelected] = useState<AuditRecord | null>(null)
  const filters = useMemo<AuditFilters>(
    () => ({ search, category, action }),
    [action, category, search],
  )
  const audit = useQuery({
    queryKey: ['audit', filters],
    queryFn: () => auditApi.list(filters),
  })
  if (!user?.roles.includes('Super Admin')) return <Navigate to="/forbidden" />
  const exportRecords = async () => {
    const blob = await auditApi.export(filters)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'meetinghq-audit.csv'
    link.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-5 sm:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Compliance</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Audit Center
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Immutable, tenant-isolated records of security, administration,
            configuration, and collaboration changes.
          </p>
        </div>
        <button
          className="flex items-center justify-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold"
          onClick={() => void exportRecords()}
          type="button"
        >
          <Download className="size-4" />
          Export CSV
        </button>
      </header>
      <section className="grid gap-4 sm:grid-cols-3">
        <Metric
          label="Records found"
          value={audit.data?.total ?? 0}
          icon={FileClock}
        />
        <Metric
          label="Event categories"
          value={audit.data?.categories.length ?? 0}
          icon={Filter}
        />
        <Metric label="Retention model" value="Immutable" icon={ShieldCheck} />
      </section>
      <section className="grid gap-3 rounded-2xl border bg-card p-4 md:grid-cols-[1fr_200px_240px]">
        <label className="relative">
          <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
          <input
            aria-label="Search audit records"
            className="h-10 w-full rounded-xl border bg-background pl-10 pr-3 text-sm"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search user, action, or resource"
            value={search}
          />
        </label>
        <select
          aria-label="Filter by category"
          className="h-10 rounded-xl border bg-background px-3 text-sm"
          onChange={(event) => setCategory(event.target.value)}
          value={category}
        >
          <option value="">All categories</option>
          {audit.data?.categories.map((item) => (
            <option key={item} value={item.toLowerCase()}>
              {item}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by action"
          className="h-10 rounded-xl border bg-background px-3 text-sm"
          onChange={(event) => setAction(event.target.value)}
          value={action}
        >
          <option value="">All actions</option>
          {audit.data?.actions.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </section>
      <section className="overflow-hidden rounded-2xl border bg-card">
        <div className="hidden grid-cols-[170px_1.2fr_1fr_1fr_100px] gap-4 border-b bg-muted/50 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground md:grid">
          <span>Timestamp</span>
          <span>Actor</span>
          <span>Action</span>
          <span>Resource</span>
          <span>Details</span>
        </div>
        {audit.isLoading && (
          <div className="space-y-3 p-4">
            {Array.from({ length: 6 }, (_, index) => (
              <div
                className="h-14 animate-pulse rounded-xl bg-muted"
                key={index}
              />
            ))}
          </div>
        )}
        {audit.isError && (
          <p className="p-8 text-center text-sm text-red-600">
            Audit records could not be loaded.
          </p>
        )}
        {audit.data?.items.map((record) => (
          <article
            className="grid gap-2 border-b px-4 py-4 last:border-0 md:grid-cols-[170px_1.2fr_1fr_1fr_100px] md:items-center md:gap-4"
            key={record.id}
          >
            <time className="text-xs text-muted-foreground">
              {new Date(record.created_at).toLocaleString()}
            </time>
            <div>
              <p className="text-sm font-semibold">{record.user_name}</p>
              <p className="text-xs text-muted-foreground">
                {record.ip_address ?? 'Internal event'}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium">{record.action}</p>
              <span className="mt-1 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                {record.category}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              {record.resource}
              {record.resource_id ? ` · ${record.resource_id.slice(0, 8)}` : ''}
            </p>
            <button
              className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold"
              onClick={() => setSelected(record)}
              type="button"
            >
              View
            </button>
          </article>
        ))}
        {audit.data?.items.length === 0 && (
          <div className="p-10 text-center">
            <FileClock className="mx-auto size-8 text-muted-foreground" />
            <p className="mt-3 font-semibold">
              No audit events match these filters
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Change the filters to broaden your search.
            </p>
          </div>
        )}
      </section>
      {selected && (
        <AuditDrawer record={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: number | string
  icon: typeof FileClock
}) {
  return (
    <article className="flex items-center gap-4 rounded-2xl border bg-card p-5">
      <div className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
        <Icon className="size-5" />
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="mt-0.5 text-xl font-semibold">{value}</p>
      </div>
    </article>
  )
}

function AuditDrawer({
  record,
  onClose,
}: {
  record: AuditRecord
  onClose: () => void
}) {
  return (
    <div
      className="fixed inset-0 z-[70] flex justify-end bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label="Audit event details"
    >
      <button
        className="flex-1"
        aria-label="Close details"
        onClick={onClose}
        type="button"
      />
      <aside className="h-full w-full max-w-lg overflow-y-auto border-l bg-background p-6 shadow-2xl">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold text-primary">
              {record.category}
            </p>
            <h2 className="mt-1 text-xl font-semibold">{record.action}</h2>
          </div>
          <button
            aria-label="Close details"
            className="rounded-lg p-2 hover:bg-muted"
            onClick={onClose}
            type="button"
          >
            <X className="size-5" />
          </button>
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
          <Detail label="Actor" value={record.user_name} />
          <Detail
            label="Timestamp"
            value={new Date(record.created_at).toLocaleString()}
          />
          <Detail label="Resource" value={record.resource} />
          <Detail
            label="Resource ID"
            value={record.resource_id ?? 'Not applicable'}
          />
          <Detail
            label="IP address"
            value={record.ip_address ?? 'Not captured'}
          />
          <Detail
            label="Browser / device"
            value={
              [record.browser, record.device].filter(Boolean).join(' · ') ||
              'Not captured'
            }
          />
          <Detail
            label="Request ID"
            value={record.request_id ?? 'Not captured'}
          />
        </dl>
        <h3 className="mt-8 text-sm font-semibold">Event metadata</h3>
        <pre className="mt-3 overflow-auto rounded-xl bg-muted p-4 text-xs">
          {JSON.stringify(record.metadata, null, 2)}
        </pre>
      </aside>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-all">{value}</dd>
    </div>
  )
}
