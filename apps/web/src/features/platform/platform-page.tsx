import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, useNavigate } from '@tanstack/react-router'
import { motion } from 'framer-motion'
import {
  Activity,
  Boxes,
  BriefcaseBusiness,
  Building2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Download,
  Eye,
  FileClock,
  Flag,
  Gauge,
  GripVertical,
  LayoutDashboard,
  Menu,
  Palette,
  Plug,
  Save,
  Search,
  ServerCog,
  Settings2,
  ShieldCheck,
  RotateCcw,
  Upload,
  Workflow,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { useConfirmation } from '@/components/feedback/confirmation'
import { useAuth } from '@/features/auth/auth-store'
import { integrationApi } from '@/features/integrations/api'
import {
  platformApi,
  type ConfigurationEntry,
  type FeatureFlag as Feature,
} from '@/features/platform/api'
import { systemHealthApi } from '@/features/system-health/api'

type Section =
  | 'overview'
  | 'features'
  | 'modules'
  | 'runtime'
  | 'security'
  | 'branding'
  | 'connections'
  | 'scheduler'
  | 'workers'
  | 'licensing'
  | 'menus'
  | 'system'

const sections: Array<[Section, string, typeof LayoutDashboard]> = [
  ['overview', 'Platform Overview', LayoutDashboard],
  ['features', 'Feature Flags', Flag],
  ['modules', 'Module Registry', Boxes],
  ['runtime', 'Runtime Configuration', Settings2],
  ['security', 'Security', ShieldCheck],
  ['branding', 'Branding', Palette],
  ['connections', 'External Connections', Plug],
  ['scheduler', 'Scheduler', Clock3],
  ['workers', 'Workers', Workflow],
  ['licensing', 'Licensing', BriefcaseBusiness],
  ['menus', 'Menu Manager', Menu],
  ['system', 'System Modules', ServerCog],
]

const managedConfigurations: Record<
  Exclude<
    Section,
    'overview' | 'features' | 'modules' | 'connections' | 'menus' | 'system'
  >,
  {
    key: string
    category: string
    title: string
    description: string
    defaults: Record<string, string | number | boolean>
  }
> = {
  runtime: {
    key: 'application_runtime',
    category: 'runtime',
    title: 'Application runtime',
    description: 'Global request, upload, locale, and operational defaults.',
    defaults: {
      default_timezone: 'UTC',
      upload_limit_mb: 25,
      request_timeout_seconds: 30,
    },
  },
  security: {
    key: 'platform_security',
    category: 'security',
    title: 'Security policy',
    description: 'Session, password, and administrative access controls.',
    defaults: {
      session_minutes: 480,
      require_mfa_for_admins: false,
      password_history: 5,
    },
  },
  branding: {
    key: 'platform_branding',
    category: 'branding',
    title: 'MeetingHQ branding',
    description: 'Platform identity presented across tenant administration.',
    defaults: {
      product_name: 'MeetingHQ',
      support_url: '/help',
      accent_color: '#2563eb',
    },
  },
  scheduler: {
    key: 'scheduler_policy',
    category: 'scheduler',
    title: 'Scheduler policy',
    description: 'Control reminder polling and maintenance execution windows.',
    defaults: {
      reminder_poll_seconds: 30,
      maintenance_window: '02:00',
      timezone: 'UTC',
    },
  },
  workers: {
    key: 'worker_policy',
    category: 'workers',
    title: 'Worker policy',
    description: 'Background execution concurrency and retry behavior.',
    defaults: { concurrency: 4, max_retries: 3, retry_delay_seconds: 30 },
  },
  licensing: {
    key: 'platform_license',
    category: 'licensing',
    title: 'License allocation',
    description: 'Commercial entitlement and seat allocation metadata.',
    defaults: { plan: 'Enterprise', seats: 100, renewal_date: '2027-08-01' },
  },
}

export function PlatformPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const confirm = useConfirmation()
  const requested = new URLSearchParams(window.location.search).get('section')
  const [section, setSection] = useState<Section>(
    sections.some(([id]) => id === requested)
      ? (requested as Section)
      : 'overview',
  )
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('All')
  const [navOpen, setNavOpen] = useState(false)
  const client = useQueryClient()
  useEffect(() => {
    const next = sections.some(([id]) => id === requested)
      ? (requested as Section)
      : 'overview'
    if (next !== section) setSection(next)
  }, [requested, section])
  const selectSection = (next: Section) => {
    setSection(next)
    void navigate({
      to: '/platform',
      search: next === 'overview' ? {} : ({ section: next } as never),
    })
  }
  const features = useQuery({
    queryKey: ['platform-features'],
    queryFn: platformApi.features,
  })
  const menus = useQuery({
    queryKey: ['platform-menus'],
    queryFn: platformApi.menus,
  })
  const configuration = useQuery({
    queryKey: ['platform-configuration'],
    queryFn: platformApi.configuration,
  })
  const integrations = useQuery({
    queryKey: ['integrations'],
    queryFn: integrationApi.list,
  })
  const health = useQuery({
    queryKey: ['system-health'],
    queryFn: systemHealthApi.snapshot,
  })
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['platform-features'] }),
      client.invalidateQueries({ queryKey: ['platform-navigation'] }),
      client.invalidateQueries({ queryKey: ['integrations'] }),
    ])
  }
  const updateFeature = useMutation({
    mutationFn: ({
      key,
      body,
    }: {
      key: string
      body: Record<string, unknown>
    }) => platformApi.updateFeature(key, body),
    onSuccess: refresh,
  })
  const requestFeatureUpdate = async (
    key: string,
    body: Record<string, unknown>,
  ) => {
    if (
      body.enabled === false &&
      !(await confirm({
        title: 'Disable this capability?',
        description:
          'Users may immediately lose access to this capability. Existing data is retained and the capability can be enabled again.',
        confirmLabel: 'Disable capability',
        tone: 'danger',
      }))
    ) {
      return
    }
    updateFeature.mutate({ key, body })
  }
  const providerKeys = new Set(
    (integrations.data ?? []).map((provider) => provider.key),
  )
  const platformFeatures = (features.data ?? []).filter(
    (feature) => !providerKeys.has(feature.key),
  )
  const categories = [
    'All',
    ...new Set(
      platformFeatures.map((feature) =>
        feature.key.includes('calendar')
          ? 'Calendar'
          : feature.key.includes('meet') || feature.key === 'recordings'
            ? 'Meetings'
            : feature.key.includes('chat') || feature.key === 'teams'
              ? 'Collaboration'
              : 'Platform',
      ),
    ),
  ]
  const filteredFeatures = platformFeatures.filter((feature) => {
    const featureCategory = feature.key.includes('calendar')
      ? 'Calendar'
      : feature.key.includes('meet') || feature.key === 'recordings'
        ? 'Meetings'
        : feature.key.includes('chat') || feature.key === 'teams'
          ? 'Collaboration'
          : 'Platform'
    return (
      (category === 'All' || category === featureCategory) &&
      `${feature.name} ${feature.description ?? ''}`
        .toLowerCase()
        .includes(search.toLowerCase())
    )
  })
  if (!user?.roles.includes('Super Admin')) return <Navigate to="/forbidden" />
  const activeSection = sections.find(([id]) => id === section)
  return (
    <div className="mx-auto max-w-[1500px] space-y-6 p-5 sm:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Super Admin</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Platform Management
          </h1>
          <p className="mt-2 max-w-3xl text-muted-foreground">
            Govern MeetingHQ capabilities, runtime behavior, security, and
            commercial policy without changing application code.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border bg-card px-3 py-2">
          <span
            className={`size-2 rounded-full ${health.data?.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500'}`}
          />
          <span className="text-sm font-semibold">
            Platform {health.data?.status ?? 'checking'}
          </span>
        </div>
      </header>
      <button
        className="flex w-full items-center justify-between rounded-xl border bg-card p-3 text-sm font-semibold lg:hidden"
        onClick={() => setNavOpen((value) => !value)}
        type="button"
      >
        {activeSection?.[1]}
        <ChevronDown className="size-4" />
      </button>
      <div className="grid gap-6 lg:grid-cols-[250px_1fr]">
        <aside
          className={`${navOpen ? 'block' : 'hidden'} self-start rounded-2xl border bg-card p-2 lg:sticky lg:top-5 lg:block`}
        >
          <nav aria-label="Platform Management sections">
            {sections.map(([id, label, Icon]) => (
              <button
                className={`mb-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition ${section === id ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}
                key={id}
                onClick={() => {
                  selectSection(id)
                  setNavOpen(false)
                }}
                type="button"
              >
                <Icon className="size-4" />
                {label}
                {section === id && <ChevronRight className="ml-auto size-4" />}
              </button>
            ))}
          </nav>
        </aside>
        <motion.main
          animate={{ opacity: 1, y: 0 }}
          className="min-w-0 space-y-5"
          initial={{ opacity: 0, y: 8 }}
          key={section}
        >
          {section === 'overview' && (
            <Overview
              configurations={configuration.data ?? []}
              features={platformFeatures}
              health={health.data}
              integrations={integrations.data ?? []}
              menus={menus.data ?? []}
              onSelect={selectSection}
            />
          )}
          {(section === 'features' || section === 'modules') && (
            <>
              <SectionHeader
                description={
                  section === 'features'
                    ? 'Control availability, visibility, maintenance, and release stages.'
                    : 'Inspect installed modules, dependencies, versions, and operational state.'
                }
                title={
                  section === 'features' ? 'Feature Flags' : 'Module Registry'
                }
              />
              <FilterBar
                categories={categories}
                category={category}
                onCategory={setCategory}
                onSearch={setSearch}
                search={search}
              />
              <section className="grid gap-4 xl:grid-cols-2">
                {filteredFeatures.map((feature) => (
                  <FeatureCard
                    detailed={section === 'modules'}
                    feature={feature}
                    key={feature.key}
                    onUpdate={(body) =>
                      void requestFeatureUpdate(feature.key, body)
                    }
                    pending={
                      updateFeature.isPending &&
                      updateFeature.variables?.key === feature.key
                    }
                  />
                ))}
              </section>
            </>
          )}
          {section in managedConfigurations && (
            <ManagedConfiguration
              definition={
                managedConfigurations[
                  section as keyof typeof managedConfigurations
                ]
              }
              entries={(configuration.data ?? []).filter(
                (entry) => entry.category !== 'integrations',
              )}
            />
          )}
          {section === 'connections' && (
            <ExternalConnections
              onToggle={(provider, enabled) =>
                void requestFeatureUpdate(provider, { enabled })
              }
              pendingKey={
                updateFeature.isPending
                  ? updateFeature.variables?.key
                  : undefined
              }
              providers={integrations.data ?? []}
            />
          )}
          {section === 'menus' && (
            <MenuManager
              items={menus.data ?? []}
              onPublished={() =>
                Promise.all([
                  client.invalidateQueries({ queryKey: ['platform-menus'] }),
                  client.invalidateQueries({
                    queryKey: ['platform-navigation'],
                  }),
                ])
              }
            />
          )}
          {section === 'system' && <SystemModules />}
        </motion.main>
      </div>
    </div>
  )
}

function Overview({
  features,
  integrations,
  configurations,
  menus,
  health,
  onSelect,
}: {
  features: Feature[]
  integrations: Awaited<ReturnType<typeof integrationApi.list>>
  configurations: ConfigurationEntry[]
  menus: Awaited<ReturnType<typeof platformApi.menus>>
  health: Awaited<ReturnType<typeof systemHealthApi.snapshot>> | undefined
  onSelect: (section: Section) => void
}) {
  const metrics = [
    [
      'Enabled capabilities',
      features.filter((item) => item.enabled).length,
      Gauge,
    ],
    [
      'Configured connections',
      integrations.filter((item) => item.configured).length,
      Plug,
    ],
    [
      'Runtime policies',
      configurations.filter((item) => item.category !== 'integrations').length,
      Settings2,
    ],
    [
      'Visible navigation',
      menus.filter((item) => item.enabled && !item.hidden).length,
      Menu,
    ],
  ] as const
  return (
    <>
      <SectionHeader
        description="A live command view of platform capability, health, configuration, and risk."
        title="Platform Overview"
      />
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(([label, value, Icon]) => (
          <article className="rounded-2xl border bg-card p-5" key={label}>
            <div className="flex items-center justify-between">
              <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
                <Icon className="size-5" />
              </span>
              <span className="text-2xl font-semibold">{value}</span>
            </div>
            <p className="mt-4 text-sm font-medium">{label}</p>
          </article>
        ))}
      </section>
      <section className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
        <article className="rounded-2xl border bg-card p-5">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="font-semibold">Platform health</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Live runtime assessment from System Health.
              </p>
            </div>
            <span className="text-3xl font-semibold text-primary">
              {health?.score ?? '—'}%
            </span>
          </div>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${health?.score ?? 0}%` }}
            />
          </div>
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {health?.components.slice(0, 6).map((component) => (
              <div
                className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2 text-sm"
                key={component.key}
              >
                <span>{component.name}</span>
                <span
                  className={`text-xs font-semibold capitalize ${component.status === 'healthy' ? 'text-emerald-600' : 'text-amber-600'}`}
                >
                  {component.status.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
          <a
            className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-primary"
            href="/system-health"
          >
            Open System Health <ChevronRight className="size-4" />
          </a>
        </article>
        <article className="rounded-2xl border bg-card p-5">
          <h2 className="font-semibold">Quick actions</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Move directly to high-frequency governance tasks.
          </p>
          <div className="mt-4 space-y-2">
            {(
              [
                ['Review feature flags', 'features', Flag],
                ['Manage connections', 'connections', Plug],
                ['Update security policy', 'security', ShieldCheck],
                ['Inspect module registry', 'modules', Boxes],
              ] as const
            ).map(([label, destination, Icon]) => (
              <button
                className="flex w-full items-center gap-3 rounded-xl border p-3 text-left text-sm font-semibold hover:border-primary/30 hover:bg-muted/30"
                key={destination}
                onClick={() => onSelect(destination)}
                type="button"
              >
                <Icon className="size-4 text-primary" />
                {label}
                <ChevronRight className="ml-auto size-4 text-muted-foreground" />
              </button>
            ))}
          </div>
        </article>
      </section>
    </>
  )
}

function FeatureCard({
  feature,
  onUpdate,
  pending,
  detailed,
}: {
  feature: Feature
  onUpdate: (body: Record<string, unknown>) => void
  pending: boolean
  detailed: boolean
}) {
  const comingSoon = feature.availability_status === 'coming_soon'
  return (
    <article className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            System module
            {feature.planned_version ? ` · v${feature.planned_version}` : ''}
          </p>
          <h2 className="mt-1 text-lg font-semibold">{feature.name}</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {feature.description}
          </p>
        </div>
        <CapabilityStatus status={feature.availability_status} />
      </div>
      <p className="mt-3 rounded-xl bg-muted/45 px-3 py-2 text-xs text-muted-foreground">
        {feature.implementation_status}
      </p>
      {detailed && (
        <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-muted/40 p-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Health</p>
            <p className="mt-1 font-semibold">
              {feature.maintenance_mode ? 'Maintenance' : 'Healthy'}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Dependencies</p>
            <p className="mt-1 font-semibold capitalize">
              {feature.dependencies.join(', ') || 'None'}
            </p>
          </div>
        </div>
      )}
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <Toggle
          checked={feature.enabled}
          disabled={comingSoon || !feature.installed}
          label="Enabled"
          onChange={(checked) => onUpdate({ enabled: checked })}
        />
        <Toggle
          checked={!feature.hidden}
          disabled={comingSoon || !feature.installed}
          label="Visible"
          onChange={(checked) => onUpdate({ hidden: !checked })}
        />
        <Toggle
          checked={feature.maintenance_mode}
          disabled={comingSoon || !feature.installed}
          label="Maintenance"
          onChange={(checked) => onUpdate({ maintenance_mode: checked })}
        />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t pt-4">
        <select
          aria-label={`${feature.name} release stage`}
          className="h-9 rounded-lg border bg-background px-2 text-sm"
          disabled={pending || comingSoon || !feature.installed}
          onChange={(event) => onUpdate({ release_stage: event.target.value })}
          value={feature.release_stage}
        >
          <option value="internal">Internal</option>
          <option value="beta">Beta</option>
          <option value="public">Production</option>
        </select>
        {comingSoon ? (
          <span className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-700">
            Coming Soon · {feature.estimated_availability ?? 'Date pending'}
          </span>
        ) : (
          feature.navigation_path && (
            <a
              className="rounded-lg border px-3 py-2 text-xs font-semibold"
              href={feature.navigation_path}
            >
              Open module
            </a>
          )
        )}
        <a
          className="rounded-lg border px-3 py-2 text-xs font-semibold"
          href={`/audit?search=${encodeURIComponent(feature.key)}`}
        >
          Audit history
        </a>
      </div>
    </article>
  )
}

function ExternalConnections({
  providers,
  onToggle,
  pendingKey,
}: {
  providers: Awaited<ReturnType<typeof integrationApi.list>>
  onToggle: (key: string, enabled: boolean) => void
  pendingKey?: string
}) {
  return (
    <>
      <SectionHeader
        description="Control provider availability here. Credentials and connection settings remain isolated in Integration Center."
        title="External Connections"
      />
      <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4 text-sm text-muted-foreground">
        <strong className="text-foreground">Clear responsibility:</strong>{' '}
        Platform Management enables capabilities; Integration Center configures
        providers.
      </div>
      <section className="grid gap-4 xl:grid-cols-2">
        {providers.map((provider) => (
          <article
            className="flex flex-col gap-4 rounded-2xl border bg-card p-5 sm:flex-row sm:items-center"
            key={provider.key}
          >
            <div className="grid size-12 shrink-0 place-items-center rounded-2xl bg-primary/10 text-lg font-bold text-primary">
              {provider.name
                .split(' ')
                .map((word) => word[0])
                .join('')
                .slice(0, 2)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {provider.category}
              </p>
              <h2 className="font-semibold">{provider.name}</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {provider.configured ? 'Configured' : 'Configuration required'}{' '}
                · Health: {provider.health}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Toggle
                checked={provider.enabled}
                disabled={pendingKey === provider.key}
                label={provider.enabled ? 'Enabled' : 'Disabled'}
                onChange={(checked) => onToggle(provider.key, checked)}
              />
              <a
                className="rounded-xl border px-3 py-2 text-sm font-semibold"
                href={`/integrations?provider=${provider.key}`}
              >
                Configure
              </a>
            </div>
          </article>
        ))}
      </section>
    </>
  )
}

function ManagedConfiguration({
  definition,
  entries,
}: {
  definition: (typeof managedConfigurations)[keyof typeof managedConfigurations]
  entries: ConfigurationEntry[]
}) {
  const client = useQueryClient()
  const existing = entries.find((entry) => entry.key === definition.key)
  const [values, setValues] = useState<
    Record<string, string | number | boolean>
  >(
    (existing?.value as Record<string, string | number | boolean>) ??
      definition.defaults,
  )
  const save = useMutation({
    mutationFn: () =>
      platformApi.setConfiguration(definition.key, {
        category: definition.category,
        value: values,
      }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ['platform-configuration'] }),
  })
  return (
    <>
      <SectionHeader
        description={definition.description}
        title={definition.title}
      />
      <form
        className="rounded-2xl border bg-card p-5"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          {Object.entries(values).map(([key, value]) => (
            <label className="block text-sm font-medium capitalize" key={key}>
              {key.replaceAll('_', ' ')}
              {typeof value === 'boolean' ? (
                <span className="mt-2 flex h-11 items-center rounded-xl border bg-background px-3">
                  <Toggle
                    checked={value}
                    label={value ? 'Enabled' : 'Disabled'}
                    onChange={(checked) =>
                      setValues((current) => ({ ...current, [key]: checked }))
                    }
                  />
                </span>
              ) : (
                <input
                  className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      [key]:
                        typeof value === 'number'
                          ? Number(event.target.value)
                          : event.target.value,
                    }))
                  }
                  type={typeof value === 'number' ? 'number' : 'text'}
                  value={String(value)}
                />
              )}
            </label>
          ))}
        </div>
        <button
          className="mt-6 flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={save.isPending}
          type="submit"
        >
          <Save className="size-4" />
          {save.isPending ? 'Saving…' : 'Save policy'}
        </button>
      </form>
    </>
  )
}

function MenuManager({
  items,
  onPublished,
}: {
  items: Awaited<ReturnType<typeof platformApi.menus>>
  onPublished: () => Promise<unknown>
}) {
  const confirm = useConfirmation()
  const [expanded, setExpanded] = useState<string | null>(null)
  const [draft, setDraft] = useState(items)
  const [dirty, setDirty] = useState(false)
  const [preview, setPreview] = useState(false)
  const [dragging, setDragging] = useState<string | null>(null)
  useEffect(() => {
    if (!dirty) setDraft(items)
  }, [dirty, items])
  const publish = useMutation({
    mutationFn: () => platformApi.publishMenus(draft),
    onSuccess: async () => {
      setDirty(false)
      await onPublished()
    },
  })
  const reset = useMutation({
    mutationFn: platformApi.resetMenus,
    onSuccess: async (result) => {
      setDraft(result)
      setDirty(false)
      await onPublished()
    },
  })
  const update = (
    key: string,
    body: Partial<(typeof draft)[number]>,
  ) => {
    setDraft((current) =>
      current.map((item) => (item.key === key ? { ...item, ...body } : item)),
    )
    setDirty(true)
  }
  const reorder = (source: string, target: string) => {
    if (source === target) return
    setDraft((current) => {
      const next = [...current]
      const sourceIndex = next.findIndex((item) => item.key === source)
      const targetIndex = next.findIndex((item) => item.key === target)
      if (sourceIndex < 0 || targetIndex < 0) return current
      const [moved] = next.splice(sourceIndex, 1)
      if (!moved) return current
      next.splice(targetIndex, 0, moved)
      return next.map((item, position) => ({ ...item, position }))
    })
    setDirty(true)
  }
  const sort = (mode: 'alphabetical' | 'priority') => {
    setDraft((current) =>
      [...current]
        .sort((left, right) =>
          mode === 'alphabetical'
            ? left.label.localeCompare(right.label)
            : left.position - right.position,
        )
        .map((item, position) => ({ ...item, position })),
    )
    setDirty(true)
  }
  const exportConfiguration = async () => {
    const payload = await platformApi.exportMenus()
    const link = document.createElement('a')
    link.href = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      }),
    )
    link.download = `meetinghq-navigation-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(link.href)
  }
  const importConfiguration = async (file: File) => {
    const payload = JSON.parse(await file.text()) as {
      items?: typeof draft
    }
    if (!Array.isArray(payload.items)) throw new Error('Invalid menu export')
    const imported = await platformApi.previewMenus(payload.items)
    setDraft(imported)
    setDirty(true)
  }
  return (
    <>
      <SectionHeader
        description="Stage, preview, and publish permission-aware navigation. Published changes update every active shell immediately."
        title="Menu Manager"
      />
      <div className="flex flex-wrap items-center gap-2 rounded-2xl border bg-card p-4">
        <button
          className="rounded-xl border px-3 py-2 text-sm font-semibold"
          onClick={() => sort('alphabetical')}
          type="button"
        >
          A–Z sort
        </button>
        <button
          className="rounded-xl border px-3 py-2 text-sm font-semibold"
          onClick={() => sort('priority')}
          type="button"
        >
          Priority sort
        </button>
        <button
          className="flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold"
          onClick={() => setPreview((value) => !value)}
          type="button"
        >
          <Eye className="size-4" />
          {preview ? 'Close preview' : 'Preview'}
        </button>
        <button
          className="flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold"
          onClick={() => void exportConfiguration()}
          type="button"
        >
          <Download className="size-4" />
          Export
        </button>
        <label className="flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold">
          <Upload className="size-4" />
          Import
          <input
            accept="application/json"
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void importConfiguration(file)
            }}
            type="file"
          />
        </label>
        <button
          className="flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold"
          onClick={() =>
            void (async () => {
              if (
                await confirm({
                  title: 'Reset navigation defaults?',
                  description:
                    'Custom labels, groups, order, badges, and visibility will be replaced by the MeetingHQ defaults.',
                  confirmLabel: 'Reset defaults',
                  tone: 'danger',
                })
              )
                reset.mutate()
            })()
          }
          type="button"
        >
          <RotateCcw className="size-4" />
          Reset defaults
        </button>
        <button
          className="ml-auto flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={!dirty || publish.isPending}
          onClick={() => publish.mutate()}
          type="button"
        >
          <Save className="size-4" />
          {publish.isPending ? 'Publishing…' : 'Publish navigation'}
        </button>
      </div>
      {preview && (
        <aside className="rounded-2xl border border-primary/20 bg-sidebar p-4 text-sidebar-foreground">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Navigation preview
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[...new Set(draft.map((item) => item.section))].map((section) => (
              <div className="space-y-1" key={section}>
                <p className="px-2 text-[11px] font-semibold uppercase text-muted-foreground">
                  {section}
                </p>
                {draft
                  .filter(
                    (item) =>
                      item.section === section &&
                      item.enabled &&
                      !item.hidden,
                  )
                  .sort((left, right) => left.position - right.position)
                  .map((item) => (
                    <div
                      className="rounded-lg px-2 py-1.5 text-sm"
                      key={item.key}
                    >
                      {item.parent_key ? '↳ ' : ''}
                      {item.label}
                      {item.badge ? ` · ${item.badge}` : ''}
                    </div>
                  ))}
              </div>
            ))}
          </div>
        </aside>
      )}
      <section className="grid gap-3">
        {draft.map((item) => (
          <article
            className="rounded-2xl border bg-card"
            draggable
            key={item.key}
            onDragEnd={() => setDragging(null)}
            onDragOver={(event) => event.preventDefault()}
            onDragStart={() => setDragging(item.key)}
            onDrop={() => {
              if (dragging) reorder(dragging, item.key)
            }}
          >
            <button
              className="flex w-full items-center gap-4 p-4 text-left"
              onClick={() =>
                setExpanded((current) =>
                  current === item.key ? null : item.key,
                )
              }
              type="button"
            >
              <GripVertical className="size-4 cursor-grab text-muted-foreground" />
              <span className="grid size-10 place-items-center rounded-xl bg-muted">
                <Menu className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-semibold">{item.label}</span>
                <span className="text-xs text-muted-foreground">
                  {item.path} · {item.section}
                </span>
              </span>
              <Status enabled={item.enabled && !item.hidden} />
              <ChevronDown
                className={`size-4 transition ${expanded === item.key ? 'rotate-180' : ''}`}
              />
            </button>
            {expanded === item.key && (
              <div className="grid gap-4 border-t p-4 sm:grid-cols-2 xl:grid-cols-4">
                <label className="text-sm font-medium">
                  Label
                  <input
                    className="mt-2 h-10 w-full rounded-xl border bg-background px-3"
                    onChange={(event) =>
                      update(item.key, { label: event.target.value })
                    }
                    value={item.label}
                  />
                </label>
                <label className="text-sm font-medium">
                  Group / section
                  <input
                    className="mt-2 h-10 w-full rounded-xl border bg-background px-3"
                    onChange={(event) =>
                      update(item.key, { section: event.target.value })
                    }
                    value={item.section}
                  />
                </label>
                <label className="text-sm font-medium">
                  Parent menu
                  <select
                    className="mt-2 h-10 w-full rounded-xl border bg-background px-3"
                    onChange={(event) =>
                      update(item.key, {
                        parent_key: event.target.value || null,
                      })
                    }
                    value={item.parent_key ?? ''}
                  >
                    <option value="">Top level</option>
                    {draft
                      .filter((candidate) => candidate.key !== item.key)
                      .map((candidate) => (
                        <option key={candidate.key} value={candidate.key}>
                          {candidate.label}
                        </option>
                      ))}
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Icon
                  <input
                    className="mt-2 h-10 w-full rounded-xl border bg-background px-3"
                    onChange={(event) =>
                      update(item.key, { icon: event.target.value })
                    }
                    value={item.icon}
                  />
                </label>
                <label className="text-sm font-medium">
                  Badge
                  <input
                    className="mt-2 h-10 w-full rounded-xl border bg-background px-3"
                    onChange={(event) =>
                      update(item.key, { badge: event.target.value || null })
                    }
                    placeholder="Optional"
                    value={item.badge ?? ''}
                  />
                </label>
                <label className="text-sm font-medium">
                  Permission
                  <input
                    className="mt-2 h-10 w-full rounded-xl border bg-background px-3"
                    onChange={(event) =>
                      update(item.key, { permission: event.target.value })
                    }
                    value={item.permission}
                  />
                </label>
                <Toggle
                  checked={item.enabled}
                  label="Enabled"
                  onChange={(checked) => update(item.key, { enabled: checked })}
                />
                <Toggle
                  checked={!item.hidden}
                  label="Visible"
                  onChange={(checked) => update(item.key, { hidden: !checked })}
                />
              </div>
            )}
          </article>
        ))}
      </section>
    </>
  )
}

function SystemModules() {
  const modules = [
    [
      'System Health',
      'Live services, providers, queues, storage, and runtime score.',
      '/system-health',
      Activity,
    ],
    [
      'Audit Center',
      'Immutable security, configuration, and administration history.',
      '/audit',
      FileClock,
    ],
    [
      'Integration Center',
      'Protected external provider configuration and credentials.',
      '/integrations',
      Plug,
    ],
    [
      'Help Center',
      'Knowledge, handbooks, deployment guidance, and page-level help.',
      '/help',
      Building2,
    ],
  ] as const
  return (
    <>
      <SectionHeader
        description="Protected operational centers installed with MeetingHQ."
        title="System Modules"
      />
      <section className="grid gap-4 md:grid-cols-2">
        {modules.map(([name, description, path, Icon]) => (
          <a
            className="group rounded-2xl border bg-card p-5 transition hover:border-primary/30 hover:shadow-md"
            href={path}
            key={path}
          >
            <span className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
              <Icon className="size-5" />
            </span>
            <h2 className="mt-4 font-semibold">{name}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{description}</p>
            <span className="mt-5 flex items-center gap-1 text-sm font-semibold text-primary">
              Open module{' '}
              <ChevronRight className="size-4 transition group-hover:translate-x-1" />
            </span>
          </a>
        ))}
      </section>
    </>
  )
}

function FilterBar({
  search,
  onSearch,
  categories,
  category,
  onCategory,
}: {
  search: string
  onSearch: (value: string) => void
  categories: string[]
  category: string
  onCategory: (value: string) => void
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border bg-card p-4 sm:flex-row">
      <label className="relative flex-1">
        <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
        <input
          aria-label="Search platform capabilities"
          className="h-10 w-full rounded-xl border bg-background pl-10 pr-3 text-sm"
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search capabilities"
          value={search}
        />
      </label>
      <select
        aria-label="Filter platform capabilities"
        className="h-10 rounded-xl border bg-background px-3 text-sm"
        onChange={(event) => onCategory(event.target.value)}
        value={category}
      >
        {categories.map((item) => (
          <option key={item}>{item}</option>
        ))}
      </select>
    </div>
  )
}

function Toggle({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <label className="flex items-center gap-2 text-xs font-semibold">
      <button
        aria-label={label}
        aria-pressed={checked}
        className={`relative h-6 w-11 rounded-full transition ${checked ? 'bg-primary' : 'bg-muted'}`}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        type="button"
      >
        <span
          className={`absolute top-1 size-4 rounded-full bg-white shadow transition ${checked ? 'left-6' : 'left-1'}`}
        />
      </button>
      <span>{label}</span>
    </label>
  )
}

function Status({ enabled }: { enabled: boolean }) {
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${enabled ? 'bg-emerald-500/10 text-emerald-700' : 'bg-muted text-muted-foreground'}`}
    >
      {enabled ? 'Enabled' : 'Disabled'}
    </span>
  )
}

function CapabilityStatus({
  status,
}: {
  status: Feature['availability_status']
}) {
  const labels: Record<Feature['availability_status'], string> = {
    available: 'Available',
    beta: 'Beta',
    preview: 'Preview',
    coming_soon: 'Coming Soon',
    deprecated: 'Deprecated',
    disabled: 'Disabled',
  }
  const tones: Record<Feature['availability_status'], string> = {
    available: 'bg-emerald-500/10 text-emerald-700',
    beta: 'bg-blue-500/10 text-blue-700',
    preview: 'bg-violet-500/10 text-violet-700',
    coming_soon: 'bg-amber-500/10 text-amber-700',
    deprecated: 'bg-red-500/10 text-red-700',
    disabled: 'bg-muted text-muted-foreground',
  }
  return (
    <span
      className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${tones[status]}`}
    >
      {labels[status]}
    </span>
  )
}

function SectionHeader({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <header>
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
        {description}
      </p>
    </header>
  )
}
