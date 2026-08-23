import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import {
  BarChart3,
  CheckCircle2,
  Clock3,
  Copy,
  FileText,
  ListChecks,
  Paperclip,
  Plus,
  Users,
  Video,
} from 'lucide-react'
import { useState } from 'react'

import { meetingApi } from '@/features/meetings/api'
import { useAuth } from '@/features/auth/auth-store'

type Section =
  | 'agenda'
  | 'notes'
  | 'decisions'
  | 'actions'
  | 'attendees'
  | 'artifacts'
  | 'recordings'
  | 'follow_ups'
  | 'analytics'
  | 'history'

export function MeetingDetailPage() {
  const { user } = useAuth()
  const { meetingId } = useParams({
    from: '/_protected/_app/meetings/$meetingId',
  })
  const queryClient = useQueryClient()
  const meeting = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => meetingApi.get(meetingId),
  })
  const history = useQuery({
    queryKey: ['meeting-history', meetingId],
    queryFn: () => meetingApi.history(meetingId),
  })
  const analytics = useQuery({
    queryKey: ['meeting-analytics', meetingId],
    queryFn: () => meetingApi.analytics(meetingId),
  })
  const [section, setSection] = useState<Section>('agenda')
  const [value, setValue] = useState('')
  const refresh = async () => {
    setValue('')
    await queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] })
    await queryClient.invalidateQueries({
      queryKey: ['meeting-history', meetingId],
    })
    await queryClient.invalidateQueries({
      queryKey: ['meeting-analytics', meetingId],
    })
  }
  const add = async () => {
    if (!value.trim()) return
    const bodies: Record<Section, object> = {
      agenda: {
        title: value,
        duration_minutes: 10,
        sort_order: meeting.data?.agenda.length ?? 0,
      },
      notes: { content: value },
      decisions: { title: value, status: 'recorded' },
      actions: { title: value, priority: 'medium', status: 'open' },
      attendees: {},
      artifacts: {
        artifact_type: 'link',
        title: value,
        storage_key: value.startsWith('http') ? value : null,
      },
      recordings: {},
      follow_ups: {
        follow_up_type: 'summary',
        scheduled_for: new Date(Date.now() + 60 * 60_000).toISOString(),
        payload: { note: value },
      },
      analytics: {},
      history: {},
    }
    if (section === 'follow_ups')
      await meetingApi.followUp(meetingId, bodies[section])
    else await meetingApi.add(meetingId, section, bodies[section])
    await refresh()
  }
  if (meeting.isLoading)
    return <p className="p-8 text-muted-foreground">Opening meeting…</p>
  if (!meeting.data)
    return (
      <div role="alert" className="p-8 text-red-600">
        Meeting could not be loaded.
      </div>
    )
  const data = meeting.data
  const isOrganizer = data.organizer_id === user?.id
  const sections: Array<[Section, string, number]> = [
    ['agenda', 'Agenda', data.agenda.length],
    ['notes', 'Notes', data.notes.length],
    ['decisions', 'Decisions', data.decisions.length],
    ['actions', 'Action items', data.action_items.length],
    ['attendees', 'RSVP', data.attendees.length],
    ['artifacts', 'Files & artifacts', data.artifacts.length],
    ['recordings', 'Recordings', data.recordings.length],
    ['follow_ups', 'Follow-ups', data.follow_ups.length],
    ['analytics', 'Analytics', 0],
    ['history', 'History', history.data?.length ?? 0],
  ]
  const itemsBySection: Record<Section, Array<Record<string, unknown>>> = {
    agenda: data.agenda,
    notes: data.notes,
    decisions: data.decisions,
    actions: data.action_items,
    attendees: data.attendees,
    artifacts: data.artifacts,
    recordings: data.recordings,
    follow_ups: data.follow_ups,
    analytics: [],
    history: history.data ?? [],
  }
  const items = itemsBySection[section]
  return (
    <div className="mx-auto max-w-7xl p-5 sm:p-8">
      <div className="rounded-3xl border bg-gradient-to-br from-card via-card to-primary/5 p-6 shadow-sm sm:p-8">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
          <div>
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium capitalize text-primary">
              {data.status.replace('_', ' ')}
            </span>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight">
              {data.title}
            </h1>
            <p className="mt-3 max-w-3xl leading-7 text-muted-foreground">
              {data.description || 'No description added.'}
            </p>
            <div className="mt-5 flex flex-wrap gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-2">
                <Clock3 className="size-4" />
                {new Date(data.start_datetime).toLocaleString()}
              </span>
              <span className="flex items-center gap-2">
                <Users className="size-4" />
                {data.attendees.length} participants
              </span>
            </div>
          </div>
          {isOrganizer && (
            <div className="flex flex-wrap gap-2">
              <Link
                className="rounded-xl border bg-background px-4 py-2.5 text-sm font-medium"
                params={{ meetingId }}
                to="/meetings/$meetingId/edit"
              >
                Edit & reschedule
              </Link>
              <button
                className="rounded-xl border bg-background px-4 py-2.5 text-sm font-medium"
                onClick={() => void meetingApi.duplicate(meetingId)}
              >
                <Copy className="mr-2 inline size-4" />
                Duplicate
              </button>
              {data.status === 'scheduled' && (
                <button
                  className="rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground"
                  onClick={() =>
                    void meetingApi
                      .transition(meetingId, 'in_progress')
                      .then(refresh)
                  }
                >
                  Start
                </button>
              )}
              {data.status === 'in_progress' && (
                <button
                  className="rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground"
                  onClick={() =>
                    void meetingApi
                      .transition(meetingId, 'completed')
                      .then(refresh)
                  }
                >
                  <CheckCircle2 className="mr-2 inline size-4" />
                  Complete
                </button>
              )}
              {['scheduled', 'confirmed', 'in_progress'].includes(
                data.status,
              ) && (
                <button
                  className="rounded-xl border border-red-500/30 px-4 py-2.5 text-sm font-medium text-red-600"
                  onClick={() =>
                    void meetingApi
                      .transition(meetingId, 'cancelled')
                      .then(refresh)
                  }
                >
                  Cancel
                </button>
              )}
              {['completed', 'cancelled'].includes(data.status) && (
                <button
                  className="rounded-xl border px-4 py-2.5 text-sm font-medium"
                  onClick={() =>
                    void meetingApi
                      .transition(meetingId, 'archived')
                      .then(refresh)
                  }
                >
                  Archive
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[230px_1fr]">
        <nav className="space-y-1 rounded-2xl border bg-card p-2 lg:self-start">
          {sections.map(([id, label, count]) => (
            <button
              className={`flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm font-medium ${section === id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-muted'}`}
              key={id}
              onClick={() => setSection(id)}
            >
              <span>{label}</span>
              <span className="rounded-full bg-background px-2 py-0.5 text-xs">
                {count}
              </span>
            </button>
          ))}
        </nav>
        <section className="rounded-2xl border bg-card p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-xl font-semibold">
              {sections.find(([id]) => id === section)?.[1]}
            </h2>
            {!['attendees', 'history', 'analytics', 'recordings'].includes(
              section,
            ) && <Plus className="size-5 text-primary" />}
          </div>
          {section === 'attendees' && (
            <div className="mb-5 flex gap-2">
              {['accepted', 'tentative', 'declined'].map((status) => (
                <button
                  className="rounded-xl border px-3 py-2 text-sm capitalize hover:border-primary hover:text-primary"
                  key={status}
                  onClick={() =>
                    void meetingApi.rsvp(meetingId, status).then(refresh)
                  }
                >
                  {status}
                </button>
              ))}
            </div>
          )}
          {section === 'artifacts' && (
            <label className="mb-5 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed p-4 text-sm font-medium hover:border-primary hover:text-primary">
              <Paperclip className="size-4" />
              Upload attachment
              <input
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file)
                    void meetingApi
                      .uploadArtifact(meetingId, file)
                      .then(refresh)
                }}
                type="file"
              />
            </label>
          )}
          {section === 'recordings' && (
            <button
              className="mb-5 flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground"
              onClick={() =>
                void meetingApi
                  .addRecording(meetingId, {
                    provider: 'meetinghq',
                    status: 'ready',
                    transcript_status: 'not_requested',
                    started_at: data.start_datetime,
                    ended_at: data.end_datetime,
                  })
                  .then(refresh)
              }
              type="button"
            >
              <Video className="size-4" /> Register recording
            </button>
          )}
          {section === 'analytics' && analytics.data && (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[
                ['Attendance', `${analytics.data.attendance_rate}%`],
                ['Joined', analytics.data.joined_count],
                [
                  'Average attended',
                  `${analytics.data.average_minutes_attended} min`,
                ],
                ['Decisions', analytics.data.decisions],
                ['Action items', analytics.data.action_items],
                ['Completed actions', analytics.data.completed_actions],
                ['Agenda items', analytics.data.agenda_items],
                ['Pending follow-ups', analytics.data.follow_ups_pending],
              ].map(([label, metric]) => (
                <article className="rounded-xl border p-4" key={label}>
                  <BarChart3 className="size-4 text-primary" />
                  <p className="mt-3 text-2xl font-semibold">{metric}</p>
                  <p className="text-xs text-muted-foreground">{label}</p>
                </article>
              ))}
            </div>
          )}
          {!['attendees', 'history', 'analytics', 'recordings'].includes(
            section,
          ) && (
            <div className="mb-6 flex gap-2">
              <input
                aria-label={`Add ${section}`}
                className="h-11 flex-1 rounded-xl border bg-background px-3"
                placeholder={`Add ${section.replace('_', ' ')}…`}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void add()
                }}
              />
              <button
                className="rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground"
                onClick={() => void add()}
              >
                Add
              </button>
            </div>
          )}
          <div
            className={`space-y-3 ${section === 'analytics' ? 'hidden' : ''}`}
          >
            {items.length === 0 && (
              <div className="py-14 text-center">
                <ListChecks className="mx-auto size-8 text-primary" />
                <p className="mt-3 font-medium">Nothing here yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Capture structured collaboration as the meeting evolves.
                </p>
              </div>
            )}
            {items.map((item, index) => (
              <article
                className="rounded-xl border p-4"
                key={String(item.id ?? index)}
              >
                <div className="flex gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
                    {section === 'notes' ? (
                      <FileText className="size-4" />
                    ) : (
                      <span className="text-xs font-semibold">{index + 1}</span>
                    )}
                  </span>
                  <div>
                    <p className="font-medium">
                      {String(
                        item.title ??
                          item.display_name ??
                          item.content ??
                          item.name ??
                          item.event_type ??
                          'Meeting update',
                      )}
                    </p>
                    {item.description ? (
                      <p className="mt-1 text-sm text-muted-foreground">
                        {String(item.description)}
                      </p>
                    ) : null}
                    {section === 'attendees' && item.email ? (
                      <p className="mt-1 text-sm text-muted-foreground">
                        {String(item.email)}
                      </p>
                    ) : null}
                    {section === 'attendees' && item.user_id && isOrganizer ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {['joined', 'left', 'no_show'].map((eventType) => (
                          <button
                            className="rounded-lg border px-2.5 py-1 text-xs capitalize hover:border-primary"
                            key={eventType}
                            onClick={() =>
                              void meetingApi
                                .attendance(meetingId, {
                                  user_id: item.user_id,
                                  event_type: eventType,
                                })
                                .then(refresh)
                            }
                            type="button"
                          >
                            {eventType.replace('_', ' ')}
                          </button>
                        ))}
                        <button
                          className="rounded-lg border px-2.5 py-1 text-xs hover:border-primary"
                          onClick={() =>
                            void meetingApi
                              .presenterControl(meetingId, {
                                user_id: item.user_id,
                                control: 'present',
                                enabled: true,
                              })
                              .then(refresh)
                          }
                          type="button"
                        >
                          Make presenter
                        </button>
                      </div>
                    ) : null}
                    <p className="mt-2 text-xs capitalize text-muted-foreground">
                      {String(
                        item.status ??
                          item.attendance_status ??
                          item.occurred_at ??
                          '',
                      )}
                    </p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
