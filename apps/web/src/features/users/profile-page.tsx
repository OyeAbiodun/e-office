import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useRouterState } from '@tanstack/react-router'
import {
  Accessibility,
  Bell,
  CalendarDays,
  Camera,
  Clock3,
  Copy,
  Download,
  KeyRound,
  Laptop,
  Link2,
  LockKeyhole,
  Mail,
  Palette,
  RefreshCcw,
  Save,
  ShieldCheck,
  Trash2,
  UserRound,
  Users,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'

import { authenticatedAsset, authApi } from '@/features/auth/api'
import { useAuth } from '@/features/auth/auth-store'
import { notificationApi } from '@/features/notifications/api'
import { profileApi } from '@/features/users/api'

const sections = [
  {
    key: 'personal',
    label: 'Personal information',
    icon: UserRound,
    path: '/profile',
  },
  {
    key: 'security',
    label: 'Security & sessions',
    icon: ShieldCheck,
    path: '/profile/security',
  },
  {
    key: 'notifications',
    label: 'Notifications',
    icon: Bell,
    path: '/profile/notifications',
  },
  {
    key: 'appearance',
    label: 'Appearance & accessibility',
    icon: Palette,
    path: '/profile/preferences',
  },
  {
    key: 'schedule',
    label: 'Calendar & meetings',
    icon: CalendarDays,
    path: '/profile/preferences?section=schedule',
  },
  {
    key: 'communication',
    label: 'Chat & mail',
    icon: Mail,
    path: '/profile/preferences?section=communication',
  },
  {
    key: 'connections',
    label: 'Connected accounts',
    icon: Link2,
    path: '/profile/connections',
  },
  {
    key: 'organization',
    label: 'Organization & access',
    icon: Users,
    path: '/profile/organization',
  },
] as const

type Section = (typeof sections)[number]['key']

export function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const search = useRouterState({ select: (state) => state.location.searchStr })
  const client = useQueryClient()
  const section = resolveSection(pathname, search)
  const profile = useQuery({
    queryKey: ['profile'],
    queryFn: profileApi.profile,
  })
  const center = useQuery({
    queryKey: ['profile-center'],
    queryFn: profileApi.center,
  })
  const sessions = useQuery({
    queryKey: ['profile-sessions'],
    queryFn: authApi.sessions,
    enabled: section === 'security',
  })
  const tokens = useQuery({
    queryKey: ['profile-api-tokens'],
    queryFn: profileApi.tokens,
    enabled: section === 'security',
  })
  const securityHistory = useQuery({
    queryKey: ['profile-security-history'],
    queryFn: profileApi.securityHistory,
    enabled: section === 'security',
  })
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['profile'] })
    void client.invalidateQueries({ queryKey: ['profile-center'] })
  }
  const updateProfile = useMutation({
    mutationFn: profileApi.updateProfile,
    onSuccess: () => {
      refresh()
      void refreshUser()
    },
  })
  const updateCenter = useMutation({
    mutationFn: profileApi.updateCenter,
    onSuccess: refresh,
  })

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-5 sm:p-8">
      <header className="overflow-hidden rounded-3xl border bg-card">
        <div
          className="h-32 bg-gradient-to-r from-primary/25 via-cyan-500/15 to-violet-500/20"
          style={
            center.data?.cover_image_url
              ? {
                  backgroundImage: `url(${center.data.cover_image_url})`,
                  backgroundPosition: 'center',
                  backgroundSize: 'cover',
                }
              : undefined
          }
        />
        <div className="flex flex-col gap-4 px-6 pb-6 sm:flex-row sm:items-end">
          <div className="-mt-12 grid size-24 shrink-0 place-items-center overflow-hidden rounded-3xl border-4 border-card bg-primary text-2xl font-semibold text-primary-foreground">
            {profile.data?.avatar_url ? (
              <AuthenticatedImage
                alt={profile.data.display_name}
                className="size-full object-cover"
                src={profile.data.avatar_url}
              />
            ) : (
              (profile.data?.first_name?.slice(0, 1) ?? 'U')
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-primary">My account</p>
            <h1 className="truncate text-3xl font-semibold tracking-tight">
              {profile.data?.display_name ??
                user?.display_name ??
                'Profile Center'}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {profile.data?.job_title || 'MeetingHQ member'}
              {profile.data?.department ? ` · ${profile.data.department}` : ''}
            </p>
          </div>
          <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold capitalize text-emerald-700 dark:text-emerald-300">
            {center.data?.presence.replaceAll('_', ' ') ?? 'available'}
          </span>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        <nav
          aria-label="Profile sections"
          className="h-fit rounded-2xl border bg-card p-2"
        >
          {sections.map(({ key, label, icon: Icon, path }) => (
            <button
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition ${
                section === key
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted'
              }`}
              key={key}
              onClick={() => void navigate({ to: path as never })}
              type="button"
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </nav>

        <main className="min-w-0 rounded-2xl border bg-card p-5 sm:p-7">
          {profile.isLoading || center.isLoading ? (
            <Loading />
          ) : profile.isError || center.isError ? (
            <ErrorState retry={refresh} />
          ) : section === 'personal' ? (
            <PersonalSection
              center={center.data!}
              profile={profile.data!}
              saveCenter={(values) => updateCenter.mutate(values)}
              saveProfile={(values) => updateProfile.mutate(values)}
            />
          ) : section === 'security' ? (
            <SecuritySection
              center={center.data!}
              refresh={refresh}
              securityHistory={securityHistory.data ?? []}
              sessions={sessions.data ?? []}
              tokens={tokens.data ?? []}
            />
          ) : section === 'notifications' ? (
            <NotificationPreferencesSection />
          ) : section === 'appearance' ? (
            <PreferenceSection
              center={center.data!}
              group="appearance"
              icon={Accessibility}
              save={(preferences) => updateCenter.mutate({ preferences })}
              title="Appearance & accessibility"
            />
          ) : section === 'schedule' ? (
            <ScheduleSection
              center={center.data!}
              save={(values) => updateCenter.mutate(values)}
            />
          ) : section === 'communication' ? (
            <PreferenceSection
              center={center.data!}
              group="communication"
              icon={Mail}
              save={(preferences) => updateCenter.mutate({ preferences })}
              title="Chat & mail preferences"
            />
          ) : section === 'connections' ? (
            <ConnectionsSection accounts={center.data!.connected_accounts} />
          ) : (
            <OrganizationSection
              center={center.data!}
              profile={profile.data!}
            />
          )}
        </main>
      </div>
    </div>
  )
}

function PersonalSection({
  profile,
  center,
  saveProfile,
  saveCenter,
}: {
  profile: Awaited<ReturnType<typeof profileApi.profile>>
  center: Awaited<ReturnType<typeof profileApi.center>>
  saveProfile: (values: Record<string, unknown>) => void
  saveCenter: (values: Record<string, unknown>) => void
}) {
  const [values, setValues] = useState({
    first_name: profile.first_name,
    last_name: profile.last_name,
    display_name: profile.display_name,
    phone: profile.phone ?? '',
    job_title: profile.job_title ?? '',
    department: profile.department ?? '',
    location: profile.location ?? '',
    timezone: profile.timezone,
    language: profile.language,
    status_message: center.status_message ?? '',
    presence: center.presence,
    signature: center.signature ?? '',
  })
  return (
    <Section
      title="Personal information"
      subtitle="Your identity, locale, presence, and signature."
    >
      <AvatarEditor profile={profile} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="First name"
          value={values.first_name}
          set={(value) => setValues({ ...values, first_name: value })}
        />
        <Field
          label="Last name"
          value={values.last_name}
          set={(value) => setValues({ ...values, last_name: value })}
        />
        <Field
          label="Display name"
          value={values.display_name}
          set={(value) => setValues({ ...values, display_name: value })}
        />
        <Field
          disabled
          label="Email"
          value={profile.email}
          set={() => undefined}
        />
        <Field
          label="Phone"
          value={values.phone}
          set={(value) => setValues({ ...values, phone: value })}
        />
        <Field
          label="Job title"
          value={values.job_title}
          set={(value) => setValues({ ...values, job_title: value })}
        />
        <Field
          label="Department"
          value={values.department}
          set={(value) => setValues({ ...values, department: value })}
        />
        <Field
          label="Location"
          value={values.location}
          set={(value) => setValues({ ...values, location: value })}
        />
        <Field
          label="Timezone"
          value={values.timezone}
          set={(value) => setValues({ ...values, timezone: value })}
        />
        <Field
          label="Language"
          value={values.language}
          set={(value) => setValues({ ...values, language: value })}
        />
        <SelectField
          label="Presence"
          value={values.presence}
          values={['available', 'busy', 'do_not_disturb', 'away', 'offline']}
          set={(value) =>
            setValues({ ...values, presence: value as typeof values.presence })
          }
        />
        <Field
          label="Status message"
          value={values.status_message}
          set={(value) => setValues({ ...values, status_message: value })}
        />
      </div>
      <label className="mt-4 block text-sm font-medium">
        Email signature
        <textarea
          className="mt-2 min-h-28 w-full rounded-xl border bg-background p-3"
          onChange={(event) =>
            setValues({ ...values, signature: event.target.value })
          }
          value={values.signature}
        />
      </label>
      <button
        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
        onClick={() => {
          saveProfile({
            first_name: values.first_name,
            last_name: values.last_name,
            display_name: values.display_name,
            phone: values.phone || null,
            job_title: values.job_title || null,
            department: values.department || null,
            location: values.location || null,
            timezone: values.timezone,
            language: values.language,
          })
          saveCenter({
            presence: values.presence,
            status_message: values.status_message || null,
            signature: values.signature || null,
          })
        }}
        type="button"
      >
        <Save className="size-4" /> Save profile
      </button>
    </Section>
  )
}

function SecuritySection({
  center,
  refresh,
  sessions,
  tokens,
  securityHistory,
}: {
  center: Awaited<ReturnType<typeof profileApi.center>>
  refresh: () => void
  sessions: Awaited<ReturnType<typeof authApi.sessions>>
  tokens: Awaited<ReturnType<typeof profileApi.tokens>>
  securityHistory: Awaited<ReturnType<typeof profileApi.securityHistory>>
}) {
  const sessionsPerPage = 8
  const client = useQueryClient()
  const [sessionPage, setSessionPage] = useState(1)
  const [passwords, setPasswords] = useState({
    current_password: '',
    new_password: '',
    confirm_new_password: '',
  })
  const [tokenName, setTokenName] = useState('')
  const [revealed, setRevealed] = useState('')
  const [mfaCode, setMfaCode] = useState('')
  const [disableMfaValues, setDisableMfaValues] = useState({
    current_password: '',
    code: '',
  })
  const [recoveryValues, setRecoveryValues] = useState({
    current_password: '',
    code: '',
  })
  const [mfaSetup, setMfaSetup] = useState<Awaited<
    ReturnType<typeof profileApi.setupMfa>
  > | null>(null)
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const sessionPageCount = Math.max(
    1,
    Math.ceil(sessions.length / sessionsPerPage),
  )
  const visibleSessions = sessions.slice(
    (sessionPage - 1) * sessionsPerPage,
    sessionPage * sessionsPerPage,
  )
  useEffect(() => {
    if (sessionPage > sessionPageCount) setSessionPage(sessionPageCount)
  }, [sessionPage, sessionPageCount])
  const changePassword = useMutation({
    mutationFn: authApi.changePassword,
    onSuccess: () =>
      setPasswords({
        current_password: '',
        new_password: '',
        confirm_new_password: '',
      }),
  })
  const createToken = useMutation({
    mutationFn: profileApi.createToken,
    onSuccess: (token) => {
      setRevealed(token.token ?? '')
      setTokenName('')
      void client.invalidateQueries({ queryKey: ['profile-api-tokens'] })
    },
  })
  const revoke = useMutation({
    mutationFn: profileApi.revokeToken,
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ['profile-api-tokens'] }),
  })
  const setupMfa = useMutation({
    mutationFn: profileApi.setupMfa,
    onSuccess: (response) => {
      setMfaSetup(response)
      setRecoveryCodes([])
    },
  })
  const verifyMfa = useMutation({
    mutationFn: profileApi.verifyMfa,
    onSuccess: (response) => {
      setRecoveryCodes(response.recovery_codes)
      setMfaCode('')
      setMfaSetup(null)
      refresh()
    },
  })
  const disableMfa = useMutation({
    mutationFn: profileApi.disableMfa,
    onSuccess: () => {
      setDisableMfaValues({ current_password: '', code: '' })
      setRecoveryCodes([])
      refresh()
    },
  })
  const regenerateRecoveryCodes = useMutation({
    mutationFn: profileApi.regenerateRecoveryCodes,
    onSuccess: (response) => {
      setRecoveryCodes(response.recovery_codes)
      setRecoveryValues({ current_password: '', code: '' })
    },
  })
  return (
    <Section
      title="Security & sessions"
      subtitle="Protect your account and review every active device."
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Password" icon={LockKeyhole}>
          <Field
            password
            label="Current password"
            value={passwords.current_password}
            set={(value) =>
              setPasswords({ ...passwords, current_password: value })
            }
          />
          <div className="mt-3">
            <Field
              password
              label="New password"
              value={passwords.new_password}
              set={(value) =>
                setPasswords({ ...passwords, new_password: value })
              }
            />
          </div>
          <div className="mt-3">
            <Field
              password
              label="Confirm new password"
              value={passwords.confirm_new_password}
              set={(value) =>
                setPasswords({ ...passwords, confirm_new_password: value })
              }
            />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Use at least 12 characters. A successful change signs out your other
            sessions.
          </p>
          <button
            className="mt-4 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={
              passwords.new_password.length < 12 ||
              passwords.new_password !== passwords.confirm_new_password
            }
            onClick={() => changePassword.mutate(passwords)}
            type="button"
          >
            Change password
          </button>
        </Card>
        <Card title="Two-factor authentication" icon={ShieldCheck}>
          <p className="text-sm text-muted-foreground">
            Add a second verification step for sensitive account access.
          </p>
          <div
            className={`mt-4 rounded-xl border p-3 text-sm ${center.mfa_enabled ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'bg-muted/40 text-muted-foreground'}`}
          >
            {center.mfa_enabled
              ? 'Two-factor authentication is enabled.'
              : 'Two-factor authentication is not enabled.'}
          </div>
          {!center.mfa_enabled ? (
            <div className="mt-4 space-y-3">
              {!mfaSetup ? (
                <button
                  className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
                  onClick={() => setupMfa.mutate()}
                  type="button"
                >
                  Start setup
                </button>
              ) : (
                <>
                  <img
                    alt="Scan this QR code with your authenticator app"
                    className="mx-auto size-48 rounded-xl border bg-white p-3"
                    src={mfaSetup.qr_code_data_url}
                  />
                  <div className="rounded-xl border bg-background p-3">
                    <p className="text-xs font-semibold uppercase text-muted-foreground">
                      Authenticator setup key
                    </p>
                    <code className="mt-2 block break-all text-xs">
                      {mfaSetup.secret}
                    </code>
                    <p className="mt-2 break-all text-xs text-muted-foreground">
                      {mfaSetup.provisioning_uri}
                    </p>
                  </div>
                  <Field
                    label="Verification code"
                    value={mfaCode}
                    set={setMfaCode}
                  />
                  <button
                    className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
                    disabled={mfaCode.length < 6}
                    onClick={() => verifyMfa.mutate(mfaCode)}
                    type="button"
                  >
                    Verify and enable
                  </button>
                </>
              )}
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <Field
                password
                label="Current password"
                value={disableMfaValues.current_password}
                set={(value) =>
                  setDisableMfaValues({
                    ...disableMfaValues,
                    current_password: value,
                  })
                }
              />
              <Field
                label="Verification code"
                value={disableMfaValues.code}
                set={(value) =>
                  setDisableMfaValues({ ...disableMfaValues, code: value })
                }
              />
              <button
                className="rounded-xl border border-destructive/30 px-4 py-2 text-sm font-semibold text-destructive"
                disabled={
                  !disableMfaValues.current_password ||
                  disableMfaValues.code.length < 6
                }
                onClick={() => disableMfa.mutate(disableMfaValues)}
                type="button"
              >
                Disable two-factor
              </button>
              <div className="border-t pt-4">
                <p className="text-sm font-semibold">Replace recovery codes</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Your existing recovery codes will stop working immediately.
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Field
                    password
                    label="Current password"
                    value={recoveryValues.current_password}
                    set={(value) =>
                      setRecoveryValues({
                        ...recoveryValues,
                        current_password: value,
                      })
                    }
                  />
                  <Field
                    label="Authenticator code"
                    value={recoveryValues.code}
                    set={(value) =>
                      setRecoveryValues({ ...recoveryValues, code: value })
                    }
                  />
                </div>
                <button
                  className="mt-3 rounded-xl border px-4 py-2 text-sm font-semibold disabled:opacity-50"
                  disabled={
                    !recoveryValues.current_password ||
                    recoveryValues.code.length < 6
                  }
                  onClick={() => regenerateRecoveryCodes.mutate(recoveryValues)}
                  type="button"
                >
                  <RefreshCcw className="mr-2 inline size-4" />
                  Regenerate codes
                </button>
              </div>
            </div>
          )}
          {recoveryCodes.length > 0 && (
            <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3">
              <p className="text-xs font-semibold">
                Save these recovery codes. They are shown once.
              </p>
              <div className="mt-2 grid gap-1 sm:grid-cols-2">
                {recoveryCodes.map((code) => (
                  <code className="text-xs" key={code}>
                    {code}
                  </code>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="rounded-lg border px-3 py-1.5 text-xs font-semibold"
                  onClick={() =>
                    void navigator.clipboard.writeText(recoveryCodes.join('\n'))
                  }
                  type="button"
                >
                  <Copy className="mr-1 inline size-3.5" />
                  Copy codes
                </button>
                <button
                  className="rounded-lg border px-3 py-1.5 text-xs font-semibold"
                  onClick={() => downloadRecoveryCodes(recoveryCodes)}
                  type="button"
                >
                  <Download className="mr-1 inline size-3.5" />
                  Download
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>
      <h3 className="mt-8 font-semibold">Active sessions & devices</h3>
      <div className="mt-3 divide-y rounded-xl border">
        {visibleSessions.map((session) => (
          <div className="flex items-center gap-3 p-4" key={session.id}>
            <Laptop className="size-5 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">
                {session.device || 'Unknown device'}{' '}
                {session.current && (
                  <span className="text-primary">· Current</span>
                )}
              </p>
              <p className="text-xs text-muted-foreground">
                {session.browser || 'Browser'} ·{' '}
                {session.os || 'Operating system'} ·{' '}
                {session.ip_address || 'IP unavailable'}
              </p>
            </div>
            {!session.current && (
              <button
                className="text-xs font-semibold text-destructive"
                onClick={() =>
                  void authApi.revokeSession(session.id).then(() =>
                    client.invalidateQueries({
                      queryKey: ['profile-sessions'],
                    }),
                  )
                }
                type="button"
              >
                Revoke
              </button>
            )}
          </div>
        ))}
      </div>
      {sessions.length > sessionsPerPage && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
          <p>
            Showing {(sessionPage - 1) * sessionsPerPage + 1}–
            {Math.min(sessionPage * sessionsPerPage, sessions.length)} of{' '}
            {sessions.length} active sessions
          </p>
          <div className="flex items-center gap-2">
            <button
              className="rounded-lg border px-3 py-1.5 font-semibold text-foreground disabled:opacity-50"
              disabled={sessionPage === 1}
              onClick={() => setSessionPage((page) => page - 1)}
              type="button"
            >
              Previous
            </button>
            <span>
              Page {sessionPage} of {sessionPageCount}
            </span>
            <button
              className="rounded-lg border px-3 py-1.5 font-semibold text-foreground disabled:opacity-50"
              disabled={sessionPage === sessionPageCount}
              onClick={() => setSessionPage((page) => page + 1)}
              type="button"
            >
              Next
            </button>
          </div>
        </div>
      )}
      <h3 className="mt-8 font-semibold">Security & password history</h3>
      <div className="mt-3 divide-y rounded-xl border">
        {securityHistory.length ? (
          securityHistory.map((event, index) => (
            <div
              className="flex items-start gap-3 p-4"
              key={`${event.action}-${event.created_at}-${index}`}
            >
              <ShieldCheck className="mt-0.5 size-4 text-primary" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {event.action.replaceAll('.', ' ')}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {new Date(event.created_at).toLocaleString()}{' '}
                  {event.ip_address ? `Â· ${event.ip_address}` : ''}
                </p>
              </div>
            </div>
          ))
        ) : (
          <p className="p-4 text-sm text-muted-foreground">
            No security events have been recorded for this account yet.
          </p>
        )}
      </div>
      <h3 className="mt-8 font-semibold">Personal API tokens</h3>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          aria-label="API token name"
          className="h-10 flex-1 rounded-xl border bg-background px-3 text-sm"
          onChange={(event) => setTokenName(event.target.value)}
          placeholder="Token name"
          value={tokenName}
        />
        <button
          className="rounded-xl border px-4 py-2 text-sm font-semibold"
          disabled={tokenName.length < 2}
          onClick={() => createToken.mutate({ name: tokenName })}
          type="button"
        >
          <KeyRound className="mr-2 inline size-4" />
          Create token
        </button>
      </div>
      {revealed && (
        <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3">
          <p className="text-xs font-semibold">
            Copy this token now. It will not be shown again.
          </p>
          <code className="mt-2 block break-all text-xs">{revealed}</code>
        </div>
      )}
      <div className="mt-3 divide-y rounded-xl border">
        {tokens.map((token) => (
          <div className="flex items-center gap-3 p-4" key={token.id}>
            <KeyRound className="size-4 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{token.name}</p>
              <p className="text-xs text-muted-foreground">
                {token.token_prefix}•••• · {token.scopes.length} scopes
              </p>
            </div>
            {!token.revoked_at && (
              <button
                className="text-xs font-semibold text-destructive"
                onClick={() => revoke.mutate(token.id)}
                type="button"
              >
                Revoke
              </button>
            )}
          </div>
        ))}
      </div>
    </Section>
  )
}

function AvatarEditor({
  profile,
}: {
  profile: Awaited<ReturnType<typeof profileApi.profile>>
}) {
  const client = useQueryClient()
  const { refreshUser } = useAuth()
  const [validationError, setValidationError] = useState<string | null>(null)
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['profile'] })
    void refreshUser()
  }
  const upload = useMutation({
    mutationFn: profileApi.uploadAvatar,
    onSuccess: refresh,
  })
  const remove = useMutation({
    mutationFn: profileApi.removeAvatar,
    onSuccess: refresh,
  })
  const selectFile = (file: File | undefined) => {
    setValidationError(null)
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setValidationError('Choose a JPEG, PNG, or WebP image.')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setValidationError('Profile pictures must be 5 MB or smaller.')
      return
    }
    upload.mutate(file)
  }
  return (
    <div className="mb-6 flex flex-col gap-4 rounded-2xl border p-4 sm:flex-row sm:items-center">
      <div className="grid size-20 shrink-0 place-items-center overflow-hidden rounded-2xl bg-primary text-xl font-semibold text-primary-foreground">
        {profile.avatar_url ? (
          <AuthenticatedImage
            alt={profile.display_name}
            className="size-full object-cover"
            src={profile.avatar_url}
          />
        ) : (
          profile.first_name.slice(0, 1)
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">Profile picture</p>
        <p className="mt-1 text-xs text-muted-foreground">
          JPEG, PNG, or WebP. Maximum file size 5 MB.
        </p>
        {validationError && (
          <p className="mt-2 text-xs text-destructive" role="alert">
            {validationError}
          </p>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <label className="inline-flex cursor-pointer items-center rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground">
          <Camera className="mr-2 size-4" />
          {profile.avatar_url ? 'Replace' : 'Upload'}
          <input
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            disabled={upload.isPending}
            onChange={(event) => selectFile(event.target.files?.[0])}
            type="file"
          />
        </label>
        {profile.avatar_url && (
          <button
            className="inline-flex items-center rounded-xl border border-destructive/30 px-3 py-2 text-sm font-semibold text-destructive"
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
            type="button"
          >
            <Trash2 className="mr-2 size-4" /> Remove
          </button>
        )}
      </div>
    </div>
  )
}

function AuthenticatedImage({
  src,
  alt,
  className,
}: {
  src: string
  alt: string
  className?: string
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    let createdUrl: string | null = null
    void authenticatedAsset(src)
      .then((blob) => {
        if (!active) return
        createdUrl = URL.createObjectURL(blob)
        setObjectUrl(createdUrl)
      })
      .catch(() => setObjectUrl(null))
    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [src])
  if (!objectUrl)
    return (
      <span aria-label={`${alt} profile picture`} role="img">
        {alt.slice(0, 1)}
      </span>
    )
  return <img alt={alt} className={className} src={objectUrl} />
}

function NotificationPreferencesSection() {
  const preferences = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: notificationApi.preferences,
  })
  const [values, setValues] = useState({
    in_app_enabled: true,
    email_enabled: true,
    browser_enabled: false,
    quiet_hours_enabled: false,
    quiet_hours_start: '22:00',
    quiet_hours_end: '07:00',
    timezone: 'UTC',
    category_rules: {} as Record<string, unknown>,
    delivery_rules: {} as Record<string, unknown>,
  })
  useEffect(() => {
    if (!preferences.data) return
    setValues({
      ...preferences.data,
      quiet_hours_start: preferences.data.quiet_hours_start ?? '22:00',
      quiet_hours_end: preferences.data.quiet_hours_end ?? '07:00',
    })
  }, [preferences.data])
  const save = useMutation({ mutationFn: notificationApi.updatePreferences })
  if (preferences.isLoading) return <Loading />
  if (preferences.isError)
    return <ErrorState retry={() => void preferences.refetch()} />
  const categoryRules = values.category_rules as Record<string, boolean>
  const categories = [
    ['meeting_invitations', 'Meeting invitations'],
    ['meeting_updates', 'Meeting updates'],
    ['meeting_cancellations', 'Meeting cancellations'],
    ['meeting_reminders', 'Meeting reminders'],
    ['chat_messages', 'Chat and messages'],
    ['mentions', 'Mentions'],
  ] as const
  return (
    <Section
      subtitle="Choose how MeetingHQ reaches you while preserving mandatory account-security notices."
      title="Notification preferences"
    >
      <div className="grid gap-3 sm:grid-cols-3">
        <PreferenceToggle
          checked={values.in_app_enabled}
          label="In-app notifications"
          onChange={(checked) =>
            setValues({ ...values, in_app_enabled: checked })
          }
        />
        <PreferenceToggle
          checked={values.email_enabled}
          label="Email notifications"
          onChange={(checked) =>
            setValues({ ...values, email_enabled: checked })
          }
        />
        <PreferenceToggle
          checked={values.browser_enabled}
          label="Browser notifications"
          onChange={(checked) =>
            setValues({ ...values, browser_enabled: checked })
          }
        />
      </div>
      <h3 className="mt-7 font-semibold">Notification categories</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {categories.map(([key, label]) => (
          <PreferenceToggle
            checked={categoryRules[key] ?? true}
            key={key}
            label={label}
            onChange={(checked) =>
              setValues({
                ...values,
                category_rules: { ...categoryRules, [key]: checked },
              })
            }
          />
        ))}
        <PreferenceToggle checked label="Security and account alerts" locked />
      </div>
      <div className="mt-7 rounded-2xl border p-4">
        <PreferenceToggle
          checked={values.quiet_hours_enabled}
          label="Quiet hours"
          onChange={(checked) =>
            setValues({ ...values, quiet_hours_enabled: checked })
          }
        />
        {values.quiet_hours_enabled && (
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <Field
              label="Starts"
              value={values.quiet_hours_start}
              set={(value) =>
                setValues({ ...values, quiet_hours_start: value })
              }
            />
            <Field
              label="Ends"
              value={values.quiet_hours_end}
              set={(value) => setValues({ ...values, quiet_hours_end: value })}
            />
            <Field
              label="Timezone"
              value={values.timezone}
              set={(value) => setValues({ ...values, timezone: value })}
            />
          </div>
        )}
      </div>
      <button
        className="mt-5 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
        disabled={save.isPending}
        onClick={() => save.mutate(values)}
        type="button"
      >
        <Save className="mr-2 inline size-4" /> Save notification preferences
      </button>
    </Section>
  )
}

function PreferenceToggle({
  label,
  checked,
  onChange,
  locked,
}: {
  label: string
  checked: boolean
  onChange?: (checked: boolean) => void
  locked?: boolean
}) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-xl border p-4 text-sm font-medium">
      <span>{label}</span>
      <input
        aria-label={label}
        checked={checked}
        disabled={locked}
        onChange={(event) => onChange?.(event.target.checked)}
        type="checkbox"
      />
    </label>
  )
}

function PreferenceSection({
  center,
  group,
  title,
  icon: Icon,
  save,
}: {
  center: Awaited<ReturnType<typeof profileApi.center>>
  group: string
  title: string
  icon: typeof Bell
  save: (preferences: Record<string, unknown>) => void
}) {
  const preferences = center.preferences
  const initial =
    group === 'communication'
      ? {
          ...(preferences.chat as Record<string, unknown>),
          ...(preferences.mail as Record<string, unknown>),
        }
      : group === 'appearance'
        ? {
            ...(preferences.appearance as Record<string, unknown>),
            ...(preferences.accessibility as Record<string, unknown>),
          }
        : ((preferences[group] as Record<string, unknown>) ?? {})
  const [values, setValues] = useState(initial)
  return (
    <Section
      title={title}
      subtitle="Preferences are saved to your account and follow you across devices."
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(values).map(([key, value]) => (
          <label
            className="flex items-center justify-between gap-4 rounded-xl border p-4"
            key={key}
          >
            <span className="flex items-center gap-2 text-sm font-medium">
              <Icon className="size-4 text-primary" />
              {key.replaceAll('_', ' ')}
            </span>
            {typeof value === 'boolean' ? (
              <input
                checked={value}
                onChange={(event) =>
                  setValues({ ...values, [key]: event.target.checked })
                }
                type="checkbox"
              />
            ) : (
              <input
                className="h-9 max-w-40 rounded-lg border bg-background px-2 text-sm"
                onChange={(event) =>
                  setValues({ ...values, [key]: event.target.value })
                }
                value={String(value)}
              />
            )}
          </label>
        ))}
      </div>
      <button
        className="mt-5 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
        onClick={() => save({ ...preferences, [group]: values })}
        type="button"
      >
        <Save className="mr-2 inline size-4" />
        Save preferences
      </button>
    </Section>
  )
}

function ScheduleSection({
  center,
  save,
}: {
  center: Awaited<ReturnType<typeof profileApi.center>>
  save: (values: Record<string, unknown>) => void
}) {
  const [hours, setHours] = useState({
    start: String(center.working_hours.start ?? '09:00'),
    end: String(center.working_hours.end ?? '17:00'),
  })
  return (
    <Section
      title="Calendar & meeting preferences"
      subtitle="Set working hours, default calendar behavior, and meeting reminders."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Working day starts"
          value={hours.start}
          set={(value) => setHours({ ...hours, start: value })}
        />
        <Field
          label="Working day ends"
          value={hours.end}
          set={(value) => setHours({ ...hours, end: value })}
        />
      </div>
      <button
        className="mt-5 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
        onClick={() =>
          save({ working_hours: { ...center.working_hours, ...hours } })
        }
        type="button"
      >
        <Clock3 className="mr-2 inline size-4" />
        Save schedule
      </button>
    </Section>
  )
}

function ConnectionsSection({
  accounts,
}: {
  accounts: Array<Record<string, unknown>>
}) {
  return (
    <Section
      title="Connected accounts & integrations"
      subtitle="Review identities and external services linked to your profile."
    >
      {accounts.length ? (
        accounts.map((account, index) => (
          <div className="rounded-xl border p-4" key={index}>
            {String(account.provider ?? 'Connected account')}
          </div>
        ))
      ) : (
        <Empty
          title="No connected accounts"
          detail="Connections approved by your administrator will appear here."
        />
      )}
    </Section>
  )
}

function OrganizationSection({
  profile,
  center,
}: {
  profile: Awaited<ReturnType<typeof profileApi.profile>>
  center: Awaited<ReturnType<typeof profileApi.center>>
}) {
  const permissions = [
    ...new Set(
      profile.roles.flatMap((role) =>
        role.permissions.map((permission) => permission.name),
      ),
    ),
  ]
  return (
    <Section
      title="Organization & access"
      subtitle="Your tenant membership, roles, effective permissions, storage, and licensing."
    >
      <div className="grid gap-4 sm:grid-cols-3">
        <Metric label="Roles" value={profile.roles.length} />
        <Metric label="Permissions" value={permissions.length} />
        <Metric
          label="Storage used"
          value={`${(center.storage_used_bytes / 1_048_576).toFixed(1)} MB`}
        />
      </div>
      <div className="mt-5 rounded-xl border p-4">
        <p className="text-sm font-semibold">License</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {center.license_name}
        </p>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        {profile.roles.map((role) => (
          <span
            className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary"
            key={role.id}
          >
            {role.name}
          </span>
        ))}
      </div>
    </Section>
  )
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <section>
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      <div className="mt-6">{children}</div>
    </section>
  )
}
function Card({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: typeof LockKeyhole
  children: ReactNode
}) {
  return (
    <div className="rounded-2xl border p-5">
      <h3 className="mb-4 flex items-center gap-2 font-semibold">
        <Icon className="size-4 text-primary" />
        {title}
      </h3>
      {children}
    </div>
  )
}
function Field({
  label,
  value,
  set,
  disabled,
  password,
}: {
  label: string
  value: string
  set: (value: string) => void
  disabled?: boolean
  password?: boolean
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 disabled:opacity-60"
        disabled={disabled}
        onChange={(event) => set(event.target.value)}
        type={password ? 'password' : 'text'}
        value={value}
      />
    </label>
  )
}
function SelectField({
  label,
  value,
  values,
  set,
}: {
  label: string
  value: string
  values: string[]
  set: (value: string) => void
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <select
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 capitalize"
        onChange={(event) => set(event.target.value)}
        value={value}
      >
        {values.map((item) => (
          <option key={item} value={item}>
            {item.replaceAll('_', ' ')}
          </option>
        ))}
      </select>
    </label>
  )
}
function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  )
}
function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-dashed p-10 text-center">
      <Link2 className="mx-auto size-7 text-muted-foreground" />
      <p className="mt-3 font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
    </div>
  )
}
function Loading() {
  return (
    <div aria-label="Loading profile" className="space-y-4">
      {[1, 2, 3].map((item) => (
        <div className="h-20 animate-pulse rounded-xl bg-muted" key={item} />
      ))}
    </div>
  )
}
function ErrorState({ retry }: { retry: () => void }) {
  return (
    <div className="p-10 text-center">
      <p className="font-semibold">Profile could not be loaded</p>
      <button
        className="mt-3 text-sm font-semibold text-primary"
        onClick={retry}
        type="button"
      >
        Retry
      </button>
    </div>
  )
}

function resolveSection(pathname: string, search: string): Section {
  if (
    pathname.startsWith('/profile/security') ||
    pathname === '/profile/sessions'
  )
    return 'security'
  if (pathname === '/profile/notifications') return 'notifications'
  if (pathname === '/profile/connections') return 'connections'
  if (pathname === '/profile/organization') return 'organization'
  if (pathname === '/profile/preferences') {
    const requested = new URLSearchParams(search).get('section')
    if (requested === 'schedule' || requested === 'communication')
      return requested
    return 'appearance'
  }
  return 'personal'
}

function downloadRecoveryCodes(codes: string[]) {
  const blob = new Blob(
    [
      `MeetingHQ recovery codes\nGenerated: ${new Date().toISOString()}\n\n${codes.join('\n')}\n`,
    ],
    { type: 'text/plain;charset=utf-8' },
  )
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'meetinghq-recovery-codes.txt'
  link.click()
  URL.revokeObjectURL(url)
}
