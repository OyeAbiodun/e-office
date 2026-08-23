import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import { Check, Clock3 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { meetingApi } from '@/features/meetings/api'

export function EditMeetingPage() {
  const { meetingId } = useParams({
    from: '/_protected/_app/meetings/$meetingId/edit',
  })
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const meeting = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => meetingApi.get(meetingId),
  })
  const [form, setForm] = useState({
    title: '',
    description: '',
    start_datetime: '',
    end_datetime: '',
    timezone: 'UTC',
  })
  const [error, setError] = useState('')
  useEffect(() => {
    if (!meeting.data) return
    setForm({
      title: meeting.data.title,
      description: meeting.data.description ?? '',
      start_datetime: new Date(meeting.data.start_datetime)
        .toISOString()
        .slice(0, 16),
      end_datetime: new Date(meeting.data.end_datetime)
        .toISOString()
        .slice(0, 16),
      timezone: meeting.data.timezone,
    })
  }, [meeting.data])
  const save = async () => {
    setError('')
    try {
      await meetingApi.update(meetingId, {
        title: form.title,
        description: form.description,
      })
      if (
        meeting.data &&
        (new Date(form.start_datetime).toISOString() !==
          meeting.data.start_datetime ||
          new Date(form.end_datetime).toISOString() !==
            meeting.data.end_datetime)
      ) {
        await meetingApi.reschedule(meetingId, {
          start_datetime: new Date(form.start_datetime).toISOString(),
          end_datetime: new Date(form.end_datetime).toISOString(),
          timezone: form.timezone,
          room_id: meeting.data.room_id,
        })
      }
      await queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] })
      await navigate({ to: '/meetings/$meetingId', params: { meetingId } })
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Meeting could not be saved',
      )
    }
  }
  return (
    <div className="mx-auto max-w-3xl p-5 sm:p-8">
      <p className="text-sm font-medium text-primary">Meeting settings</p>
      <h1 className="mt-2 text-3xl font-semibold">Edit and reschedule</h1>
      <div className="mt-8 space-y-5 rounded-3xl border bg-card p-6 shadow-sm sm:p-8">
        {error && (
          <div
            role="alert"
            className="rounded-xl bg-red-500/10 p-3 text-sm text-red-600"
          >
            {error}
          </div>
        )}
        <Field
          label="Title"
          value={form.title}
          onChange={(title) => setForm({ ...form, title })}
        />
        <label className="block text-sm font-medium">
          Description
          <textarea
            className="mt-2 min-h-28 w-full rounded-xl border bg-background p-3 font-normal"
            value={form.description}
            onChange={(event) =>
              setForm({ ...form, description: event.target.value })
            }
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Starts"
            type="datetime-local"
            value={form.start_datetime}
            onChange={(start_datetime) => setForm({ ...form, start_datetime })}
          />
          <Field
            label="Ends"
            type="datetime-local"
            value={form.end_datetime}
            onChange={(end_datetime) => setForm({ ...form, end_datetime })}
          />
        </div>
        <div className="rounded-xl bg-primary/5 p-4 text-sm text-muted-foreground">
          <Clock3 className="mr-2 inline size-4 text-primary" />
          Any time change is revalidated by the Scheduling Engine before it is
          saved.
        </div>
        <button
          className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-medium text-primary-foreground"
          onClick={() => void save()}
        >
          <Check className="size-4" />
          Save changes
        </button>
      </div>
    </div>
  )
}

function Field({
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
