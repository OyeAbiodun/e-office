import { useQuery } from '@tanstack/react-query'
import { Navigate } from '@tanstack/react-router'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleGauge,
  Clock3,
  Database,
  HardDrive,
  RefreshCw,
  Server,
  Wifi,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'

import { useAuth } from '@/features/auth/auth-store'
import {
  systemHealthApi,
  type ComponentHealth,
  type HealthState,
} from '@/features/system-health/api'

const stateStyle: Record<HealthState, string> = {
  healthy: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  degraded: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
  unavailable: 'bg-red-500/10 text-red-700 dark:text-red-300',
  not_configured: 'bg-slate-500/10 text-slate-600 dark:text-slate-300',
}

const icons: Record<string, typeof Activity> = {
  api: Server,
  database: Database,
  redis: Activity,
  workers: CircleGauge,
  scheduler: Clock3,
  smtp: Wifi,
  storage: HardDrive,
  websocket: Wifi,
  integrations: Activity,
}

function formatUptime(seconds: number) {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${days}d ${hours}h ${minutes}m`
}

export function SystemHealthPage() {
  const { user } = useAuth()
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [selected, setSelected] = useState<ComponentHealth | null>(null)
  const health = useQuery({
    queryKey: ['system-health'],
    queryFn: systemHealthApi.snapshot,
    refetchInterval: autoRefresh ? 30_000 : false,
  })
  const history = useQuery({
    queryKey: ['system-health-history'],
    queryFn: systemHealthApi.history,
    refetchInterval: autoRefresh ? 60_000 : false,
  })
  if (!user?.roles.includes('Super Admin')) return <Navigate to="/forbidden" />
  if (health.isLoading) return <HealthLoading />
  if (health.isError || !health.data)
    return (
      <div className="mx-auto max-w-7xl p-5 sm:p-8">
        <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6">
          <XCircle className="size-7 text-red-600" />
          <h1 className="mt-3 text-xl font-semibold">
            Health data unavailable
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            The administration API could not complete a health snapshot.
          </p>
          <button
            className="mt-4 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            onClick={() => void health.refetch()}
            type="button"
          >
            Try again
          </button>
        </div>
      </div>
    )
  const data = health.data
  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-5 sm:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Operations</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            System Health
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Live operational status across MeetingHQ services, providers,
            queues, and storage.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 rounded-xl border bg-card px-3 py-2 text-sm">
            <input
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
              type="checkbox"
            />
            Auto-refresh
          </label>
          <button
            className="flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-semibold"
            disabled={health.isFetching}
            onClick={() => void health.refetch()}
            type="button"
          >
            <RefreshCw
              className={`size-4 ${health.isFetching ? 'animate-spin' : ''}`}
            />
            Refresh
          </button>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Health score"
          value={`${data.score}%`}
          detail={data.status.replace('_', ' ')}
          accent
        />
        <Metric
          label="Required services"
          value={`${data.required_healthy}/${data.required_total}`}
          detail="Healthy required components"
        />
        <Metric
          label="Uptime"
          value={formatUptime(data.uptime_seconds)}
          detail={`Version ${data.version}`}
        />
        <Metric
          label="Queue depth"
          value={String(data.queue.pending)}
          detail={`${data.queue.failed} failed · ${data.queue.delivered} delivered`}
        />
        <Metric
          label="Environment"
          value={data.environment}
          detail={`Updated ${new Date(data.last_updated).toLocaleTimeString()}`}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <HealthHistory points={history.data ?? []} />
        <article className="rounded-2xl border bg-card p-5">
          <h2 className="font-semibold">Readiness policy</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Only required services and configured optional providers affect the
            health score. Unconfigured optional capabilities remain visible
            without reducing readiness.
          </p>
          <div className="mt-4 rounded-xl bg-primary/5 p-4">
            <p className="text-3xl font-semibold text-primary">{data.score}%</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Current production readiness
            </p>
          </div>
        </article>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.components.map((component) => (
          <button
            className="text-left"
            key={component.key}
            onClick={() => setSelected(component)}
            type="button"
          >
            <ComponentCard component={component} />
          </button>
        ))}
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <HealthList
          empty="No active operational warnings."
          icon={AlertTriangle}
          items={[...data.errors, ...data.warnings]}
          title="Warnings and errors"
        />
        <HealthList
          empty="No recommendations. Core services are configured."
          icon={CheckCircle2}
          items={data.recommendations}
          title="Recommendations"
        />
      </section>
      {selected && (
        <div
          className="fixed inset-0 z-[90] flex justify-end bg-black/45"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) setSelected(null)
          }}
        >
          <aside
            aria-label={`${selected.name} health details`}
            className="h-full w-full max-w-lg overflow-y-auto border-l bg-background p-6 shadow-2xl"
          >
            <button
              className="float-right rounded-lg border px-3 py-1.5 text-sm"
              onClick={() => setSelected(null)}
              type="button"
            >
              Close
            </button>
            <p className="text-sm font-semibold text-primary">
              {selected.category}
            </p>
            <h2 className="mt-1 text-2xl font-semibold">{selected.name}</h2>
            <span
              className={`mt-4 inline-flex rounded-full px-3 py-1 text-xs font-semibold capitalize ${stateStyle[selected.status]}`}
            >
              {selected.status.replace('_', ' ')}
            </span>
            <dl className="mt-6 grid gap-4">
              <Detail label="Requirement" value={selected.requirement} />
              <Detail
                label="Configured"
                value={selected.configured ? 'Yes' : 'No'}
              />
              <Detail
                label="Latency"
                value={
                  selected.latency_ms === null
                    ? 'Not measured'
                    : `${selected.latency_ms} ms`
                }
              />
              <Detail label="Diagnostic" value={selected.message} />
            </dl>
            {Object.keys(selected.details).length > 0 && (
              <pre className="mt-6 overflow-x-auto rounded-xl bg-muted p-4 text-xs">
                {JSON.stringify(selected.details, null, 2)}
              </pre>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}

function Metric({
  label,
  value,
  detail,
  accent = false,
}: {
  label: string
  value: string
  detail: string
  accent?: boolean
}) {
  return (
    <article
      className={`rounded-2xl border p-5 ${accent ? 'border-primary/30 bg-primary/5' : 'bg-card'}`}
    >
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold capitalize">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </article>
  )
}

function ComponentCard({ component }: { component: ComponentHealth }) {
  const Icon = icons[component.key] ?? Activity
  return (
    <article className="rounded-2xl border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
          <Icon className="size-5" />
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${stateStyle[component.status]}`}
        >
          {component.status.replace('_', ' ')}
        </span>
      </div>
      <div className="mt-3 flex gap-2">
        <span className="rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize">
          {component.requirement}
        </span>
        {!component.configured && (
          <span className="rounded-full border px-2 py-0.5 text-[10px]">
            Unconfigured
          </span>
        )}
      </div>
      <p className="mt-4 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {component.category}
      </p>
      <h2 className="mt-1 font-semibold">{component.name}</h2>
      <p className="mt-2 min-h-10 text-sm text-muted-foreground">
        {component.message}
      </p>
      {component.latency_ms !== null && (
        <p className="mt-3 text-xs font-medium text-muted-foreground">
          {component.latency_ms} ms latency
        </p>
      )}
    </article>
  )
}

function HealthHistory({
  points,
}: {
  points: Awaited<ReturnType<typeof systemHealthApi.history>>
}) {
  if (points.length === 0)
    return (
      <article className="min-w-0 rounded-2xl border bg-card p-5">
        <h2 className="font-semibold">Health history</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Readiness score and incident recovery over the last 96 samples.
        </p>
        <div className="mt-5 grid h-44 place-items-center rounded-xl border border-dashed bg-muted/20 p-6 text-center">
          <div>
            <Activity className="mx-auto size-6 text-muted-foreground" />
            <p className="mt-2 text-sm font-medium">
              History is being collected
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              The first measured sample will appear after the next collection
              interval.
            </p>
          </div>
        </div>
      </article>
    )
  const values = points
  const width = 700
  const height = 180
  const path = values
    .map((point, index) => {
      const x =
        values.length === 1 ? width : (index / (values.length - 1)) * width
      const y = height - (point.score / 100) * height
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
  return (
    <article className="min-w-0 rounded-2xl border bg-card p-5">
      <h2 className="font-semibold">Health history</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Readiness score and incident recovery over the last 96 samples.
      </p>
      <div className="mt-5 overflow-hidden rounded-xl bg-muted/40 p-3">
        <svg
          aria-label="Health score history chart"
          className="h-44 w-full"
          preserveAspectRatio="none"
          role="img"
          viewBox={`0 0 ${width} ${height}`}
        >
          <line
            stroke="currentColor"
            strokeDasharray="5 5"
            strokeOpacity=".15"
            x1="0"
            x2={width}
            y1={height / 2}
            y2={height / 2}
          />
          <path
            d={path}
            fill="none"
            stroke="hsl(var(--primary))"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="4"
          />
        </svg>
      </div>
    </article>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border p-4">
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 text-sm capitalize">{value}</dd>
    </div>
  )
}

function HealthList({
  title,
  items,
  empty,
  icon: Icon,
}: {
  title: string
  items: string[]
  empty: string
  icon: typeof Activity
}) {
  return (
    <article className="rounded-2xl border bg-card p-5">
      <h2 className="flex items-center gap-2 font-semibold">
        <Icon className="size-4 text-primary" />
        {title}
      </h2>
      <div className="mt-4 space-y-2">
        {(items.length ? items : [empty]).map((item) => (
          <p
            className="rounded-xl bg-muted px-3 py-2.5 text-sm text-muted-foreground"
            key={item}
          >
            {item}
          </p>
        ))}
      </div>
    </article>
  )
}

function HealthLoading() {
  return (
    <div className="mx-auto grid max-w-7xl animate-pulse gap-4 p-8 md:grid-cols-3">
      {Array.from({ length: 9 }, (_, index) => (
        <div className="h-44 rounded-2xl bg-muted" key={index} />
      ))}
    </div>
  )
}
