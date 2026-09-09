import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { CalendarDays, CheckCircle2, Clock3, Search, Users } from 'lucide-react'
import { useMemo, useState } from 'react'

import { leaveApi } from './api'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Pagination,
  PersonMark,
  StatusBadge,
} from './shared'
import { formatDay, formatDays } from './utils'
import { useAuth } from '@/features/auth/auth-store'

function dateValue(offsetDays: number) {
  const value = new Date()
  value.setDate(value.getDate() + offsetDays)
  return value.toISOString().slice(0, 10)
}

export function LeaveManagerPage() {
  const { user } = useAuth()
  const allowed = user?.permissions.includes('leave.view_team') ?? false
  const [section, setSection] = useState<
    'pending' | 'team' | 'calendar' | 'reviewed'
  >('pending')
  const [search, setSearch] = useState('')
  const [leaveType, setLeaveType] = useState('')
  const [startDate, setStartDate] = useState(dateValue(-14))
  const [endDate, setEndDate] = useState(dateValue(60))
  const [page, setPage] = useState(1)
  const types = useQuery({
    queryKey: ['leave', 'types', 'manager'],
    queryFn: () => leaveApi.types({ active: true }),
    enabled: allowed,
  })
  const summary = useQuery({
    queryKey: ['leave', 'team-summary'],
    queryFn: leaveApi.managerSummary,
    enabled: allowed,
    refetchOnMount: 'always',
  })
  const scope =
    section === 'reviewed'
      ? 'recently_reviewed'
      : section === 'pending'
        ? 'pending'
        : 'team'
  const requests = useQuery({
    queryKey: [
      'leave',
      'requests',
      scope,
      search,
      leaveType,
      startDate,
      endDate,
      page,
    ],
    queryFn: () =>
      leaveApi.requests({
        scope,
        search,
        leave_type_id: leaveType,
        start_date: startDate,
        end_date: endDate,
        page,
        page_size: 25,
      }),
    enabled: allowed && section !== 'calendar',
    refetchOnMount: 'always',
  })
  const availability = useQuery({
    queryKey: ['leave', 'availability', startDate, endDate],
    queryFn: () => leaveApi.availability(startDate, endDate),
    enabled: allowed && section === 'calendar' && Boolean(startDate && endDate),
    refetchOnMount: 'always',
  })
  const filteredAvailability = useMemo(
    () =>
      (availability.data ?? []).filter((person) =>
        person.employee_name.toLowerCase().includes(search.toLowerCase()),
      ),
    [availability.data, search],
  )
  if (!allowed)
    return (
      <div className="p-5 sm:p-8">
        <ErrorState retry={() => window.location.assign('/leave')} />
      </div>
    )
  if (summary.isLoading || types.isLoading)
    return (
      <div className="p-5 sm:p-8">
        <LoadingState label="Loading manager leave workspace" />
      </div>
    )
  if (summary.isError || types.isError || !summary.data || !types.data)
    return (
      <div className="p-5 sm:p-8">
        <ErrorState
          retry={() => {
            void summary.refetch()
            void types.refetch()
          }}
        />
      </div>
    )
  const tabs: Array<[typeof section, string]> = [
    ['pending', 'Pending requests'],
    ['team', 'Team leave'],
    ['calendar', 'Team calendar'],
    ['reviewed', 'Recently reviewed'],
  ]
  return (
    <div className="mx-auto max-w-[1480px] space-y-7 p-4 sm:p-6 lg:p-8">
      <PageHeader
        actions={
          <Link
            className="rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold"
            to="/leave"
          >
            My Leave
          </Link>
        }
        description="Review requests with the balance and availability context needed to make a confident decision."
        eyebrow="Manager workspace"
        title="Team Leave"
      />
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          icon={Clock3}
          label="Pending approval"
          value={summary.data.pending_count}
          attention={summary.data.pending_count > 0}
        />
        <Metric
          icon={Users}
          label="Away today"
          value={summary.data.away_today.length}
        />
        <Metric
          icon={CalendarDays}
          label="Upcoming leave"
          value={summary.data.upcoming.length}
        />
        <Metric
          icon={CheckCircle2}
          label="Recently reviewed"
          value={summary.data.recently_reviewed.length}
        />
      </section>
      {summary.data.away_today.length > 0 && (
        <section className="rounded-2xl border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">People away today</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            {summary.data.away_today.map((person) => (
              <div
                className="flex min-w-56 items-center gap-3 rounded-xl bg-muted/50 p-3"
                key={person.employee_id}
              >
                <PersonMark name={person.employee_name} />
                <div>
                  <p className="text-sm font-semibold">
                    {person.employee_name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Away · returns after {formatDay(person.end_date)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
      <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
        <nav
          aria-label="Manager leave views"
          className="flex gap-1 overflow-x-auto border-b p-2"
        >
          {tabs.map(([value, label]) => (
            <button
              aria-current={section === value ? 'page' : undefined}
              className={`whitespace-nowrap rounded-xl px-4 py-2 text-sm font-semibold ${section === value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
              key={value}
              onClick={() => {
                setSection(value)
                setPage(1)
              }}
              type="button"
            >
              {label}
              {value === 'pending' && summary.data.pending_count > 0
                ? ` (${summary.data.pending_count})`
                : ''}
            </button>
          ))}
        </nav>
        <div className="grid gap-3 border-b p-4 lg:grid-cols-[minmax(220px,1fr)_220px_170px_170px_auto]">
          <label className="relative">
            <span className="sr-only">Search employees</span>
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <input
              className="w-full rounded-xl border bg-background py-2 pl-9 pr-3 text-sm"
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
              placeholder="Search employee"
              value={search}
            />
          </label>
          {section !== 'calendar' && (
            <label>
              <span className="sr-only">Leave type</span>
              <select
                className="w-full rounded-xl border bg-background px-3 py-2 text-sm"
                onChange={(event) => {
                  setLeaveType(event.target.value)
                  setPage(1)
                }}
                value={leaveType}
              >
                <option value="">All leave types</option>
                {types.data.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            <span className="sr-only">From date</span>
            <input
              aria-label="From date"
              className="w-full rounded-xl border bg-background px-3 py-2 text-sm"
              onChange={(event) => setStartDate(event.target.value)}
              type="date"
              value={startDate}
            />
          </label>
          <label>
            <span className="sr-only">To date</span>
            <input
              aria-label="To date"
              className="w-full rounded-xl border bg-background px-3 py-2 text-sm"
              min={startDate}
              onChange={(event) => setEndDate(event.target.value)}
              type="date"
              value={endDate}
            />
          </label>
          <button
            className="rounded-xl border px-3 py-2 text-sm font-semibold"
            onClick={() => {
              setSearch('')
              setLeaveType('')
              setStartDate(dateValue(-14))
              setEndDate(dateValue(60))
              setPage(1)
            }}
            type="button"
          >
            Reset
          </button>
        </div>
        {section === 'calendar' ? (
          availability.isLoading ? (
            <div className="p-5">
              <LoadingState label="Loading team availability" />
            </div>
          ) : availability.isError ? (
            <div className="p-5">
              <ErrorState retry={() => void availability.refetch()} />
            </div>
          ) : filteredAvailability.length ? (
            <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
              {filteredAvailability.map((person, index) => (
                <article
                  className="flex items-center gap-3 rounded-xl border p-4"
                  key={`${person.employee_id}-${person.start_date}-${index}`}
                >
                  <PersonMark name={person.employee_name} />
                  <div className="min-w-0">
                    <p className="truncate font-semibold">
                      {person.employee_name}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Away · {formatDay(person.start_date)} –{' '}
                      {formatDay(person.end_date)}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="p-5">
              <EmptyState
                detail="No approved absences fall within the selected dates."
                title="The team is available"
              />
            </div>
          )
        ) : requests.isLoading ? (
          <div className="p-5">
            <LoadingState label="Loading leave requests" />
          </div>
        ) : requests.isError || !requests.data ? (
          <div className="p-5">
            <ErrorState retry={() => void requests.refetch()} />
          </div>
        ) : requests.data.items.length ? (
          <>
            <div className="divide-y">
              {requests.data.items.map((request) => (
                <Link
                  className="grid gap-3 p-4 hover:bg-muted/40 sm:grid-cols-[minmax(220px,1.2fr)_1fr_130px_120px] sm:items-center"
                  key={request.id}
                  params={{ requestId: request.id }}
                  to="/leave/requests/$requestId"
                >
                  <div className="flex items-center gap-3">
                    <PersonMark name={request.employee_name ?? 'Employee'} />
                    <div className="min-w-0">
                      <p className="truncate font-semibold">
                        {request.employee_name ?? 'Employee'}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {request.department_name || 'No department'}
                        {request.employee_number
                          ? ` · ${request.employee_number}`
                          : ''}
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-semibold">
                      {request.leave_type_name ?? 'Leave'}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatDay(request.start_date)} –{' '}
                      {formatDay(request.end_date)}
                    </p>
                  </div>
                  <p className="text-sm font-medium">
                    {formatDays(Number(request.duration_days))}
                  </p>
                  <StatusBadge value={request.status} />
                </Link>
              ))}
            </div>
            <Pagination
              onPage={setPage}
              page={page}
              pageSize={25}
              total={requests.data.total}
            />
          </>
        ) : (
          <div className="p-5">
            <EmptyState
              detail={
                section === 'pending'
                  ? 'You have reviewed every request currently assigned to you.'
                  : 'No leave requests match the current filters.'
              }
              title={
                section === 'pending'
                  ? 'No pending leave requests'
                  : 'No team leave found'
              }
            />
          </div>
        )}
      </section>
    </div>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
  attention = false,
}: {
  icon: typeof Clock3
  label: string
  value: number
  attention?: boolean
}) {
  return (
    <article className="rounded-2xl border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{label}</p>
        <Icon
          className={`size-5 ${attention ? 'text-amber-600' : 'text-primary'}`}
        />
      </div>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
    </article>
  )
}
