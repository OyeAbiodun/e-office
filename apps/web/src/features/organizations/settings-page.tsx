import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { PageHeader } from '@/components/page'
import { notify } from '@/components/feedback/events'
import { organizationApi } from '@/features/organizations/api'

export function OrganizationSettingsPage() {
  const queryClient = useQueryClient()
  const organization = useQuery({
    queryKey: ['organization'],
    queryFn: organizationApi.organization,
  })
  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [language, setLanguage] = useState('en')
  const [color, setColor] = useState('#2563eb')
  const [logoUrl, setLogoUrl] = useState('')
  const [country, setCountry] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [website, setWebsite] = useState('')
  const [streetAddress, setStreetAddress] = useState('')
  const [city, setCity] = useState('')
  const [postalCode, setPostalCode] = useState('')
  const [sessionTimeout, setSessionTimeout] = useState(1440)
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (organization.data) {
      setName(organization.data.name)
      setTimezone(organization.data.timezone)
      setLanguage(organization.data.default_language)
      setColor(organization.data.brand_color)
      setLogoUrl(organization.data.logo_url ?? '')
      setCountry(organization.data.country ?? '')
      setContactEmail(String(organization.data.settings.contact_email ?? ''))
      setContactPhone(String(organization.data.settings.contact_phone ?? ''))
      setWebsite(String(organization.data.settings.website ?? ''))
      setStreetAddress(String(organization.data.settings.street_address ?? ''))
      setCity(String(organization.data.settings.city ?? ''))
      setPostalCode(String(organization.data.settings.postal_code ?? ''))
      setSessionTimeout(
        Number(organization.data.settings.session_timeout_minutes ?? 1440),
      )
    }
  }, [organization.data])
  const save = async () => {
    setSaving(true)
    try {
      await organizationApi.updateOrganization({
        name,
        timezone,
        default_language: language,
        brand_color: color,
        logo_url: logoUrl || null,
        country: country || null,
        settings: {
          ...organization.data?.settings,
          contact_email: contactEmail || null,
          contact_phone: contactPhone || null,
          website: website || null,
          street_address: streetAddress || null,
          city: city || null,
          postal_code: postalCode || null,
          session_timeout_minutes: sessionTimeout,
        },
      })
      await queryClient.invalidateQueries({ queryKey: ['organization'] })
      notify({
        tone: 'success',
        title: 'Organization settings saved',
        description:
          'Profile, branding, contact details, and defaults are up to date.',
      })
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="page-container mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow="Organization administration"
        title="Organization settings"
        description="Manage your organization identity, public contact details, and everyday defaults. Platform-wide controls remain in Platform Management."
      />
      <section className="rounded-2xl border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Organization profile</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The identity employees see throughout OfficeFlow.
        </p>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <Field label="Organization name" value={name} onChange={setName} />
          <Field
            label="Country code"
            value={country}
            onChange={setCountry}
            placeholder="US"
          />
        </div>
      </section>
      <section className="rounded-2xl border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Branding</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Keep the employee experience recognizable and consistent.
        </p>
        <div className="mt-5 grid gap-5 sm:grid-cols-[1fr_12rem]">
          <Field
            label="Logo URL"
            value={logoUrl}
            onChange={setLogoUrl}
            placeholder="https://…"
          />
          <div>
            <label className="block text-sm font-medium">
              Brand color
              <span className="mt-2 flex gap-2">
                <input
                  aria-label="Brand color picker"
                  className="h-11 w-14 rounded-xl border bg-background p-1"
                  type="color"
                  value={color}
                  onChange={(event) => setColor(event.target.value)}
                />
                <input
                  aria-label="Brand color HEX value"
                  className="h-11 min-w-0 flex-1 rounded-xl border bg-background px-3 font-mono uppercase"
                  maxLength={7}
                  pattern="#[0-9a-fA-F]{6}"
                  value={color}
                  onChange={(event) => setColor(event.target.value)}
                />
              </span>
            </label>
            <div aria-label="Brand color presets" className="mt-3 flex gap-2">
              {['#2563eb', '#7c3aed', '#0f766e', '#c2410c', '#be185d'].map(
                (preset) => (
                  <button
                    aria-label={`Use ${preset}`}
                    className="size-7 rounded-full border-2 border-background shadow ring-1 ring-border"
                    key={preset}
                    onClick={() => setColor(preset)}
                    style={{ backgroundColor: preset }}
                    type="button"
                  />
                ),
              )}
            </div>
          </div>
        </div>
        <div className="mt-5 rounded-xl border p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Live preview
          </p>
          <button
            className="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white"
            style={{ backgroundColor: color }}
            type="button"
          >
            Primary action
          </button>
          <a
            className="ml-4 text-sm font-semibold"
            href="#branding"
            style={{ color }}
          >
            Branded link
          </a>
        </div>
      </section>
      <section className="rounded-2xl border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Contact details</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Business contact information used by administrators and employees.
        </p>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <Field
            label="Contact email"
            value={contactEmail}
            onChange={setContactEmail}
            type="email"
          />
          <Field
            label="Contact phone"
            value={contactPhone}
            onChange={setContactPhone}
          />
          <Field
            label="Website"
            value={website}
            onChange={setWebsite}
            placeholder="https://…"
          />
          <Field
            label="Street address"
            value={streetAddress}
            onChange={setStreetAddress}
          />
          <Field label="City" value={city} onChange={setCity} />
          <Field
            label="Postal code"
            value={postalCode}
            onChange={setPostalCode}
          />
        </div>
      </section>
      <section className="rounded-2xl border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Security</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          End inactive sign-ins across this organization. Enforcement occurs on
          the server when the browser rotates its refresh session; an existing
          access token can remain valid for no more than 15 minutes.
        </p>
        <label className="mt-5 block max-w-sm text-sm font-medium">
          Inactivity timeout (minutes)
          <input
            className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
            max={43200}
            min={15}
            onChange={(event) => setSessionTimeout(Number(event.target.value))}
            type="number"
            value={sessionTimeout}
          />
          <span className="mt-2 block text-xs text-muted-foreground">
            Default 1,440 minutes (24 hours). Allowed range: 15 minutes to 30
            days. Changes apply to existing sessions at their next refresh.
          </span>
        </label>
      </section>
      <section className="rounded-2xl border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Defaults</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Applied when a more specific employee or workspace preference is not
          set.
        </p>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Timezone
            <select
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
            >
              {[
                'UTC',
                'America/Chicago',
                'America/New_York',
                'Europe/London',
                'Africa/Lagos',
              ].map((zone) => (
                <option key={zone}>{zone}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Default language
            <select
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
            >
              <option value="en">English</option>
              <option value="fr">French</option>
              <option value="es">Spanish</option>
            </select>
          </label>
        </div>
      </section>
      <div className="flex justify-end rounded-2xl border bg-card p-4 shadow-sm">
        <button
          className="rounded-xl bg-primary px-5 py-2.5 font-medium text-primary-foreground disabled:opacity-60"
          disabled={saving}
          onClick={() => void save()}
          type="button"
        >
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 outline-none focus:border-primary"
        value={value}
        placeholder={placeholder}
        type={type}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
