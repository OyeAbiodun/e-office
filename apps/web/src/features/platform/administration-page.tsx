import { useQuery } from '@tanstack/react-query'
import { Navigate } from '@tanstack/react-router'
import {
  ArrowRight,
  Building2,
  Settings2,
  ShieldCheck,
  Plug,
  UserRoundCog,
} from 'lucide-react'

import { platformApi } from '@/features/platform/api'
import { useAuth } from '@/features/auth/auth-store'

const icons = {
  building: Building2,
  settings: Settings2,
  shield: ShieldCheck,
  plug: Plug,
  'user-cog': UserRoundCog,
}

export function AdministrationPage() {
  const { user } = useAuth()
  const menus = useQuery({
    queryKey: ['platform-menus'],
    queryFn: platformApi.menus,
  })
  const features = useQuery({
    queryKey: ['platform-features'],
    queryFn: platformApi.features,
  })
  const administration = (menus.data ?? []).filter(
    (item) =>
      item.parent_key === 'administration' && item.enabled && !item.hidden,
  )
  const enabledFeatures = (features.data ?? []).filter(
    (feature) => feature.enabled && !feature.hidden,
  ).length
  const maintenance = (features.data ?? []).filter(
    (feature) => feature.maintenance_mode,
  ).length
  if (!user?.roles.includes('Super Admin'))
    return <Navigate to="/unauthorized" />
  return (
    <div className="mx-auto max-w-7xl space-y-7 p-5 sm:p-8">
      <header>
        <p className="text-sm font-semibold text-primary">Super Admin</p>
        <h1 className="mt-1 text-3xl font-semibold">Administration</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Manage people, access, organization policy, and platform behavior from
          one protected workspace.
        </p>
      </header>
      <section className="grid gap-4 sm:grid-cols-3">
        <Metric label="Enabled modules" value={enabledFeatures} />
        <Metric label="Maintenance mode" value={maintenance} />
        <Metric label="Administrative tools" value={administration.length} />
      </section>
      {menus.isLoading ? (
        <div className="h-56 animate-pulse rounded-2xl bg-muted" />
      ) : menus.isError ? (
        <div
          className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6 text-red-600"
          role="alert"
        >
          Administration configuration could not be loaded.
        </div>
      ) : (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {administration.map((item) => {
            const Icon = icons[item.icon as keyof typeof icons] ?? Settings2
            return (
              <a
                className="group rounded-2xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
                href={item.path}
                key={item.key}
              >
                <span className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </span>
                <h2 className="mt-4 font-semibold">{item.label}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Permission: {item.permission}
                </p>
                <span className="mt-5 flex items-center gap-1 text-sm font-semibold text-primary">
                  Open{' '}
                  <ArrowRight className="size-4 transition group-hover:translate-x-1" />
                </span>
              </a>
            )
          })}
        </section>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <article className="rounded-2xl border bg-card p-5">
      <p className="text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-sm text-muted-foreground">{label}</p>
    </article>
  )
}
