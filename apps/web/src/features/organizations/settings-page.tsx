import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

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
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (organization.data) {
      setName(organization.data.name)
      setTimezone(organization.data.timezone)
      setLanguage(organization.data.default_language)
      setColor(organization.data.brand_color)
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
      })
      await queryClient.invalidateQueries({ queryKey: ['organization'] })
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="mx-auto max-w-3xl p-5 sm:p-8">
      <h1 className="text-3xl font-semibold">Organization settings</h1>
      <p className="mt-2 text-muted-foreground">
        Branding, locale, and organization defaults.
      </p>
      <div className="mt-8 space-y-5 rounded-2xl border bg-card p-6">
        <Field label="Organization name" value={name} onChange={setName} />
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Timezone" value={timezone} onChange={setTimezone} />
          <Field label="Language" value={language} onChange={setLanguage} />
        </div>
        <label className="block text-sm font-medium">
          Brand color
          <input
            className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
            type="color"
            value={color}
            onChange={(event) => setColor(event.target.value)}
          />
        </label>
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
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 outline-none focus:border-primary"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
