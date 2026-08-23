import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  CalendarPlus,
  CheckSquare2,
  Clock3,
  Inbox,
  Plus,
  Sparkles,
} from 'lucide-react'

import { meetingApi } from '@/features/meetings/api'
import { MeetingCard } from '@/features/meetings/meeting-card'

type View = 'dashboard' | 'upcoming' | 'past' | 'actions'

export function MeetingsPage({ view = 'dashboard' }: { view?: View }) {
  const dashboard = useQuery({
    queryKey: ['meeting-dashboard'],
    queryFn: meetingApi.dashboard,
  })
  const data = dashboard.data
  const meetings =
    view === 'upcoming'
      ? [...(data?.today ?? []), ...(data?.upcoming ?? [])]
      : view === 'past'
        ? (data?.recent ?? [])
        : []
  return (
    <div className="mx-auto max-w-7xl space-y-8 p-5 sm:p-8">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-primary">Meetings</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            {view === 'dashboard'
              ? 'Your collaboration hub'
              : view === 'actions'
                ? 'My action items'
                : `${view.charAt(0).toUpperCase()}${view.slice(1)} meetings`}
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Plan thoughtful conversations, capture outcomes, and keep work
            moving.
          </p>
        </div>
        <Link
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/20"
          to="/meetings/new"
        >
          <Plus className="size-4" /> Schedule meeting
        </Link>
      </header>

      {dashboard.isLoading && (
        <p className="text-muted-foreground">Preparing your meetings…</p>
      )}
      {dashboard.isError && (
        <div
          role="alert"
          className="rounded-2xl bg-red-500/10 p-5 text-red-600"
        >
          Meetings could not be loaded.
        </div>
      )}

      {view === 'dashboard' && data && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ['Today', data.today.length, CalendarPlus],
              ['Upcoming', data.upcoming.length, Clock3],
              ['Pending RSVPs', data.pending_rsvps, Inbox],
              ['My actions', data.my_action_items.length, CheckSquare2],
            ].map(([label, value, Icon]) => {
              const MetricIcon = Icon as typeof CalendarPlus
              return (
                <article
                  className="rounded-2xl border bg-card p-5 shadow-sm"
                  key={String(label)}
                >
                  <MetricIcon className="size-5 text-primary" />
                  <p className="mt-6 text-3xl font-semibold">{String(value)}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {String(label)}
                  </p>
                </article>
              )
            })}
          </section>
          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Coming up</h2>
              <Link
                className="text-sm font-medium text-primary"
                to="/meetings/upcoming"
              >
                View all
              </Link>
            </div>
            <MeetingGrid meetings={[...data.today, ...data.upcoming]} />
          </section>
        </>
      )}
      {(view === 'upcoming' || view === 'past') && (
        <MeetingGrid meetings={meetings} />
      )}
      {view === 'actions' &&
        data &&
        (data.my_action_items.length ? (
          <div className="overflow-hidden rounded-2xl border bg-card">
            {data.my_action_items.map((item) => (
              <div
                className="flex items-center justify-between border-b p-5 last:border-0"
                key={String(item.id)}
              >
                <div>
                  <p className="font-medium">{String(item.title)}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Due{' '}
                    {item.due_date
                      ? new Date(String(item.due_date)).toLocaleDateString()
                      : 'anytime'}
                  </p>
                </div>
                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium capitalize text-primary">
                  {String(item.priority)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Nothing outstanding"
            description="Action items assigned to you will appear here."
          />
        ))}
    </div>
  )
}

function MeetingGrid({ meetings }: { meetings: import('./api').Meeting[] }) {
  if (!meetings.length)
    return (
      <EmptyState
        title="Your calendar is clear"
        description="Schedule a meeting to begin planning the conversation and outcomes."
      />
    )
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {meetings.map((meeting, index) => (
        <MeetingCard index={index} key={meeting.id} meeting={meeting} />
      ))}
    </div>
  )
}

function EmptyState({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="rounded-3xl border border-dashed bg-gradient-to-br from-card to-primary/5 px-6 py-16 text-center">
      <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary/10 text-primary">
        <Sparkles className="size-6" />
      </div>
      <h2 className="mt-5 text-lg font-semibold">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
        {description}
      </p>
      <Link
        className="mt-6 inline-flex rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground"
        to="/meetings/new"
      >
        Schedule meeting
      </Link>
    </div>
  )
}
