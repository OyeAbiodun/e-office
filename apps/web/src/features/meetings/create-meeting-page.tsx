import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Paperclip,
  Search,
  Users,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { meetingApi } from '@/features/meetings/api'
import { organizationApi } from '@/features/organizations/api'
import { userAdminApi } from '@/features/users/api'

const steps = [
  'Meeting details',
  'Date & time',
  'Participants',
  'Resources',
  'Agenda',
  'Review',
]

export function CreateMeetingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const workspaces = useQuery({
    queryKey: ['workspaces'],
    queryFn: organizationApi.workspaces,
  })
  const members = useQuery({
    queryKey: ['meeting-participants'],
    queryFn: () => userAdminApi.list({ status: 'active' }),
  })
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const tomorrow = new Date(Date.now() + 86_400_000)
  tomorrow.setMinutes(0, 0, 0)
  const [form, setForm] = useState({
    title: '',
    description: '',
    meeting_type: 'standard',
    location_type: 'virtual',
    meeting_url: '',
    location: '',
    workspace_id: '',
    start_datetime: tomorrow.toISOString().slice(0, 16),
    end_datetime: new Date(tomorrow.getTime() + 3_600_000)
      .toISOString()
      .slice(0, 16),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    visibility: 'members',
    attendee_ids: [] as string[],
    cohost_ids: [] as string[],
    recurrence_frequency: 'none',
    recurrence_interval: '1',
    agenda: [] as string[],
  })
  const [participantSearch, setParticipantSearch] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [attachments, setAttachments] = useState<File[]>([])
  const departments = useMemo(
    () => [
      ...new Set(
        (members.data ?? [])
          .map((member) => member.department)
          .filter((value): value is string => Boolean(value)),
      ),
    ],
    [members.data],
  )
  const participantRows = useMemo(
    () =>
      (members.data ?? []).filter(
        (member) =>
          `${member.display_name} ${member.email}`
            .toLowerCase()
            .includes(participantSearch.toLowerCase()) &&
          (!departmentFilter || member.department === departmentFilter) &&
          (!roleFilter ||
            member.roles.some((role) => role.name === roleFilter)),
      ),
    [departmentFilter, members.data, participantSearch, roleFilter],
  )
  const update = (key: string, value: string | string[]) =>
    setForm((current) => ({ ...current, [key]: value }))
  const submit = async () => {
    setError('')
    try {
      const meeting = await meetingApi.create({
        ...form,
        agenda: form.agenda.filter(Boolean).join('\n') || null,
        recurrence:
          form.recurrence_frequency === 'none'
            ? null
            : {
                frequency: form.recurrence_frequency,
                interval: Number(form.recurrence_interval),
                days_of_week: [],
                end_date: null,
                occurrence_count: null,
                skip_holidays: false,
              },
        workspace_id: form.workspace_id || workspaces.data?.[0]?.id,
        start_datetime: new Date(form.start_datetime).toISOString(),
        end_datetime: new Date(form.end_datetime).toISOString(),
      })
      for (const [index, title] of form.agenda.entries()) {
        if (title.trim())
          await meetingApi.add(meeting.id, 'agenda', {
            title,
            duration_minutes: 10,
            sort_order: index,
          })
      }
      for (const attachment of attachments)
        await meetingApi.uploadArtifact(meeting.id, attachment)
      await queryClient.invalidateQueries({ queryKey: ['meeting-dashboard'] })
      await navigate({
        to: '/meetings/$meetingId',
        params: { meetingId: meeting.id },
      })
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'Meeting could not be scheduled',
      )
    }
  }
  const canContinue = step !== 0 || form.title.trim().length > 0
  return (
    <div className="mx-auto max-w-5xl p-5 sm:p-8">
      <div className="mb-8">
        <p className="text-sm font-medium text-primary">New meeting</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Plan a great conversation
        </h1>
      </div>
      <ol className="mb-8 grid grid-cols-3 gap-2 lg:grid-cols-6">
        {steps.map((label, index) => (
          <li
            className={`rounded-xl border p-3 text-xs ${index === step ? 'border-primary bg-primary/5 text-primary' : index < step ? 'bg-muted' : 'text-muted-foreground'}`}
            key={label}
          >
            <span className="mb-1 block font-semibold">
              {index < step ? <Check className="size-3.5" /> : `0${index + 1}`}
            </span>
            {label}
          </li>
        ))}
      </ol>
      <section className="min-h-[360px] rounded-3xl border bg-card p-6 shadow-sm sm:p-8">
        {error && (
          <div
            role="alert"
            className="mb-5 rounded-xl bg-red-500/10 p-3 text-sm text-red-600"
          >
            {error}
          </div>
        )}
        {step === 0 && (
          <Fields title="What are you meeting about?">
            <Input
              label="Title"
              value={form.title}
              onChange={(value) => update('title', value)}
            />
            <TextArea
              label="Description"
              value={form.description}
              onChange={(value) => update('description', value)}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Select
                label="Meeting type"
                value={form.meeting_type}
                options={[
                  'standard',
                  'planning',
                  'one-on-one',
                  'standup',
                  'retrospective',
                ]}
                onChange={(value) => update('meeting_type', value)}
              />
              <Select
                label="Visibility"
                value={form.visibility}
                options={['members', 'private', 'public']}
                onChange={(value) => update('visibility', value)}
              />
            </div>
          </Fields>
        )}
        {step === 1 && (
          <Fields title="Find the right time">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Starts"
                type="datetime-local"
                value={form.start_datetime}
                onChange={(value) => update('start_datetime', value)}
              />
              <Input
                label="Ends"
                type="datetime-local"
                value={form.end_datetime}
                onChange={(value) => update('end_datetime', value)}
              />
            </div>
            <Input
              label="Timezone"
              value={form.timezone}
              onChange={(value) => update('timezone', value)}
            />
          </Fields>
        )}
        {step === 2 && (
          <Fields title="Invite participants">
            <div className="grid gap-3 md:grid-cols-[1fr_180px_180px]">
              <label className="relative">
                <span className="sr-only">Search participants</span>
                <Search className="absolute left-3 top-3.5 size-4 text-muted-foreground" />
                <input
                  aria-label="Search participants"
                  className="h-11 w-full rounded-xl border bg-background pl-9 pr-3"
                  onChange={(event) => setParticipantSearch(event.target.value)}
                  placeholder="Name or email"
                  value={participantSearch}
                />
              </label>
              <select
                aria-label="Filter participants by department"
                className="h-11 rounded-xl border bg-background px-3"
                onChange={(event) => setDepartmentFilter(event.target.value)}
                value={departmentFilter}
              >
                <option value="">All departments</option>
                {departments.map((department) => (
                  <option key={department}>{department}</option>
                ))}
              </select>
              <select
                aria-label="Filter participants by role"
                className="h-11 rounded-xl border bg-background px-3"
                onChange={(event) => setRoleFilter(event.target.value)}
                value={roleFilter}
              >
                <option value="">All roles</option>
                {[
                  ...new Set(
                    (members.data ?? []).flatMap((member) =>
                      member.roles.map((role) => role.name),
                    ),
                  ),
                ].map((role) => (
                  <option key={role}>{role}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-wrap gap-2">
              {departments.map((department) => (
                <button
                  className="rounded-full border px-3 py-1.5 text-xs font-medium"
                  key={department}
                  onClick={() =>
                    update('attendee_ids', [
                      ...new Set([
                        ...form.attendee_ids,
                        ...(members.data ?? [])
                          .filter((member) => member.department === department)
                          .map((member) => member.id),
                      ]),
                    ])
                  }
                  type="button"
                >
                  Add {department}
                </button>
              ))}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {participantRows.map((member) => {
                const selected = form.attendee_ids.includes(member.id)
                return (
                  <div
                    className={`flex items-center gap-3 rounded-xl border p-4 text-left ${selected ? 'border-primary bg-primary/5' : ''}`}
                    key={member.id}
                  >
                    <button
                      className="flex min-w-0 flex-1 items-center gap-3 text-left"
                      onClick={() =>
                        update(
                          'attendee_ids',
                          selected
                            ? form.attendee_ids.filter((id) => id !== member.id)
                            : [...form.attendee_ids, member.id],
                        )
                      }
                      type="button"
                    >
                      <span className="grid size-9 place-items-center rounded-full bg-muted">
                        <Users className="size-4" />
                      </span>
                      <span className="min-w-0">
                        <span className="block font-medium">
                          {member.display_name}
                        </span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {member.email} ·{' '}
                          {member.department || 'No department'}
                        </span>
                      </span>
                    </button>
                    {selected && (
                      <label className="flex items-center gap-1 text-xs">
                        <input
                          checked={form.cohost_ids.includes(member.id)}
                          onChange={(event) =>
                            update(
                              'cohost_ids',
                              event.target.checked
                                ? [...form.cohost_ids, member.id]
                                : form.cohost_ids.filter(
                                    (id) => id !== member.id,
                                  ),
                            )
                          }
                          type="checkbox"
                        />
                        Co-host
                      </label>
                    )}
                  </div>
                )
              })}
            </div>
          </Fields>
        )}
        {step === 3 && (
          <Fields title="Choose where to meet">
            <Select
              label="Location"
              value={form.location_type}
              options={['virtual', 'in-person', 'hybrid']}
              onChange={(value) => update('location_type', value)}
            />
            <Input
              label="Meeting link (optional)"
              value={form.meeting_url}
              onChange={(value) => update('meeting_url', value)}
            />
            <Input
              label="Physical location (optional)"
              value={form.location}
              onChange={(value) => update('location', value)}
            />
            <Select
              label="Workspace"
              value={form.workspace_id || workspaces.data?.[0]?.id || ''}
              options={(workspaces.data ?? []).map((item) => item.id)}
              labels={(workspaces.data ?? []).map((item) => item.name)}
              onChange={(value) => update('workspace_id', value)}
            />
          </Fields>
        )}
        {step === 4 && (
          <Fields title="Build the agenda">
            <div className="grid gap-4 sm:grid-cols-2">
              <Select
                label="Repeat"
                value={form.recurrence_frequency}
                options={['none', 'daily', 'weekly', 'monthly', 'custom']}
                onChange={(value) => update('recurrence_frequency', value)}
              />
              {form.recurrence_frequency !== 'none' && (
                <Input
                  label="Repeat interval"
                  type="number"
                  value={form.recurrence_interval}
                  onChange={(value) => update('recurrence_interval', value)}
                />
              )}
            </div>
            <p className="mb-4 text-sm text-muted-foreground">
              Add structured topics now. You can reorder and expand them after
              scheduling.
            </p>
            {[...form.agenda, ''].map((item, index) => (
              <Input
                key={index}
                label={`Topic ${index + 1}`}
                value={item}
                onChange={(value) => {
                  const agenda = [...form.agenda]
                  agenda[index] = value
                  update(
                    'agenda',
                    agenda.filter(
                      (entry, position) => entry || position <= index,
                    ),
                  )
                }}
              />
            ))}
            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed p-4 text-sm">
              <Paperclip className="size-5 text-primary" />
              <span className="flex-1">
                <span className="block font-medium">Meeting attachments</span>
                <span className="text-xs text-muted-foreground">
                  {attachments.length
                    ? attachments.map((file) => file.name).join(', ')
                    : 'Add agenda documents or reference files'}
                </span>
              </span>
              <input
                className="sr-only"
                multiple
                onChange={(event) =>
                  setAttachments(Array.from(event.target.files ?? []))
                }
                type="file"
              />
            </label>
          </Fields>
        )}
        {step === 5 && (
          <Fields title="Ready to schedule">
            <div className="grid gap-4 rounded-2xl bg-muted/50 p-5 sm:grid-cols-2">
              <Summary label="Meeting" value={form.title} />
              <Summary
                label="When"
                value={`${new Date(form.start_datetime).toLocaleString()} – ${new Date(form.end_datetime).toLocaleTimeString()}`}
              />
              <Summary
                label="Participants"
                value={`${form.attendee_ids.length + 1} people`}
              />
              <Summary label="Location" value={form.location_type} />
              <Summary
                label="Agenda"
                value={`${form.agenda.filter(Boolean).length} topics`}
              />
              <Summary label="Timezone" value={form.timezone} />
            </div>
          </Fields>
        )}
      </section>
      <div className="mt-5 flex justify-between">
        <button
          className="inline-flex h-11 items-center gap-2 rounded-xl border px-4 text-sm font-medium disabled:opacity-40"
          disabled={step === 0}
          onClick={() => setStep((value) => value - 1)}
        >
          <ArrowLeft className="size-4" /> Back
        </button>
        {step < 5 ? (
          <button
            className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-medium text-primary-foreground disabled:opacity-40"
            disabled={!canContinue}
            onClick={() => setStep((value) => value + 1)}
          >
            Continue <ArrowRight className="size-4" />
          </button>
        ) : (
          <button
            className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-medium text-primary-foreground"
            onClick={() => void submit()}
          >
            <Check className="size-4" /> Schedule meeting
          </button>
        )}
      </div>
    </div>
  )
}

function Fields({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-5">
      <h2 className="text-xl font-semibold">{title}</h2>
      {children}
    </div>
  )
}
function Input({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 font-normal"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
function TextArea({
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
      <textarea
        className="mt-2 min-h-28 w-full rounded-xl border bg-background p-3 font-normal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
function Select({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  labels?: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <select
        className="mt-2 h-11 w-full rounded-xl border bg-background px-3 font-normal capitalize"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option, index) => (
          <option key={option} value={option}>
            {labels?.[index] ?? option.replaceAll('-', ' ')}
          </option>
        ))}
      </select>
    </label>
  )
}
function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 font-medium capitalize">{value}</p>
    </div>
  )
}
