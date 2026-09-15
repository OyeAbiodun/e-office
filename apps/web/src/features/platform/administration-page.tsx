import { useQuery } from '@tanstack/react-query'
import { Link, Navigate } from '@tanstack/react-router'
import {
  Activity,
  ArrowRight,
  Building2,
  FileClock,
  HeartPulse,
  Mail,
  Menu,
  Plug,
  Settings2,
  ShieldCheck,
  UserRoundCog,
  Users,
  type LucideIcon,
} from 'lucide-react'

import {
  EmptyState,
  ErrorState,
  LoadingState,
  MetricLink,
  Page,
  PageHeader,
  Surface,
} from '@/components/page'
import { useAuth } from '@/features/auth/auth-store'
import { platformApi, type MenuDefinition } from '@/features/platform/api'

const icons: Record<string, LucideIcon> = {
  activity: Activity,
  building: Building2,
  'file-clock': FileClock,
  mail: Mail,
  plug: Plug,
  settings: Settings2,
  shield: ShieldCheck,
  'user-cog': UserRoundCog,
  users: Users,
}

const descriptions: Record<string, string> = {
  users: 'Provision accounts, employment access, and user lifecycle.',
  roles: 'Define roles and govern permission assignments.',
  platform: 'Control capabilities, menus, environments, and releases.',
  'organization-settings':
    'Manage organization identity, defaults, and policy.',
  health: 'Review service health, dependencies, and recovery guidance.',
  audit: 'Investigate immutable security and administration history.',
  integrations: 'Configure connected providers and verify their health.',
}

const groups = [
  {
    title: 'People & access',
    description: 'Identity, structure, and authorization.',
    keys: ['users', 'roles', 'organization-settings'],
  },
  {
    title: 'Platform & services',
    description: 'Capabilities, navigation, providers, and delivery.',
    keys: ['platform', 'integrations'],
  },
  {
    title: 'Trust & operations',
    description: 'Health, traceability, and operational confidence.',
    keys: ['health', 'audit'],
  },
] as const

const administrationPermissions = new Set([
  'admin.manage',
  'users.manage',
  'roles.manage',
  'organizations.manage',
])

export function AdministrationPage() {
  const { user } = useAuth()
  const permissions = new Set(user?.permissions ?? [])
  const canAccess = [...administrationPermissions].some((permission) =>
    permissions.has(permission),
  )
  const navigation = useQuery({
    queryKey: ['platform-navigation'],
    queryFn: platformApi.navigation,
    enabled: canAccess,
  })
  const features = useQuery({
    queryKey: ['platform-features'],
    queryFn: platformApi.features,
    enabled: permissions.has('admin.manage'),
  })

  if (!canAccess) return <Navigate to="/unauthorized" />

  const administration = (navigation.data ?? []).filter(
    (item) => item.parent_key === 'administration',
  )
  const available = (features.data ?? []).filter(
    (feature) => feature.enabled && !feature.hidden,
  ).length
  const attention = (features.data ?? []).filter(
    (feature) => feature.maintenance_mode || !feature.enabled,
  ).length

  return (
    <Page className="space-y-7">
      <PageHeader
        eyebrow="Control center"
        title="Administration"
        description="Manage people, access, connected services, and operational health from one permission-aware workspace."
      />

      {features.data && (
        <section
          aria-label="Administration summary"
          className="grid gap-3 sm:grid-cols-3"
        >
          <MetricLink
            label="Available capabilities"
            value={available}
            detail="Enabled for this organization"
            to="/platform"
            icon={Settings2}
            tone="success"
          />
          <MetricLink
            label="Needs attention"
            value={attention}
            detail="Disabled or in maintenance"
            to="/platform"
            icon={HeartPulse}
            tone={attention ? 'warning' : 'success'}
          />
          <MetricLink
            label="Authorized tools"
            value={administration.length}
            detail="Based on your current access"
            to="/roles"
            icon={ShieldCheck}
          />
        </section>
      )}

      {navigation.isLoading ? (
        <LoadingState label="Loading administration" />
      ) : navigation.isError ? (
        <ErrorState
          title="Administration is temporarily unavailable"
          description="The navigation registry could not be loaded. Try again without leaving this page."
          onRetry={() => void navigation.refetch()}
        />
      ) : administration.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="No administration tools assigned"
          description="Your account can open the control center, but no administrative destinations are currently permitted."
        />
      ) : (
        <div className="grid gap-5 xl:grid-cols-3">
          {groups.map((group) => {
            const items = group.keys
              .map((key) => administration.find((item) => item.key === key))
              .filter((item): item is MenuDefinition => Boolean(item))
            if (!items.length) return null
            return (
              <Surface className="overflow-hidden" key={group.title}>
                <div className="border-b bg-muted/35 px-5 py-4">
                  <h2 className="font-semibold">{group.title}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {group.description}
                  </p>
                </div>
                <nav aria-label={group.title} className="divide-y">
                  {items.map((item) => (
                    <AdminLink item={item} key={item.key} />
                  ))}
                </nav>
              </Surface>
            )
          })}
        </div>
      )}

      <Surface className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold">Need operational context?</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Review recent administrative changes or open Help & Support for
            administrator guidance.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {administration.some((item) => item.key === 'audit') && (
            <Link className="button-secondary" to="/audit">
              <FileClock className="size-4" /> Recent activity
            </Link>
          )}
          <Link className="button-secondary" to="/help">
            Administrator handbook <ArrowRight className="size-4" />
          </Link>
        </div>
      </Surface>
    </Page>
  )
}

function AdminLink({ item }: { item: MenuDefinition }) {
  const Icon = icons[item.icon] ?? Menu
  return (
    <Link
      className="group flex min-h-24 items-center gap-4 p-5 transition hover:bg-muted/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
      to={item.path as never}
    >
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-subtle text-primary">
        <Icon aria-hidden="true" className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{item.label}</span>
        <span className="mt-1 block text-sm leading-5 text-muted-foreground">
          {descriptions[item.key] ?? 'Open this administration workspace.'}
        </span>
      </span>
      <ArrowRight
        aria-hidden="true"
        className="size-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary"
      />
    </Link>
  )
}
