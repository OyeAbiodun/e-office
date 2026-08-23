import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  DoorOpen,
  Import,
  Plus,
  Search,
  Settings2,
  SunMedium,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import {
  calendarApi,
  type CalendarEvent,
  type EventCategory,
  type Resource,
} from './api'
import { organizationApi } from '@/features/organizations/api'

type CalendarView =
  | 'day'
  | 'week'
  | 'month'
  | 'agenda'
  | 'settings'
  | 'availability'
  | 'resources'
  | 'holidays'
  | 'detail'

const viewLinks = [
  ['Day', '/calendar/day'],
  ['Week', '/calendar/week'],
  ['Month', '/calendar/month'],
  ['Agenda', '/calendar/agenda'],
] as const

const managementLinks = [
  { label: 'Availability', to: '/calendar/availability', icon: Clock3 },
  { label: 'Resources', to: '/calendar/resources', icon: DoorOpen },
  { label: 'Holidays', to: '/calendar/holidays', icon: SunMedium },
  { label: 'Settings', to: '/calendar/settings', icon: Settings2 },
] as const

const startOfWeek = (date: Date) => {
  const value = new Date(date)
  const day = value.getDay() || 7
  value.setDate(value.getDate() - day + 1)
  value.setHours(0, 0, 0, 0)
  return value
}
const addDays = (date: Date, amount: number) => {
  const value = new Date(date)
  value.setDate(value.getDate() + amount)
  return value
}
const localInput = (date: Date) => {
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16)
}

function EmptyCalendar({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="grid min-h-[420px] place-items-center p-8 text-center">
      <div>
        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary/10 text-primary">
          <CalendarDays className="size-7" />
        </span>
        <h3 className="mt-4 text-lg font-semibold">Your schedule is clear</h3>
        <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
          Create an event to block focus time, reserve a room, or bring a team
          together.
        </p>
        <button
          className="mt-5 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
          onClick={onCreate}
          type="button"
        >
          Create event
        </button>
      </div>
    </div>
  )
}

function EventDialog({
  calendars,
  categories,
  resources,
  initialDate,
  event,
  onClose,
}: {
  calendars: Array<{ id: string; name: string; timezone: string }>
  categories: EventCategory[]
  resources: Resource[]
  initialDate: Date
  event?: CalendarEvent
  onClose: () => void
}) {
  const client = useQueryClient()
  const [calendarId, setCalendarId] = useState(
    event?.calendar_id ?? calendars[0]?.id ?? '',
  )
  const [title, setTitle] = useState(event?.title ?? '')
  const [description, setDescription] = useState(event?.description ?? '')
  const [start, setStart] = useState(
    localInput(event ? new Date(event.start_datetime) : initialDate),
  )
  const [end, setEnd] = useState(
    localInput(
      event
        ? new Date(event.end_datetime)
        : new Date(initialDate.getTime() + 60 * 60_000),
    ),
  )
  const [error, setError] = useState('')
  const [categoryId, setCategoryId] = useState(event?.category_id ?? '')
  const [resourceId, setResourceId] = useState('')
  const [frequency, setFrequency] = useState(
    event?.recurrence_rule_id ? 'weekly' : 'none',
  )
  const [recurrenceEnd, setRecurrenceEnd] = useState('')
  const create = useMutation({
    mutationFn: () =>
      event
        ? calendarApi.updateEvent(event.id, {
            title,
            description: description || null,
            start_datetime: new Date(start).toISOString(),
            end_datetime: new Date(end).toISOString(),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            category_id: categoryId || null,
          })
        : calendarApi.createEvent(calendarId, {
            title,
            description: description || null,
            start_datetime: new Date(start).toISOString(),
            end_datetime: new Date(end).toISOString(),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            status: 'confirmed',
            visibility: 'members',
            all_day: false,
            category_id: categoryId || null,
            recurrence:
              frequency === 'none'
                ? null
                : {
                    frequency,
                    interval: 1,
                    end_date: recurrenceEnd || null,
                    days_of_week:
                      frequency === 'weekly'
                        ? [
                            new Date(start).getDay() === 0
                              ? 6
                              : new Date(start).getDay() - 1,
                          ]
                        : [],
                  },
          }),
    onSuccess: async (saved) => {
      if (event && frequency !== 'none') {
        await calendarApi.setRecurrence(event.id, {
          frequency,
          interval: 1,
          end_date: recurrenceEnd || null,
          days_of_week:
            frequency === 'weekly'
              ? [
                  new Date(start).getDay() === 0
                    ? 6
                    : new Date(start).getDay() - 1,
                ]
              : [],
        })
      }
      if (!event && resourceId) {
        await calendarApi.reserve({
          resource_id: resourceId,
          calendar_event_id: saved.id,
          start_datetime: new Date(start).toISOString(),
          end_datetime: new Date(end).toISOString(),
        })
      }
      await client.invalidateQueries({ queryKey: ['calendar-events'] })
      await client.invalidateQueries({ queryKey: ['calendar-resources'] })
      onClose()
    },
    onError: (reason) =>
      setError(
        reason instanceof Error ? reason.message : 'Event could not be created',
      ),
  })
  const submit = () => {
    setError('')
    if (!calendarId || !title.trim())
      return setError('Choose a calendar and enter a title.')
    if (new Date(end) <= new Date(start))
      return setError('End time must be after start time.')
    create.mutate()
  }
  return (
    <div
      aria-label="Create event"
      aria-modal="true"
      className="fixed inset-0 z-[90] grid place-items-center overflow-y-auto bg-black/55 p-4 backdrop-blur-sm"
      role="dialog"
    >
      <section className="flex max-h-[calc(100dvh-2rem)] w-full max-w-xl flex-col rounded-2xl border bg-card shadow-2xl">
        <header className="flex items-center border-b px-5 py-4">
          <div>
            <h2 className="font-semibold">
              {event ? 'Edit event' : 'Create event'}
            </h2>
            <p className="text-xs text-muted-foreground">
              {event
                ? 'Update this shared calendar event.'
                : 'Add it to a shared calendar.'}
            </p>
          </div>
          <button
            aria-label={`Close ${event ? 'edit' : 'create'} event`}
            className="ml-auto rounded-lg p-2 hover:bg-muted"
            onClick={onClose}
            type="button"
          >
            <X className="size-4" />
          </button>
        </header>
        <div className="space-y-4 overflow-y-auto p-5">
          <label className="block text-sm font-medium">
            Title
            <input
              autoFocus
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3 outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setTitle(event.target.value)}
              value={title}
            />
          </label>
          <label className="block text-sm font-medium">
            Calendar
            <select
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              onChange={(event) => setCalendarId(event.target.value)}
              value={calendarId}
            >
              {calendars.map((calendar) => (
                <option key={calendar.id} value={calendar.id}>
                  {calendar.name}
                </option>
              ))}
            </select>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Starts
              <input
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                onChange={(event) => setStart(event.target.value)}
                type="datetime-local"
                value={start}
              />
            </label>
            <label className="block text-sm font-medium">
              Ends
              <input
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                onChange={(event) => setEnd(event.target.value)}
                type="datetime-local"
                value={end}
              />
            </label>
          </div>
          <label className="block text-sm font-medium">
            Description
            <textarea
              className="mt-2 min-h-24 w-full resize-y rounded-xl border bg-background p-3"
              onChange={(event) => setDescription(event.target.value)}
              value={description}
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Color category
              <select
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                onChange={(item) => setCategoryId(item.target.value)}
                value={categoryId}
              >
                <option value="">Calendar default</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium">
              Room or equipment
              <select
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                disabled={Boolean(event)}
                onChange={(item) => setResourceId(item.target.value)}
                value={resourceId}
              >
                <option value="">No resource</option>
                {resources
                  .filter((resource) => resource.status === 'available')
                  .map((resource) => (
                    <option key={resource.id} value={resource.id}>
                      {resource.name} · {resource.category}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <div className="grid gap-4 rounded-xl border bg-muted/20 p-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Repeat
              <select
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                onChange={(item) => setFrequency(item.target.value)}
                value={frequency}
              >
                <option value="none">Does not repeat</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
              </select>
            </label>
            <label className="block text-sm font-medium">
              Recurrence ends
              <input
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
                disabled={frequency === 'none'}
                onChange={(item) => setRecurrenceEnd(item.target.value)}
                type="date"
                value={recurrenceEnd}
              />
            </label>
          </div>
          {error && (
            <p className="text-sm text-red-500" role="alert">
              {error}
            </p>
          )}
        </div>
        <footer className="flex justify-end gap-2 border-t p-4">
          {event && (
            <button
              className="mr-auto rounded-xl px-4 py-2 text-sm text-red-500 hover:bg-red-500/10"
              onClick={() => {
                void calendarApi.deleteEvent(event.id).then(async () => {
                  await client.invalidateQueries({
                    queryKey: ['calendar-events'],
                  })
                  onClose()
                })
              }}
              type="button"
            >
              Delete
            </button>
          )}
          <button
            className="rounded-xl px-4 py-2 text-sm hover:bg-muted"
            onClick={onClose}
            type="button"
          >
            Cancel
          </button>
          <button
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={create.isPending}
            onClick={submit}
            type="button"
          >
            {create.isPending
              ? 'Saving…'
              : event
                ? 'Save changes'
                : 'Create event'}
          </button>
        </footer>
      </section>
    </div>
  )
}

function CalendarSurface({
  view,
  date,
  events,
  onCreate,
  onEdit,
  onMove,
  timezone,
}: {
  view: CalendarView
  date: Date
  events: CalendarEvent[]
  onCreate: (date?: Date) => void
  onEdit: (event: CalendarEvent) => void
  onMove: (event: CalendarEvent, start: Date, end: Date) => void
  timezone: string
}) {
  const formatter = new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: timezone,
  })
  if (!events.length) return <EmptyCalendar onCreate={() => onCreate(date)} />
  if (view === 'agenda') {
    return (
      <div className="divide-y">
        {events.map((event) => (
          <button
            className="flex w-full gap-4 p-4 text-left hover:bg-muted/45"
            key={event.id}
            onClick={() => onEdit(event)}
            type="button"
          >
            <div className="w-20 text-sm font-semibold">
              {formatter.format(new Date(event.start_datetime))}
            </div>
            <div>
              <p className="font-semibold">{event.title}</p>
              <p className="text-sm text-muted-foreground">
                {new Date(event.start_datetime).toLocaleDateString()} ·{' '}
                {event.status}
              </p>
            </div>
          </button>
        ))}
      </div>
    )
  }
  if (view === 'month') {
    const first = new Date(date.getFullYear(), date.getMonth(), 1)
    const gridStart = addDays(first, -(first.getDay() || 7) + 1)
    return (
      <div className="grid min-h-[560px] grid-cols-7">
        {Array.from({ length: 42 }, (_, index) =>
          addDays(gridStart, index),
        ).map((day) => {
          const dayEvents = events.filter(
            (event) =>
              new Date(event.start_datetime).toDateString() ===
              day.toDateString(),
          )
          return (
            <button
              className="min-h-24 border-b border-r p-2 text-left align-top hover:bg-muted/40"
              key={day.toISOString()}
              onDoubleClick={() => onCreate(new Date(day.setHours(9)))}
              type="button"
            >
              <span
                className={
                  day.getMonth() === date.getMonth()
                    ? 'text-sm'
                    : 'text-sm text-muted-foreground'
                }
              >
                {day.getDate()}
              </span>
              {dayEvents.slice(0, 3).map((event) => (
                <span
                  className="mt-1 block truncate rounded-md bg-primary/12 px-1.5 py-1 text-xs text-primary"
                  key={event.id}
                  onClick={(click) => {
                    click.stopPropagation()
                    onEdit(event)
                  }}
                >
                  {event.title}
                </span>
              ))}
            </button>
          )
        })}
      </div>
    )
  }
  const days =
    view === 'day'
      ? [date]
      : Array.from({ length: 5 }, (_, index) =>
          addDays(startOfWeek(date), index),
        )
  const hours = Array.from({ length: 11 }, (_, index) => index + 7)
  return (
    <div className="overflow-auto">
      <div className="min-w-[720px]">
        <div
          className={`grid border-b bg-muted/20`}
          style={{
            gridTemplateColumns: `72px repeat(${days.length}, minmax(120px, 1fr))`,
          }}
        >
          <div />
          {days.map((day) => (
            <div
              className="border-l px-3 py-3 text-center"
              key={day.toISOString()}
            >
              <p className="text-xs uppercase text-muted-foreground">
                {day.toLocaleDateString(undefined, { weekday: 'short' })}
              </p>
              <p className="mt-1 font-semibold">{day.getDate()}</p>
            </div>
          ))}
        </div>
        {hours.map((hour) => (
          <div
            className="grid h-16 border-b"
            key={hour}
            style={{
              gridTemplateColumns: `72px repeat(${days.length}, minmax(120px, 1fr))`,
            }}
          >
            <div className="-translate-y-2 px-3 text-right text-xs text-muted-foreground">
              {hour}:00
            </div>
            {days.map((day) => {
              const cellEvents = events.filter((event) => {
                const start = new Date(event.start_datetime)
                return (
                  start.toDateString() === day.toDateString() &&
                  start.getHours() === hour
                )
              })
              return (
                <div
                  aria-label={`Create event ${day.toDateString()} at ${hour}:00`}
                  className="relative border-l text-left hover:bg-primary/5"
                  key={day.toISOString()}
                  onDragOver={(drag) => drag.preventDefault()}
                  onDrop={(drop) => {
                    drop.preventDefault()
                    const eventId = drop.dataTransfer.getData(
                      'application/x-meetinghq-event',
                    )
                    const moved = events.find((item) => item.id === eventId)
                    if (!moved) return
                    const previousStart = new Date(moved.start_datetime)
                    const duration =
                      new Date(moved.end_datetime).getTime() -
                      previousStart.getTime()
                    const nextStart = new Date(
                      day.getFullYear(),
                      day.getMonth(),
                      day.getDate(),
                      hour,
                      previousStart.getMinutes(),
                    )
                    onMove(
                      moved,
                      nextStart,
                      new Date(nextStart.getTime() + duration),
                    )
                  }}
                  onDoubleClick={() =>
                    onCreate(
                      new Date(
                        day.getFullYear(),
                        day.getMonth(),
                        day.getDate(),
                        hour,
                      ),
                    )
                  }
                  onKeyDown={(keyboard) => {
                    if (keyboard.key === 'Enter')
                      onCreate(
                        new Date(
                          day.getFullYear(),
                          day.getMonth(),
                          day.getDate(),
                          hour,
                        ),
                      )
                  }}
                  role="gridcell"
                  tabIndex={0}
                >
                  {cellEvents.map((event) => (
                    <div
                      className="absolute inset-x-1 top-1 z-10 flex rounded-lg border border-primary/25 bg-primary/15 text-xs text-primary shadow-sm"
                      draggable
                      key={event.id}
                      onDragStart={(drag) => {
                        drag.dataTransfer.setData(
                          'application/x-meetinghq-event',
                          event.id,
                        )
                        drag.dataTransfer.effectAllowed = 'move'
                      }}
                      onContextMenu={(context) => {
                        context.preventDefault()
                        onEdit(event)
                      }}
                    >
                      <button
                        className="min-w-0 flex-1 px-2 py-1.5 text-left"
                        onClick={() => onEdit(event)}
                        type="button"
                      >
                        <strong className="block truncate">
                          {event.title}
                        </strong>
                        {formatter.format(new Date(event.start_datetime))}
                      </button>
                      <button
                        aria-label={`Extend ${event.title} by 15 minutes`}
                        className="border-l border-primary/20 px-1.5 hover:bg-primary/10"
                        onClick={() =>
                          onMove(
                            event,
                            new Date(event.start_datetime),
                            new Date(
                              new Date(event.end_datetime).getTime() +
                                15 * 60000,
                            ),
                          )
                        }
                        title="Extend by 15 minutes"
                        type="button"
                      >
                        ↕
                      </button>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

export function CalendarPage({ view = 'week' }: { view?: CalendarView }) {
  const client = useQueryClient()
  const [date, setDate] = useState(new Date())
  const [search, setSearch] = useState('')
  const [selectedCalendarIds, setSelectedCalendarIds] = useState<Set<string>>(
    new Set(),
  )
  const [resourceForm, setResourceForm] = useState({
    name: '',
    category: 'room',
    capacity: 1,
    location: '',
  })
  const [calendarAction, setCalendarAction] = useState('')
  const [availabilityForm, setAvailabilityForm] = useState({
    weekday: 0,
    start_time: '09:00',
    end_time: '17:00',
  })
  const [shareForm, setShareForm] = useState({
    user_id: '',
    permission: 'read',
  })
  const [categoryForm, setCategoryForm] = useState({
    name: '',
    color: '#2563eb',
  })
  const [suggestedSlots, setSuggestedSlots] = useState<
    Array<{ start_datetime: string; end_datetime: string }>
  >([])
  const importRef = useRef<HTMLInputElement>(null)
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone,
  )
  const [dialog, setDialog] = useState<{
    date: Date
    event?: CalendarEvent
  } | null>(null)
  const calendars = useQuery({
    queryKey: ['calendars'],
    queryFn: calendarApi.calendars,
  })
  const resources = useQuery({
    queryKey: ['calendar-resources'],
    queryFn: calendarApi.resources,
  })
  const categories = useQuery({
    queryKey: ['calendar-categories'],
    queryFn: calendarApi.categories,
  })
  const workspaces = useQuery({
    queryKey: ['workspaces'],
    queryFn: organizationApi.workspaces,
  })
  const members = useQuery({
    queryKey: ['organization-members'],
    queryFn: organizationApi.members,
  })
  const primaryCalendarId = calendars.data?.[0]?.id
  const availability = useQuery({
    queryKey: ['calendar-availability', primaryCalendarId],
    queryFn: () => calendarApi.availability(primaryCalendarId!),
    enabled: Boolean(primaryCalendarId),
  })
  const shares = useQuery({
    queryKey: ['calendar-shares', primaryCalendarId],
    queryFn: () => calendarApi.shares(primaryCalendarId!),
    enabled: Boolean(primaryCalendarId),
  })
  const holidays = useQuery({
    queryKey: ['calendar-holidays'],
    queryFn: calendarApi.holidays,
  })
  const eventQueries = useQueries({
    queries: (calendars.data ?? []).map((calendar) => ({
      queryKey: ['calendar-events', calendar.id],
      queryFn: () => calendarApi.events(calendar.id),
    })),
  })
  useEffect(() => {
    if (calendars.data?.length)
      setSelectedCalendarIds((current) =>
        current.size
          ? current
          : new Set(calendars.data.map((calendar) => calendar.id)),
      )
  }, [calendars.data])
  const allEvents = useMemo(
    () =>
      eventQueries
        .flatMap((query) => query.data ?? [])
        .filter((event) => selectedCalendarIds.has(event.calendar_id))
        .filter((event) =>
          event.title.toLowerCase().includes(search.toLowerCase()),
        )
        .sort((a, b) => a.start_datetime.localeCompare(b.start_datetime)),
    [eventQueries, search, selectedCalendarIds],
  )
  const loading =
    calendars.isLoading || eventQueries.some((query) => query.isLoading)
  const error = calendars.isError || eventQueries.some((query) => query.isError)
  const management = [
    'settings',
    'availability',
    'resources',
    'holidays',
    'detail',
  ].includes(view)
  const periodLabel =
    view === 'month'
      ? date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
      : view === 'day'
        ? date.toLocaleDateString(undefined, {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
          })
        : `${startOfWeek(date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}–${addDays(startOfWeek(date), 4).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`
  const move = (direction: number) =>
    setDate((current) =>
      addDays(
        current,
        direction * (view === 'month' ? 28 : view === 'day' ? 1 : 7),
      ),
    )
  const moveEvent = async (event: CalendarEvent, start: Date, end: Date) => {
    setCalendarAction(`Moving ${event.title}…`)
    try {
      await calendarApi.updateEvent(event.id, {
        start_datetime: start.toISOString(),
        end_datetime: end.toISOString(),
        timezone,
      })
      await client.invalidateQueries({ queryKey: ['calendar-events'] })
      setCalendarAction(`${event.title} updated`)
    } catch (reason) {
      setCalendarAction(
        reason instanceof Error ? reason.message : 'Event could not be moved',
      )
    }
  }
  const importIcs = async (file: File) => {
    const calendarId = calendars.data?.[0]?.id
    if (!calendarId) return
    setCalendarAction('Importing calendar…')
    try {
      const events = await calendarApi.importIcs(calendarId, file)
      await client.invalidateQueries({ queryKey: ['calendar-events'] })
      setCalendarAction(
        `${events.length} event${events.length === 1 ? '' : 's'} imported`,
      )
    } catch (reason) {
      setCalendarAction(
        reason instanceof Error ? reason.message : 'Calendar import failed',
      )
    } finally {
      if (importRef.current) importRef.current.value = ''
    }
  }
  const exportIcs = async () => {
    const calendar = calendars.data?.[0]
    if (!calendar) return
    const blob = await calendarApi.exportIcs(calendar.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${calendar.name.toLowerCase().replaceAll(' ', '-')}.ics`
    link.click()
    URL.revokeObjectURL(url)
    setCalendarAction(`${calendar.name} exported`)
  }
  const createResource = async () => {
    const workspaceId = workspaces.data?.[0]?.id
    if (!workspaceId || !resourceForm.name.trim()) return
    await calendarApi.createResource({
      workspace_id: workspaceId,
      name: resourceForm.name.trim(),
      category: resourceForm.category,
      capacity: resourceForm.capacity,
      location: resourceForm.location || null,
      timezone,
    })
    setResourceForm({ name: '', category: 'room', capacity: 1, location: '' })
    await Promise.all([
      client.invalidateQueries({ queryKey: ['calendar-resources'] }),
      client.invalidateQueries({ queryKey: ['calendars'] }),
    ])
    setCalendarAction('Resource created')
  }
  const createAvailability = async () => {
    if (!primaryCalendarId) return
    await calendarApi.createAvailability(primaryCalendarId, {
      ...availabilityForm,
      availability_type: 'available',
      priority: 0,
    })
    await client.invalidateQueries({ queryKey: ['calendar-availability'] })
    setCalendarAction('Availability updated')
  }
  const compareAvailability = async () => {
    if (!calendars.data?.length) return
    const start = new Date()
    start.setMinutes(0, 0, 0)
    const end = addDays(start, 14)
    const slots = await calendarApi.suggestions({
      calendar_ids: calendars.data
        .filter((calendar) => selectedCalendarIds.has(calendar.id))
        .map((calendar) => calendar.id),
      resource_ids: [],
      start_datetime: start.toISOString(),
      end_datetime: new Date(start.getTime() + 30 * 60000).toISOString(),
      search_end: end.toISOString(),
      timezone,
      duration_minutes: 30,
      limit: 5,
    })
    setSuggestedSlots(slots)
    setCalendarAction(`${slots.length} shared slots found`)
  }
  const shareCalendar = async () => {
    if (!primaryCalendarId || !shareForm.user_id) return
    await calendarApi.share(primaryCalendarId, shareForm)
    await client.invalidateQueries({ queryKey: ['calendar-shares'] })
    setCalendarAction('Calendar sharing updated')
  }
  const createCategory = async () => {
    if (!categoryForm.name.trim()) return
    await calendarApi.createCategory({
      name: categoryForm.name.trim(),
      color: categoryForm.color,
    })
    setCategoryForm({ name: '', color: '#2563eb' })
    await client.invalidateQueries({ queryKey: ['calendar-categories'] })
    setCalendarAction('Event category created')
  }

  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        event.target instanceof HTMLSelectElement
      )
        return
      if (event.key.toLowerCase() === 'n') {
        event.preventDefault()
        setDialog({ date: new Date() })
      }
      if (event.key.toLowerCase() === 't') setDate(new Date())
      if (event.key === 'ArrowLeft') move(-1)
      if (event.key === 'ArrowRight') move(1)
      if (event.key === '/') {
        event.preventDefault()
        document
          .querySelector<HTMLInputElement>(
            '[aria-label="Search calendar events"]',
          )
          ?.focus()
      }
    }
    window.addEventListener('keydown', keyboard)
    return () => window.removeEventListener('keydown', keyboard)
  })

  return (
    <div className="mx-auto max-w-[1500px] space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-primary">
            Scheduling workspace
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Calendar
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Your real events, availability, and shared resources.
          </p>
        </div>
        <button
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
          onClick={() => setDialog({ date: new Date() })}
          type="button"
        >
          <Plus className="size-4" /> New event
        </button>
      </header>
      <div className="grid gap-4 xl:grid-cols-[240px_1fr]">
        <aside className="rounded-2xl border bg-card p-3 shadow-sm">
          <p className="px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            My calendars
          </p>
          {calendars.data?.map((calendar) => (
            <label
              className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-muted"
              key={calendar.id}
            >
              <input
                checked={selectedCalendarIds.has(calendar.id)}
                className="sr-only"
                onChange={(toggle) => {
                  const next = new Set(selectedCalendarIds)
                  if (toggle.target.checked) next.add(calendar.id)
                  else next.delete(calendar.id)
                  setSelectedCalendarIds(next)
                }}
                type="checkbox"
              />
              <span
                className={`size-3 rounded-full ring-2 ring-offset-2 ring-offset-card ${
                  selectedCalendarIds.has(calendar.id)
                    ? 'ring-primary/35'
                    : 'opacity-30 ring-transparent'
                }`}
                style={{ background: calendar.color }}
              />
              <span className="truncate">{calendar.name}</span>
            </label>
          ))}
          {!calendars.isLoading && !calendars.data?.length && (
            <p className="rounded-xl bg-muted/50 p-3 text-sm text-muted-foreground">
              No calendars are available.
            </p>
          )}
          <div className="my-3 border-t" />
          <div className="grid grid-cols-2 gap-2 px-1 pb-3">
            <button
              className="flex items-center justify-center gap-1 rounded-lg border px-2 py-2 text-xs hover:bg-muted"
              onClick={() => importRef.current?.click()}
              type="button"
            >
              <Import className="size-3.5" /> Import
            </button>
            <button
              className="flex items-center justify-center gap-1 rounded-lg border px-2 py-2 text-xs hover:bg-muted"
              onClick={() => void exportIcs()}
              type="button"
            >
              <Download className="size-3.5" /> Export
            </button>
            <input
              accept=".ics,text/calendar"
              className="hidden"
              onChange={(item) => {
                const file = item.target.files?.[0]
                if (file) void importIcs(file)
              }}
              ref={importRef}
              type="file"
            />
          </div>
          {managementLinks.map(({ label, to, icon: Icon }) => (
            <Link
              className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              key={label}
              to={to}
            >
              <Icon className="size-4" /> {label}
            </Link>
          ))}
        </aside>
        <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
          <div className="flex flex-wrap items-center gap-3 border-b p-3">
            <button
              className="rounded-lg border px-3 py-2 text-sm"
              onClick={() => setDate(new Date())}
              type="button"
            >
              Today
            </button>
            <button
              aria-label="Previous period"
              className="rounded-lg p-2 hover:bg-muted"
              onClick={() => move(-1)}
              type="button"
            >
              <ChevronLeft className="size-4" />
            </button>
            <button
              aria-label="Next period"
              className="rounded-lg p-2 hover:bg-muted"
              onClick={() => move(1)}
              type="button"
            >
              <ChevronRight className="size-4" />
            </button>
            <h2 className="font-semibold">{periodLabel}</h2>
            <span
              aria-live="polite"
              className="max-w-48 truncate text-xs text-muted-foreground"
            >
              {calendarAction}
            </span>
            <div className="relative ml-auto hidden md:block">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <input
                aria-label="Search calendar events"
                className="h-9 rounded-lg border bg-background pl-9 pr-3 text-sm"
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search events"
                value={search}
              />
            </div>
            <select
              aria-label="Calendar timezone"
              className="h-9 rounded-lg border bg-background px-2 text-sm"
              onChange={(event) => setTimezone(event.target.value)}
              value={timezone}
            >
              {[
                Intl.DateTimeFormat().resolvedOptions().timeZone,
                'UTC',
                'America/Chicago',
                'America/New_York',
                'Europe/London',
              ]
                .filter((item, index, values) => values.indexOf(item) === index)
                .map((zone) => (
                  <option key={zone}>{zone}</option>
                ))}
            </select>
            <div className="flex rounded-xl bg-muted p-1">
              {viewLinks.map(([label, to]) => (
                <Link
                  activeProps={{
                    className: 'bg-background shadow-sm text-foreground',
                  }}
                  className="rounded-lg px-3 py-1.5 text-sm text-muted-foreground"
                  key={label}
                  to={to}
                >
                  {label}
                </Link>
              ))}
            </div>
          </div>
          {loading && (
            <div className="space-y-3 p-6" aria-label="Loading calendar">
              {[1, 2, 3, 4].map((item) => (
                <div
                  className="h-16 animate-pulse rounded-xl bg-muted"
                  key={item}
                />
              ))}
            </div>
          )}
          {error && (
            <div className="p-10 text-center" role="alert">
              <p className="font-semibold">Calendar could not be loaded</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Check your connection and try again.
              </p>
            </div>
          )}
          {!loading && !error && management && (
            <div className="p-6">
              <h2 className="text-lg font-semibold">
                {managementLinks.find((item) => item.to.endsWith(view))
                  ?.label ?? 'Calendar settings'}
              </h2>
              <div className="mt-4 space-y-3">
                {view === 'resources' && (
                  <div className="grid gap-3 rounded-xl border bg-muted/20 p-4 md:grid-cols-2 xl:grid-cols-5">
                    <input
                      aria-label="Resource name"
                      className="h-10 rounded-lg border bg-background px-3 text-sm xl:col-span-2"
                      onChange={(item) =>
                        setResourceForm({
                          ...resourceForm,
                          name: item.target.value,
                        })
                      }
                      placeholder="Room or equipment name"
                      value={resourceForm.name}
                    />
                    <select
                      aria-label="Resource type"
                      className="h-10 rounded-lg border bg-background px-3 text-sm"
                      onChange={(item) =>
                        setResourceForm({
                          ...resourceForm,
                          category: item.target.value,
                        })
                      }
                      value={resourceForm.category}
                    >
                      <option value="room">Room</option>
                      <option value="equipment">Equipment</option>
                      <option value="desk">Desk</option>
                      <option value="vehicle">Vehicle</option>
                    </select>
                    <input
                      aria-label="Resource capacity"
                      className="h-10 rounded-lg border bg-background px-3 text-sm"
                      min={1}
                      onChange={(item) =>
                        setResourceForm({
                          ...resourceForm,
                          capacity: Number(item.target.value),
                        })
                      }
                      type="number"
                      value={resourceForm.capacity}
                    />
                    <button
                      className="rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                      disabled={
                        !resourceForm.name.trim() || !workspaces.data?.length
                      }
                      onClick={() => void createResource()}
                      type="button"
                    >
                      Add resource
                    </button>
                    <input
                      aria-label="Resource location"
                      className="h-10 rounded-lg border bg-background px-3 text-sm md:col-span-2 xl:col-span-5"
                      onChange={(item) =>
                        setResourceForm({
                          ...resourceForm,
                          location: item.target.value,
                        })
                      }
                      placeholder="Location (optional)"
                      value={resourceForm.location}
                    />
                  </div>
                )}
                {view === 'resources' &&
                  resources.data?.map((resource) => (
                    <article
                      className="rounded-xl border p-4"
                      key={resource.id}
                    >
                      <p className="font-semibold">{resource.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {resource.category} · capacity {resource.capacity} ·{' '}
                        {resource.status}
                      </p>
                    </article>
                  ))}
                {view === 'availability' && (
                  <>
                    <div className="grid gap-3 rounded-xl border bg-muted/20 p-4 sm:grid-cols-4">
                      <select
                        aria-label="Availability weekday"
                        className="h-10 rounded-lg border bg-background px-3 text-sm"
                        onChange={(item) =>
                          setAvailabilityForm({
                            ...availabilityForm,
                            weekday: Number(item.target.value),
                          })
                        }
                        value={availabilityForm.weekday}
                      >
                        {[
                          'Monday',
                          'Tuesday',
                          'Wednesday',
                          'Thursday',
                          'Friday',
                          'Saturday',
                          'Sunday',
                        ].map((day, index) => (
                          <option key={day} value={index}>
                            {day}
                          </option>
                        ))}
                      </select>
                      <input
                        aria-label="Availability starts"
                        className="h-10 rounded-lg border bg-background px-3 text-sm"
                        onChange={(item) =>
                          setAvailabilityForm({
                            ...availabilityForm,
                            start_time: item.target.value,
                          })
                        }
                        type="time"
                        value={availabilityForm.start_time}
                      />
                      <input
                        aria-label="Availability ends"
                        className="h-10 rounded-lg border bg-background px-3 text-sm"
                        onChange={(item) =>
                          setAvailabilityForm({
                            ...availabilityForm,
                            end_time: item.target.value,
                          })
                        }
                        type="time"
                        value={availabilityForm.end_time}
                      />
                      <button
                        className="rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground"
                        onClick={() => void createAvailability()}
                        type="button"
                      >
                        Add hours
                      </button>
                    </div>
                    {availability.data?.map((rule) => (
                      <article
                        className="flex items-center rounded-xl border p-4"
                        key={rule.id}
                      >
                        <Clock3 className="mr-3 size-5 text-primary" />
                        <p className="font-medium">
                          {
                            [
                              'Monday',
                              'Tuesday',
                              'Wednesday',
                              'Thursday',
                              'Friday',
                              'Saturday',
                              'Sunday',
                            ][rule.weekday]
                          }{' '}
                          · {rule.start_time.slice(0, 5)}–
                          {rule.end_time.slice(0, 5)}
                        </p>
                        <button
                          className="ml-auto rounded-lg px-3 py-1.5 text-sm text-red-600 hover:bg-red-500/10"
                          onClick={async () => {
                            await calendarApi.deleteAvailability(rule.id)
                            await client.invalidateQueries({
                              queryKey: ['calendar-availability'],
                            })
                          }}
                          type="button"
                        >
                          Remove
                        </button>
                      </article>
                    ))}
                    <div className="rounded-xl border p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <h3 className="font-semibold">
                            Compare selected calendars
                          </h3>
                          <p className="text-sm text-muted-foreground">
                            Find the next shared 30-minute windows.
                          </p>
                        </div>
                        <button
                          className="rounded-lg border px-3 py-2 text-sm"
                          onClick={() => void compareAvailability()}
                          type="button"
                        >
                          Find times
                        </button>
                      </div>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {suggestedSlots.map((slot) => (
                          <button
                            className="rounded-lg bg-muted p-3 text-left text-sm hover:bg-primary/10"
                            key={slot.start_datetime}
                            onClick={() =>
                              setDialog({
                                date: new Date(slot.start_datetime),
                              })
                            }
                            type="button"
                          >
                            {new Date(slot.start_datetime).toLocaleString()} ·
                            available
                          </button>
                        ))}
                      </div>
                    </div>
                  </>
                )}
                {view === 'settings' && (
                  <>
                    <div className="rounded-xl border p-4">
                      <h3 className="font-semibold">Event color categories</h3>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <input
                          aria-label="Category name"
                          className="h-10 min-w-56 flex-1 rounded-lg border bg-background px-3 text-sm"
                          onChange={(item) =>
                            setCategoryForm({
                              ...categoryForm,
                              name: item.target.value,
                            })
                          }
                          placeholder="Category name"
                          value={categoryForm.name}
                        />
                        <input
                          aria-label="Category color"
                          className="h-10 w-14 rounded-lg border bg-background p-1"
                          onChange={(item) =>
                            setCategoryForm({
                              ...categoryForm,
                              color: item.target.value,
                            })
                          }
                          type="color"
                          value={categoryForm.color}
                        />
                        <button
                          className="rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground"
                          onClick={() => void createCategory()}
                          type="button"
                        >
                          Add category
                        </button>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {categories.data?.map((category) => (
                          <span
                            className="rounded-full px-3 py-1 text-xs font-medium text-white"
                            key={category.id}
                            style={{ background: category.color }}
                          >
                            {category.name}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-xl border p-4">
                      <h3 className="font-semibold">Calendar sharing</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Grant explicit access to the primary calendar.
                      </p>
                      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_140px_auto]">
                        <select
                          aria-label="Share with member"
                          className="h-10 rounded-lg border bg-background px-3 text-sm"
                          onChange={(item) =>
                            setShareForm({
                              ...shareForm,
                              user_id: item.target.value,
                            })
                          }
                          value={shareForm.user_id}
                        >
                          <option value="">Choose a member</option>
                          {members.data?.map((member) => (
                            <option key={member.id} value={member.id}>
                              {member.display_name} · {member.email}
                            </option>
                          ))}
                        </select>
                        <select
                          aria-label="Calendar permission"
                          className="h-10 rounded-lg border bg-background px-3 text-sm"
                          onChange={(item) =>
                            setShareForm({
                              ...shareForm,
                              permission: item.target.value,
                            })
                          }
                          value={shareForm.permission}
                        >
                          <option value="read">Can view</option>
                          <option value="write">Can edit</option>
                          <option value="manage">Can manage</option>
                        </select>
                        <button
                          className="rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                          disabled={!shareForm.user_id}
                          onClick={() => void shareCalendar()}
                          type="button"
                        >
                          Share
                        </button>
                      </div>
                      {shares.data?.map((share) => {
                        const member = members.data?.find(
                          (item) => item.id === share.user_id,
                        )
                        return (
                          <div
                            className="mt-3 flex items-center rounded-lg bg-muted/45 p-3 text-sm"
                            key={share.id}
                          >
                            <span>
                              {member?.display_name ?? share.user_id} ·{' '}
                              {share.permission}
                            </span>
                            <button
                              className="ml-auto text-red-600"
                              onClick={async () => {
                                if (!primaryCalendarId) return
                                await calendarApi.revokeShare(
                                  primaryCalendarId,
                                  share.id,
                                )
                                await client.invalidateQueries({
                                  queryKey: ['calendar-shares'],
                                })
                              }}
                              type="button"
                            >
                              Revoke
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  </>
                )}
                {view === 'holidays' &&
                  holidays.data?.map((holiday) => (
                    <article className="rounded-xl border p-4" key={holiday.id}>
                      <p className="font-semibold">{holiday.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(
                          `${holiday.date}T12:00:00`,
                        ).toLocaleDateString()}
                      </p>
                    </article>
                  ))}
                {((view === 'resources' && !resources.data?.length) ||
                  (view === 'holidays' && !holidays.data?.length)) && (
                  <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                    No records have been configured.
                  </p>
                )}
                {![
                  'resources',
                  'holidays',
                  'availability',
                  'settings',
                ].includes(view) && (
                  <p className="rounded-xl border border-dashed p-8 text-sm text-muted-foreground">
                    This configuration is managed through the organization
                    scheduling policy. No simulated settings are shown.
                  </p>
                )}
              </div>
            </div>
          )}
          {!loading && !error && !management && (
            <CalendarSurface
              date={date}
              events={allEvents}
              onCreate={(value) => setDialog({ date: value ?? new Date() })}
              onEdit={(event) =>
                setDialog({ date: new Date(event.start_datetime), event })
              }
              onMove={(event, start, end) => void moveEvent(event, start, end)}
              timezone={timezone}
              view={view}
            />
          )}
        </section>
      </div>
      {dialog && calendars.data && (
        <EventDialog
          calendars={calendars.data}
          categories={categories.data ?? []}
          event={dialog.event}
          initialDate={dialog.date}
          onClose={() => setDialog(null)}
          resources={resources.data ?? []}
        />
      )}
    </div>
  )
}
