import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate } from '@tanstack/react-router'
import {
  CheckCircle2,
  CircleAlert,
  Plug,
  RefreshCw,
  ScrollText,
  Search,
  Send,
  Server,
  Settings2,
  ShieldCheck,
  TestTube2,
  Unplug,
  X,
} from 'lucide-react'
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useMemo,
  useEffect,
  useState,
} from 'react'
import { z } from 'zod'

import { useAuth } from '@/features/auth/auth-store'
import { notify } from '@/components/feedback/events'
import { ProviderLogo } from '@/components/provider-logo'
import {
  integrationApi,
  type IntegrationProvider,
  type IntegrationTestResult,
  type SmtpConfiguration,
  type SmtpConfigurationUpdate,
} from '@/features/integrations/api'

interface FieldDefinition {
  key: string
  label: string
  secret?: boolean
  placeholder: string
}

const fallbackFields: FieldDefinition[] = [
  {
    key: 'base_url',
    label: 'Base URL',
    placeholder: 'https://api.example.com',
  },
  {
    key: 'token',
    label: 'Access token',
    placeholder: 'Credential',
    secret: true,
  },
]

const fieldsByType: Record<string, FieldDefinition[]> = {
  oauth: [
    {
      key: 'client_id',
      label: 'Client ID',
      placeholder: 'Application client ID',
    },
    {
      key: 'client_secret',
      label: 'Client secret',
      placeholder: 'Enter provider secret',
      secret: true,
    },
    {
      key: 'tenant',
      label: 'Tenant or domain',
      placeholder: 'contoso.onmicrosoft.com',
    },
  ],
  smtp: [
    { key: 'host', label: 'SMTP host', placeholder: 'smtp.example.com' },
    { key: 'port', label: 'Port', placeholder: '587' },
    {
      key: 'username',
      label: 'Username',
      placeholder: 'mailer@example.com',
    },
    {
      key: 'password',
      label: 'Password',
      placeholder: 'Enter account password',
      secret: true,
    },
  ],
  imap: [
    { key: 'host', label: 'IMAP host', placeholder: 'imap.example.com' },
    { key: 'port', label: 'Port', placeholder: '993' },
    {
      key: 'username',
      label: 'Username',
      placeholder: 'mailbox@example.com',
    },
    {
      key: 'password',
      label: 'Password',
      placeholder: 'Enter account password',
      secret: true,
    },
  ],
  caldav: [
    {
      key: 'server_url',
      label: 'CalDAV URL',
      placeholder: 'https://caldav.example.com',
    },
    {
      key: 'username',
      label: 'Username',
      placeholder: 'calendar@example.com',
    },
    {
      key: 'app_password',
      label: 'App password',
      placeholder: 'Enter app password',
      secret: true,
    },
  ],
  storage: [
    {
      key: 'endpoint',
      label: 'Service endpoint',
      placeholder: 'https://storage.example.com',
    },
    {
      key: 'container',
      label: 'Bucket or container',
      placeholder: 'meetinghq-files',
    },
    {
      key: 'access_key',
      label: 'Access key',
      placeholder: 'Access key ID',
    },
    {
      key: 'secret_key',
      label: 'Secret key',
      placeholder: 'Enter secret key',
      secret: true,
    },
  ],
  api_key: [
    {
      key: 'endpoint',
      label: 'API endpoint',
      placeholder: 'Provider API endpoint',
    },
    {
      key: 'model',
      label: 'Default model',
      placeholder: 'Model deployment or name',
    },
    {
      key: 'api_key',
      label: 'API key',
      placeholder: 'Enter API key',
      secret: true,
    },
  ],
  token: fallbackFields,
  webhook: [
    {
      key: 'endpoint',
      label: 'Webhook endpoint',
      placeholder: 'https://example.com/hooks/meetinghq',
    },
    {
      key: 'signing_secret',
      label: 'Signing secret',
      placeholder: 'Enter signing secret',
      secret: true,
    },
  ],
}

export function IntegrationCenterPage() {
  const { user } = useAuth()
  const client = useQueryClient()
  const requested = new URLSearchParams(window.location.search).get('provider')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('All')
  const [selectedKey, setSelectedKey] = useState<string | null>(requested)
  const providers = useQuery({
    queryKey: ['integrations'],
    queryFn: integrationApi.list,
  })
  const selected = providers.data?.find((item) => item.key === selectedKey)
  const categories = useMemo(
    () => [
      'All',
      ...new Set((providers.data ?? []).map((item) => item.category)),
    ],
    [providers.data],
  )
  const filtered = (providers.data ?? []).filter(
    (item) =>
      (category === 'All' || item.category === category) &&
      `${item.name} ${item.description}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  )
  const refresh = () => client.invalidateQueries({ queryKey: ['integrations'] })
  const disconnect = useMutation({
    mutationFn: integrationApi.disconnect,
    onSuccess: refresh,
  })
  if (!user?.permissions.includes('integrations.view'))
    return <Navigate to="/forbidden" />
  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-5 sm:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Administration</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Integration Center
          </h1>
          <p className="mt-2 max-w-3xl text-muted-foreground">
            Authenticate, configure, test, and monitor external providers in one
            protected credential boundary.
          </p>
        </div>
        <a
          className="rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold"
          href="/platform?section=connections"
        >
          Manage availability
        </a>
      </header>
      <section className="grid gap-4 sm:grid-cols-3">
        <Metric
          label="Available providers"
          value={providers.data?.length ?? 0}
        />
        <Metric
          label="Enabled"
          value={providers.data?.filter((item) => item.enabled).length ?? 0}
        />
        <Metric
          label="Configured"
          value={providers.data?.filter((item) => item.configured).length ?? 0}
        />
        <Metric
          label="Validated connections"
          value={providers.data?.filter((item) => item.validated).length ?? 0}
        />
      </section>
      <section className="flex flex-col gap-3 rounded-2xl border bg-card p-4 sm:flex-row">
        <label className="relative flex-1">
          <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
          <input
            aria-label="Search integrations"
            className="h-10 w-full rounded-xl border bg-background pl-10 pr-3 text-sm"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search providers"
            value={search}
          />
        </label>
        <select
          aria-label="Filter integrations by category"
          className="h-10 rounded-xl border bg-background px-3 text-sm"
          onChange={(event) => setCategory(event.target.value)}
          value={category}
        >
          {categories.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </section>
      {providers.isLoading ? (
        <div className="grid animate-pulse gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 9 }, (_, index) => (
            <div className="h-56 rounded-2xl bg-muted" key={index} />
          ))}
        </div>
      ) : providers.isError ? (
        <div
          className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6 text-red-600"
          role="alert"
        >
          Integration providers could not be loaded.
        </div>
      ) : (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((provider) => (
            <ProviderCard
              key={provider.key}
              onConfigure={() => setSelectedKey(provider.key)}
              provider={provider}
            />
          ))}
        </section>
      )}
      {selected?.key === 'smtp' ? (
        <SmtpConfigurationPanel
          onClose={() => setSelectedKey(null)}
          provider={selected}
        />
      ) : selected ? (
        <ConfigurationPanel
          disconnecting={disconnect.isPending}
          onClose={() => setSelectedKey(null)}
          onDisconnect={() => disconnect.mutate(selected.key)}
          provider={selected}
        />
      ) : null}
    </div>
  )
}

function ProviderCard({
  provider,
  onConfigure,
}: {
  provider: IntegrationProvider
  onConfigure: () => void
}) {
  return (
    <article className="rounded-2xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="grid size-12 place-items-center rounded-2xl bg-primary/10 text-primary">
          <ProviderLogo className="size-7" provider={provider.key} />
        </div>
        <HealthBadge health={provider.health} />
      </div>
      <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {provider.category}
      </p>
      <h2 className="mt-1 text-lg font-semibold">{provider.name}</h2>
      <p className="mt-2 min-h-10 text-sm text-muted-foreground">
        {provider.description}
      </p>
      <div className="mt-5 flex items-center justify-between border-t pt-4">
        <span
          className={`text-xs font-semibold ${provider.enabled ? 'text-emerald-600' : 'text-muted-foreground'}`}
        >
          {provider.enabled ? 'Enabled by platform' : 'Disabled by platform'}
        </span>
        <button
          className="flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground"
          onClick={onConfigure}
          type="button"
        >
          <Settings2 className="size-4" /> Configure
        </button>
      </div>
    </article>
  )
}

const smtpDefaults: SmtpConfigurationUpdate = {
  provider_display_name: 'SMTP',
  host: '',
  port: 587,
  security_mode: 'starttls',
  allow_insecure: false,
  connection_timeout: 20,
  authentication_enabled: true,
  authentication_method: 'password',
  username: '',
  password: '',
  from_email: '',
  from_name: 'MeetingHQ',
  reply_to: null,
  return_path: null,
  enabled: true,
  max_retry_attempts: 3,
  retry_delay_seconds: 1,
  timeout_seconds: 20,
  default_priority: 'normal',
}

const smtpTestRecipientSchema = z.string().trim().email()

function SmtpConfigurationPanel({
  provider,
  onClose,
}: {
  provider: IntegrationProvider
  onClose: () => void
}) {
  const { user } = useAuth()
  const client = useQueryClient()
  const [tab, setTab] = useState<'setup' | 'testing' | 'operations'>('setup')
  const [form, setForm] = useState<SmtpConfigurationUpdate>(smtpDefaults)
  const [testRecipient, setTestRecipient] = useState('')
  const configuration = useQuery({
    queryKey: ['smtp-configuration'],
    queryFn: integrationApi.smtpConfiguration,
  })
  const audit = useQuery({
    queryKey: ['integration-audit', 'smtp'],
    queryFn: () => integrationApi.audit('smtp'),
    enabled: tab === 'operations',
  })
  useEffect(() => {
    if (!configuration.data) return
    const current = configuration.data
    setForm({
      provider_display_name: current.provider_display_name,
      host: current.host,
      port: current.port,
      security_mode: current.security_mode,
      allow_insecure: current.allow_insecure,
      connection_timeout: current.connection_timeout,
      authentication_enabled: current.authentication_enabled,
      authentication_method: 'password',
      username: current.username,
      password: '',
      from_email: current.from_email,
      from_name: current.from_name,
      reply_to: current.reply_to,
      return_path: current.return_path,
      enabled: current.enabled,
      max_retry_attempts: current.max_retry_attempts,
      retry_delay_seconds: current.retry_delay_seconds,
      timeout_seconds: current.timeout_seconds,
      default_priority: current.default_priority,
    })
  }, [configuration.data])
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['smtp-configuration'] }),
      client.invalidateQueries({ queryKey: ['integrations'] }),
      client.invalidateQueries({ queryKey: ['integration-audit', 'smtp'] }),
      client.invalidateQueries({ queryKey: ['system-health'] }),
    ])
  }
  const applyValidationResult = (result: IntegrationTestResult) => {
    const healthy = result.status === 'healthy'
    client.setQueryData<SmtpConfiguration>(['smtp-configuration'], (current) =>
      current
        ? {
            ...current,
            state: healthy ? 'healthy' : 'failed',
            last_validated_at: result.checked_at,
          }
        : current,
    )
    client.setQueryData<IntegrationProvider[]>(['integrations'], (current) =>
      current?.map((item) =>
        item.key === 'smtp'
          ? {
              ...item,
              validated: healthy,
              health: healthy ? 'healthy' : 'attention',
              last_tested_at: result.checked_at,
            }
          : item,
      ),
    )
  }
  const save = useMutation({
    mutationFn: () => integrationApi.configureSmtp(form),
    onSuccess: async (saved) => {
      setForm((current) => ({ ...current, password: '' }))
      connectionTest.reset()
      emailTest.reset()
      client.setQueryData(['smtp-configuration'], saved)
      await refresh()
    },
  })
  const connectionTest = useMutation({
    mutationFn: () => integrationApi.test('smtp'),
    onMutate: () => {
      client.setQueryData<SmtpConfiguration>(
        ['smtp-configuration'],
        (current) => (current ? { ...current, state: 'testing' } : current),
      )
    },
    onSuccess: async (result) => {
      applyValidationResult(result)
      await refresh()
      // Keep the completed mutation authoritative while the transaction-scoped
      // provider status is settling in deployments with response buffering.
      applyValidationResult(result)
    },
    onError: refresh,
  })
  const normalizedRecipient = testRecipient.trim()
  const emailTest = useMutation({
    mutationFn: () => integrationApi.sendSmtpTestEmail(normalizedRecipient),
    onSuccess: async (result) => {
      notify({
        tone: result.status === 'accepted' ? 'success' : 'error',
        title:
          result.status === 'accepted'
            ? 'Test email accepted by SMTP provider'
            : 'Test email failed',
        description: result.message,
      })
      await refresh()
    },
  })
  const state = configuration.data?.state ?? 'not_configured'
  const configured = state !== 'not_configured'
  const canManage = user?.permissions.includes('integrations.manage') ?? false
  const canTest = user?.permissions.includes('integrations.test') ?? false
  const recipientIsValid =
    smtpTestRecipientSchema.safeParse(normalizedRecipient).success
  const connectionTestUnavailableReason = !canTest
    ? 'You do not have permission to test SMTP.'
    : !provider.enabled
      ? 'SMTP is disabled in Platform Management.'
      : !configured
        ? 'Configure SMTP before testing the connection.'
        : null
  const emailTestUnavailableReason = !canTest
    ? 'You do not have permission to test SMTP.'
    : !provider.enabled
      ? 'SMTP is disabled in Platform Management.'
      : !configured
        ? 'Configure SMTP before sending a test email.'
        : !configuration.data?.enabled
          ? 'Outbound SMTP delivery is disabled. Enable it in Setup before sending a test email.'
          : state !== 'healthy'
            ? 'Test the current SMTP configuration successfully before sending a test email.'
            : !recipientIsValid
              ? 'Enter a valid recipient email address.'
              : null
  return (
    <div
      aria-label="Configure SMTP"
      aria-modal="true"
      className="fixed inset-0 z-[80] flex justify-end bg-black/45"
      role="dialog"
    >
      <button
        aria-label="Close SMTP configuration"
        className="flex-1"
        onClick={onClose}
        type="button"
      />
      <aside className="flex h-full w-full max-w-5xl flex-col border-l bg-background shadow-2xl">
        <header className="border-b p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="grid size-12 place-items-center rounded-2xl bg-primary/10 text-primary">
                <ProviderLogo className="size-7" provider="smtp" />
              </div>
              <div>
                <p className="text-sm font-semibold text-primary">
                  Administration / Integration Center / Email
                </p>
                <h2 className="mt-1 text-2xl font-semibold">SMTP delivery</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  One secure outbound path for meetings, identity,
                  notifications, and external mail.
                </p>
              </div>
            </div>
            <button
              aria-label="Close SMTP configuration"
              className="rounded-lg p-2 hover:bg-muted"
              onClick={onClose}
              type="button"
            >
              <X className="size-5" />
            </button>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <SmtpStateBadge state={state} />
            <span className="rounded-full bg-muted px-3 py-1 text-xs font-semibold">
              Revision {configuration.data?.revision ?? 0}
            </span>
            {configuration.data?.password_configured && (
              <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-700">
                Credential stored securely
              </span>
            )}
          </div>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b px-5 py-2">
          {(['setup', 'testing', 'operations'] as const).map((item) => (
            <button
              aria-current={tab === item ? 'page' : undefined}
              className={`rounded-lg px-4 py-2 text-sm font-semibold capitalize ${
                tab === item
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted'
              }`}
              key={item}
              onClick={() => setTab(item)}
              type="button"
            >
              {item === 'testing' ? 'Test & delivery' : item}
            </button>
          ))}
        </nav>
        <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-6">
          {configuration.isLoading ? (
            <div className="h-96 animate-pulse rounded-2xl bg-muted" />
          ) : configuration.isError ? (
            <p
              className="rounded-xl border border-red-500/30 bg-red-500/5 p-5 text-red-700"
              role="alert"
            >
              SMTP configuration could not be loaded.
            </p>
          ) : tab === 'setup' ? (
            <SmtpSetupForm
              canManage={canManage}
              form={form}
              passwordConfigured={
                configuration.data?.password_configured ?? false
              }
              providerEnabled={provider.enabled}
              saving={save.isPending}
              setForm={setForm}
              submit={() => save.mutate()}
            />
          ) : tab === 'testing' ? (
            <div className="grid gap-5 lg:grid-cols-2">
              <section className="rounded-2xl border bg-card p-5">
                <Server className="size-6 text-primary" />
                <h3 className="mt-4 text-lg font-semibold">Test connection</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Validates DNS, network, TLS, authentication, and SMTP NOOP.
                </p>
                <button
                  aria-describedby={
                    connectionTestUnavailableReason
                      ? 'smtp-connection-test-reason'
                      : undefined
                  }
                  className="mt-5 h-11 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                  disabled={
                    Boolean(connectionTestUnavailableReason) ||
                    connectionTest.isPending
                  }
                  onClick={() => connectionTest.mutate()}
                  type="button"
                >
                  {connectionTest.isPending ? 'Testing…' : 'Test connection'}
                </button>
                {connectionTestUnavailableReason && (
                  <p
                    className="mt-3 text-sm text-amber-700"
                    id="smtp-connection-test-reason"
                  >
                    {connectionTestUnavailableReason}
                  </p>
                )}
                {connectionTest.data && (
                  <TestResult
                    latency={connectionTest.data.latency_ms}
                    message={connectionTest.data.message}
                    success={connectionTest.data.status === 'healthy'}
                  />
                )}
              </section>
              <section className="rounded-2xl border bg-card p-5">
                <Send className="size-6 text-primary" />
                <h3 className="mt-4 text-lg font-semibold">Send test email</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Uses the exact outbound transport used by MeetingHQ. SMTP
                  acceptance is not final mailbox-delivery proof.
                </p>
                <label className="mt-5 block text-sm font-medium">
                  Recipient email
                  <input
                    aria-label="SMTP test recipient"
                    aria-describedby={
                      testRecipient && !recipientIsValid
                        ? 'smtp-recipient-error'
                        : undefined
                    }
                    aria-invalid={
                      testRecipient && !recipientIsValid ? true : undefined
                    }
                    className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                    onChange={(event) => setTestRecipient(event.target.value)}
                    placeholder="operator@example.com"
                    type="email"
                    value={testRecipient}
                  />
                </label>
                {testRecipient && !recipientIsValid && (
                  <p
                    className="mt-2 text-sm text-red-600"
                    id="smtp-recipient-error"
                    role="alert"
                  >
                    Enter a valid recipient email address.
                  </p>
                )}
                <button
                  aria-describedby={
                    emailTestUnavailableReason
                      ? 'smtp-test-email-reason'
                      : undefined
                  }
                  className="mt-4 h-11 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                  disabled={
                    Boolean(emailTestUnavailableReason) || emailTest.isPending
                  }
                  onClick={() => emailTest.mutate()}
                  type="button"
                >
                  {emailTest.isPending ? 'Submitting…' : 'Send test email'}
                </button>
                {emailTestUnavailableReason && !emailTest.isPending && (
                  <p
                    className="mt-3 text-sm text-amber-700"
                    id="smtp-test-email-reason"
                    role="status"
                  >
                    {emailTestUnavailableReason}
                  </p>
                )}
                {emailTest.data && (
                  <TestResult
                    latency={emailTest.data.latency_ms}
                    message={emailTest.data.message}
                    success={emailTest.data.status === 'accepted'}
                  />
                )}
              </section>
            </div>
          ) : (
            <ProviderAudit
              rows={audit.data ?? []}
              title="SMTP operational log"
            />
          )}
        </div>
      </aside>
    </div>
  )
}

function SmtpSetupForm({
  canManage,
  form,
  setForm,
  submit,
  saving,
  passwordConfigured,
  providerEnabled,
}: {
  canManage: boolean
  form: SmtpConfigurationUpdate
  setForm: Dispatch<SetStateAction<SmtpConfigurationUpdate>>
  submit: () => void
  saving: boolean
  passwordConfigured: boolean
  providerEnabled: boolean
}) {
  const set = (
    key: keyof SmtpConfigurationUpdate,
    value: string | number | boolean | null | undefined,
  ) =>
    setForm(
      (current) => ({ ...current, [key]: value }) as SmtpConfigurationUpdate,
    )
  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      {!providerEnabled && (
        <p className="rounded-xl border border-amber-300 bg-amber-500/10 p-4 text-sm text-amber-800">
          SMTP is unavailable in Platform Management. Save configuration now,
          then enable the SMTP capability before delivery.
        </p>
      )}
      {!canManage && (
        <p className="rounded-xl border border-amber-300 bg-amber-500/10 p-4 text-sm text-amber-800">
          You do not have permission to change SMTP configuration.
        </p>
      )}
      <SmtpSection
        title="Connection"
        description="Server endpoint and encrypted transport policy."
      >
        <TextField
          label="Provider display name"
          value={form.provider_display_name}
          onChange={(value) => set('provider_display_name', value)}
        />
        <TextField
          label="SMTP host"
          value={form.host}
          onChange={(value) => set('host', value)}
          placeholder="smtp.example.com"
        />
        <NumberField
          label="SMTP port"
          value={form.port}
          min={1}
          max={65535}
          onChange={(value) => set('port', value)}
        />
        <label className="text-sm font-medium">
          Security mode
          <select
            className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
            value={form.security_mode}
            onChange={(event) =>
              set(
                'security_mode',
                event.target.value as SmtpConfigurationUpdate['security_mode'],
              )
            }
          >
            <option value="starttls">STARTTLS</option>
            <option value="ssl_tls">SSL / TLS</option>
            <option value="none">None (insecure)</option>
          </select>
        </label>
        <NumberField
          label="Connection timeout (seconds)"
          value={form.connection_timeout}
          min={1}
          max={120}
          onChange={(value) => set('connection_timeout', value)}
        />
        {form.security_mode === 'none' && (
          <CheckboxField
            checked={form.allow_insecure}
            label="I explicitly allow unencrypted SMTP for this tenant"
            onChange={(value) => set('allow_insecure', value)}
          />
        )}
      </SmtpSection>
      <SmtpSection
        title="Authentication"
        description="The password is write-only and encrypted before persistence."
      >
        <CheckboxField
          checked={form.authentication_enabled}
          label="Authentication enabled"
          onChange={(value) => set('authentication_enabled', value)}
        />
        <TextField
          label="Username"
          value={form.username ?? ''}
          onChange={(value) => set('username', value)}
          disabled={!form.authentication_enabled}
        />
        <TextField
          label="Password / app password"
          value={form.password ?? ''}
          onChange={(value) => set('password', value)}
          disabled={!form.authentication_enabled}
          placeholder={
            passwordConfigured
              ? '•••••••••••• (leave blank to preserve)'
              : 'Enter SMTP secret'
          }
          type="password"
        />
      </SmtpSection>
      <SmtpSection
        title="Sender"
        description="Identity applied consistently to application-generated email."
      >
        <TextField
          label="From email address"
          value={form.from_email}
          onChange={(value) => set('from_email', value)}
          type="email"
        />
        <TextField
          label="From display name"
          value={form.from_name}
          onChange={(value) => set('from_name', value)}
        />
        <TextField
          label="Reply-To address"
          value={form.reply_to ?? ''}
          onChange={(value) => set('reply_to', value || null)}
          type="email"
        />
        <TextField
          label="Return path / bounce address"
          value={form.return_path ?? ''}
          onChange={(value) => set('return_path', value || null)}
          type="email"
        />
      </SmtpSection>
      <SmtpSection
        title="Delivery"
        description="Bounded retries and truthful outbound state handling."
      >
        <CheckboxField
          checked={form.enabled}
          label="Enable outbound email delivery"
          onChange={(value) => set('enabled', value)}
        />
        <NumberField
          label="Maximum retry attempts"
          value={form.max_retry_attempts}
          min={1}
          max={10}
          onChange={(value) => set('max_retry_attempts', value)}
        />
        <NumberField
          label="Retry delay (seconds)"
          value={form.retry_delay_seconds}
          min={0}
          max={300}
          onChange={(value) => set('retry_delay_seconds', value)}
        />
        <NumberField
          label="Send timeout (seconds)"
          value={form.timeout_seconds}
          min={1}
          max={120}
          onChange={(value) => set('timeout_seconds', value)}
        />
        <label className="text-sm font-medium">
          Default priority
          <select
            className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
            value={form.default_priority}
            onChange={(event) =>
              set(
                'default_priority',
                event.target
                  .value as SmtpConfigurationUpdate['default_priority'],
              )
            }
          >
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
          </select>
        </label>
      </SmtpSection>
      <div className="sticky bottom-0 flex justify-end border-t bg-background/95 py-4 backdrop-blur">
        <button
          className="h-11 rounded-xl bg-primary px-6 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={
            saving ||
            !canManage ||
            !form.host ||
            !form.from_email ||
            (form.security_mode === 'none' && !form.allow_insecure)
          }
          type="submit"
        >
          {saving ? 'Saving securely…' : 'Save SMTP configuration'}
        </button>
      </div>
    </form>
  )
}

function SmtpSection({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section className="rounded-2xl border bg-card p-5">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">{children}</div>
    </section>
  )
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  disabled = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
  disabled?: boolean
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <input
        aria-label={label}
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 disabled:opacity-60"
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type={type}
        value={value}
      />
    </label>
  )
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min: number
  max: number
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <input
        aria-label={label}
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
        max={max}
        min={min}
        onChange={(event) => onChange(Number(event.target.value))}
        type="number"
        value={value}
      />
    </label>
  )
}

function CheckboxField({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label className="flex items-center gap-3 rounded-xl border p-3 text-sm font-medium">
      <input
        checked={checked}
        className="size-4 accent-primary"
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
      {label}
    </label>
  )
}

function SmtpStateBadge({ state }: { state: string }) {
  const healthy = state === 'healthy'
  const failed = state === 'failed' || state === 'degraded'
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${healthy ? 'bg-emerald-500/10 text-emerald-700' : failed ? 'bg-red-500/10 text-red-700' : 'bg-amber-500/10 text-amber-800'}`}
    >
      {state.replaceAll('_', ' ')}
    </span>
  )
}

function TestResult({
  success,
  message,
  latency,
}: {
  success: boolean
  message: string
  latency: number
}) {
  return (
    <div
      className={`mt-4 rounded-xl border p-4 text-sm ${success ? 'border-emerald-300 bg-emerald-500/5' : 'border-red-300 bg-red-500/5'}`}
      role="status"
    >
      <p className="font-semibold">
        {success ? 'Successful' : 'Attention required'} · {latency} ms
      </p>
      <p className="mt-1 text-muted-foreground">{message}</p>
    </div>
  )
}

type ProviderTab =
  | 'overview'
  | 'authentication'
  | 'permissions'
  | 'configuration'
  | 'health'
  | 'logs'
  | 'synchronization'
  | 'advanced'
  | 'audit'
  | 'test connection'

const providerTabs: ProviderTab[] = [
  'overview',
  'authentication',
  'permissions',
  'configuration',
  'health',
  'logs',
  'synchronization',
  'advanced',
  'audit',
  'test connection',
]

function ConfigurationPanel({
  provider,
  onClose,
  onDisconnect,
  disconnecting,
}: {
  provider: IntegrationProvider
  onClose: () => void
  onDisconnect: () => void
  disconnecting: boolean
}) {
  const client = useQueryClient()
  const fields = fieldsByType[provider.auth_type] ?? fallbackFields
  const [values, setValues] = useState<Record<string, string>>({})
  const [tab, setTab] = useState<ProviderTab>('configuration')
  const save = useMutation({
    mutationFn: () => integrationApi.configure(provider.key, values),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['integrations'] })
      onClose()
    },
  })
  const test = useMutation({
    mutationFn: () => integrationApi.test(provider.key),
  })
  const synchronize = useMutation({
    mutationFn: () => integrationApi.synchronize(provider.key),
  })
  const audit = useQuery({
    queryKey: ['integration-audit', provider.key],
    queryFn: () => integrationApi.audit(provider.key),
    enabled: tab === 'logs' || tab === 'audit',
  })
  return (
    <div
      aria-label={`Configure ${provider.name}`}
      aria-modal="true"
      className="fixed inset-0 z-[80] flex justify-end bg-black/45"
      role="dialog"
    >
      <button
        aria-label="Close integration configuration"
        className="flex-1"
        onClick={onClose}
        type="button"
      />
      <aside className="flex h-full w-full max-w-4xl flex-col border-l bg-background shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b p-6">
          <div>
            <p className="text-sm font-semibold text-primary">
              {provider.category}
            </p>
            <h2 className="mt-1 text-2xl font-semibold">{provider.name}</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {provider.description}
            </p>
          </div>
          <button
            aria-label="Close integration configuration"
            className="rounded-lg p-2 hover:bg-muted"
            onClick={onClose}
            type="button"
          >
            <X className="size-5" />
          </button>
        </div>
        <nav
          aria-label={`${provider.name} configuration sections`}
          className="flex shrink-0 gap-1 overflow-x-auto border-b px-4 py-2"
        >
          {providerTabs.map((item) => (
            <button
              aria-current={tab === item ? 'page' : undefined}
              className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold capitalize ${
                tab === item
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
              key={item}
              onClick={() => setTab(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {tab === 'overview' && <ProviderOverview provider={provider} />}
          {tab === 'authentication' && (
            <InfoSection
              description={`This provider uses ${provider.auth_type.toUpperCase()} authentication. Credentials are sealed with authenticated encryption before database persistence and are never returned by the API.`}
              icon={ShieldCheck}
              title="Authentication"
            >
              <dl className="grid gap-3 rounded-xl border bg-card p-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Method</dt>
                  <dd className="mt-1 font-semibold uppercase">
                    {provider.auth_type}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Credential state</dt>
                  <dd className="mt-1 font-semibold">
                    {provider.configured ? 'Stored securely' : 'Not configured'}
                  </dd>
                </div>
              </dl>
            </InfoSection>
          )}
          {tab === 'permissions' && (
            <InfoSection
              description="MeetingHQ requests the minimum provider capabilities required for enabled workflows."
              icon={ShieldCheck}
              title="Provider permissions"
            >
              <div className="space-y-2">
                {providerScopes(provider).map((scope) => (
                  <div
                    className="flex items-center gap-3 rounded-xl border bg-card p-3 text-sm"
                    key={scope}
                  >
                    <CheckCircle2 className="size-4 text-emerald-600" />
                    {scope}
                  </div>
                ))}
              </div>
            </InfoSection>
          )}
          {tab === 'configuration' && (
            <ConfigurationForm
              disconnecting={disconnecting}
              fields={fields}
              onDisconnect={onDisconnect}
              provider={provider}
              save={save}
              setValues={setValues}
              values={values}
            />
          )}
          {tab === 'health' && (
            <InfoSection
              description="Current state reflects availability and credential configuration. Run a live test for network evidence."
              icon={CheckCircle2}
              title="Connection health"
            >
              <div className="rounded-xl border bg-card p-5">
                <HealthBadge health={provider.health} />
                <p className="mt-4 text-sm text-muted-foreground">
                  Last configuration change:{' '}
                  {provider.updated_at
                    ? new Date(provider.updated_at).toLocaleString()
                    : 'No configuration has been saved.'}
                </p>
              </div>
            </InfoSection>
          )}
          {tab === 'logs' && (
            <ProviderAudit rows={audit.data ?? []} title="Provider logs" />
          )}
          {tab === 'synchronization' && (
            <InfoSection
              description="Run a provider synchronization now. Requests are audit logged and processed through the configured provider boundary."
              icon={RefreshCw}
              title="Synchronization"
            >
              <button
                className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                disabled={!provider.configured || synchronize.isPending}
                onClick={() => synchronize.mutate()}
                type="button"
              >
                {synchronize.isPending ? 'Queueing…' : 'Synchronize now'}
              </button>
              {synchronize.data && (
                <p className="mt-3 rounded-xl bg-emerald-500/10 p-3 text-sm text-emerald-700">
                  {synchronize.data.message}
                </p>
              )}
            </InfoSection>
          )}
          {tab === 'advanced' && (
            <InfoSection
              description="Endpoint overrides and provider-specific values are validated in Configuration."
              icon={Settings2}
              title="Advanced"
            >
              <button
                className="rounded-xl border px-4 py-2 text-sm font-semibold hover:bg-muted"
                onClick={() => setTab('configuration')}
                type="button"
              >
                Review configuration
              </button>
            </InfoSection>
          )}
          {tab === 'audit' && (
            <ProviderAudit rows={audit.data ?? []} title="Audit history" />
          )}
          {tab === 'test connection' && (
            <InfoSection
              description="Perform a live network and authentication probe without exposing stored credentials."
              icon={TestTube2}
              title="Test connection"
            >
              {!provider.configured ? (
                <div className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
                  Save provider configuration before running a test.
                </div>
              ) : (
                <>
                  <button
                    className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60"
                    disabled={test.isPending}
                    onClick={() => test.mutate()}
                    type="button"
                  >
                    {test.isPending
                      ? 'Testing connection…'
                      : 'Run connection test'}
                  </button>
                  {test.data && (
                    <div
                      className={`mt-4 rounded-xl border p-4 text-sm ${
                        test.data.status === 'healthy'
                          ? 'border-emerald-300 bg-emerald-500/5'
                          : 'border-amber-300 bg-amber-500/5'
                      }`}
                    >
                      <p className="font-semibold capitalize">
                        {test.data.status} · {test.data.latency_ms} ms
                      </p>
                      <p className="mt-1 text-muted-foreground">
                        {test.data.message}
                      </p>
                      <time className="mt-2 block text-xs text-muted-foreground">
                        {new Date(test.data.checked_at).toLocaleString()}
                      </time>
                    </div>
                  )}
                </>
              )}
            </InfoSection>
          )}
        </div>
      </aside>
    </div>
  )
}

function ConfigurationForm({
  provider,
  fields,
  values,
  setValues,
  save,
  onDisconnect,
  disconnecting,
}: {
  provider: IntegrationProvider
  fields: FieldDefinition[]
  values: Record<string, string>
  setValues: Dispatch<SetStateAction<Record<string, string>>>
  save: { isPending: boolean; mutate: () => void }
  onDisconnect: () => void
  disconnecting: boolean
}) {
  return (
    <>
      <div className="flex items-center gap-3 rounded-xl border bg-muted/30 p-4">
        <ShieldCheck className="size-5 text-primary" />
        <p className="text-sm text-muted-foreground">
          Credentials are encrypted at rest and never returned after saving.
        </p>
      </div>
      {!provider.enabled && (
        <p className="mt-4 rounded-xl bg-amber-500/10 p-3 text-sm text-amber-700">
          This provider is disabled in Platform Management. Configuration can be
          prepared, but MeetingHQ will not use it until enabled.
        </p>
      )}
      <form
        className="mt-6 grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        {fields.map((field) => (
          <label className="block text-sm font-medium" key={field.key}>
            {field.label}
            <input
              aria-label={`${provider.name} ${field.label}`}
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  [field.key]: event.target.value,
                }))
              }
              placeholder={field.placeholder}
              required
              type={field.secret ? 'password' : 'text'}
              value={values[field.key] ?? ''}
            />
          </label>
        ))}
        <button
          className="h-11 rounded-xl bg-primary font-semibold text-primary-foreground disabled:opacity-50 sm:col-span-2"
          disabled={
            save.isPending || fields.some((field) => !values[field.key])
          }
          type="submit"
        >
          {save.isPending
            ? 'Saving securely…'
            : provider.configured
              ? 'Replace configuration'
              : 'Save configuration'}
        </button>
      </form>
      {provider.configured && (
        <button
          className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-red-500/30 text-sm font-semibold text-red-600 disabled:opacity-50"
          disabled={disconnecting}
          onClick={onDisconnect}
          type="button"
        >
          <Unplug className="size-4" />
          Disconnect provider
        </button>
      )}
    </>
  )
}

function ProviderOverview({ provider }: { provider: IntegrationProvider }) {
  return (
    <InfoSection
      description={provider.description}
      icon={Plug}
      title="Overview"
    >
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric
          label="Platform availability"
          value={provider.enabled ? 1 : 0}
        />
        <Metric label="Credential sets" value={provider.configured ? 1 : 0} />
        <Metric label="Validated" value={provider.validated ? 1 : 0} />
        <div className="rounded-2xl border bg-card p-5">
          <HealthBadge health={provider.health} />
          <p className="mt-2 text-sm text-muted-foreground">Current health</p>
        </div>
      </div>
    </InfoSection>
  )
}

function ProviderAudit({
  rows,
  title,
}: {
  rows: Awaited<ReturnType<typeof integrationApi.audit>>
  title: string
}) {
  return (
    <InfoSection
      description="Immutable provider operations are shown without credentials or secret values."
      icon={ScrollText}
      title={title}
    >
      <div className="divide-y rounded-xl border">
        {rows.map((row) => (
          <div
            className="flex items-center gap-3 p-4 text-sm"
            key={`${row.action}-${row.created_at}`}
          >
            <CheckCircle2 className="size-4 text-primary" />
            <div className="min-w-0 flex-1">
              <p className="font-medium">{row.action.replaceAll('.', ' - ')}</p>
              <p className="text-xs text-muted-foreground">
                {new Date(row.created_at).toLocaleString()}
                {row.latency_ms != null ? ` · ${row.latency_ms} ms` : ''}
                {row.revision != null ? ` · revision ${row.revision}` : ''}
              </p>
              {row.diagnostic && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {row.diagnostic}
                </p>
              )}
              {row.recipient && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Test recipient: {row.recipient}
                </p>
              )}
            </div>
            <span className="rounded-full bg-muted px-2 py-1 text-xs capitalize">
              {row.status}
            </span>
          </div>
        ))}
        {rows.length === 0 && (
          <p className="p-8 text-center text-sm text-muted-foreground">
            No provider operations recorded yet.
          </p>
        )}
      </div>
    </InfoSection>
  )
}

function InfoSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Plug
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section>
      <div className="flex items-start gap-3">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
          <Icon className="size-5" />
        </div>
        <div>
          <h3 className="text-lg font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="mt-6">{children}</div>
    </section>
  )
}

function providerScopes(provider: IntegrationProvider) {
  if (provider.category === 'Email')
    return [
      'Send messages',
      'Read mailbox metadata',
      'Synchronize folders and message state',
    ]
  if (provider.category === 'Calendar')
    return [
      'Read calendars',
      'Create and update events',
      'Synchronize attendee responses',
    ]
  if (provider.category === 'Storage')
    return [
      'Read authorized objects',
      'Create MeetingHQ objects',
      'Manage MeetingHQ object metadata',
    ]
  if (provider.category === 'AI')
    return ['Invoke configured models', 'Read provider usage metadata']
  if (provider.category === 'Meetings')
    return [
      'Create conferences',
      'Read conference status',
      'Synchronize meeting links',
    ]
  return ['Connect to the configured service', 'Read provider health metadata']
}

function HealthBadge({ health }: { health: IntegrationProvider['health'] }) {
  const Icon =
    health === 'healthy'
      ? CheckCircle2
      : health === 'attention'
        ? CircleAlert
        : Unplug
  return (
    <span
      className={`flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${
        health === 'healthy'
          ? 'bg-emerald-500/10 text-emerald-700'
          : health === 'attention'
            ? 'bg-amber-500/10 text-amber-700'
            : 'bg-muted text-muted-foreground'
      }`}
    >
      <Icon className="size-3.5" />
      {health}
    </span>
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
