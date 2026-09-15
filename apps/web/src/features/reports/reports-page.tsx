import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  BarChart3,
  CalendarClock,
  CheckCircle2,
  FilePlus2,
  Filter,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'

import { DecisionBarChart } from '@/components/decision-chart'
import { reportsApi, type PeriodType, type ReportType } from './api'
import { useAuth } from '@/features/auth/auth-store'
import { organizationApi } from '@/features/organizations/api'
import { projectsApi } from '@/features/projects/api'
import { tasksApi } from '@/features/tasks/api'

const label = (value: string) =>
  value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

const iso = (date: Date) => date.toISOString().slice(0, 10)
const today = () => iso(new Date())
const weekStart = () => {
  const value = new Date()
  value.setDate(value.getDate() - 6)
  return iso(value)
}
const initialTab = () => {
  const value = new URLSearchParams(window.location.search).get('tab')
  return ['overview', 'reports', 'review', 'policy'].includes(value ?? '')
    ? (value as 'overview' | 'reports' | 'review' | 'policy')
    : 'overview'
}

export function ReportsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const permissions = new Set(user?.permissions ?? [])
  const client = useQueryClient()
  const [tab, setTab] = useState<'overview' | 'reports' | 'review' | 'policy'>(
    initialTab,
  )
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [historyType, setHistoryType] = useState('')
  const [historyPeriod, setHistoryPeriod] = useState('')
  const [reportType, setReportType] = useState<ReportType>('employee')
  const [periodType, setPeriodType] = useState<PeriodType>('weekly')
  const [subjectId, setSubjectId] = useState(user?.id ?? '')
  const [start, setStart] = useState(weekStart())
  const [end, setEnd] = useState(today())
  const [showGenerate, setShowGenerate] = useState(false)
  const [insightWindow, setInsightWindow] = useState('weekly')

  const dashboard = useQuery({
    queryKey: ['reporting-dashboard'],
    queryFn: reportsApi.dashboard,
  })
  const reports = useQuery({
    queryKey: [
      'reports',
      status,
      search,
      historyType,
      historyPeriod,
      page,
      pageSize,
      tab,
    ],
    queryFn: () =>
      reportsApi.list({
        status:
          tab === 'review' && !status ? 'pending_review' : status || undefined,
        search: search || undefined,
        report_type: historyType || undefined,
        period_type: historyPeriod || undefined,
        page,
        page_size: pageSize,
      }),
  })
  const people = useQuery({
    queryKey: ['report-subjects', 'people'],
    queryFn: tasksApi.assignees,
    enabled: showGenerate && reportType === 'employee',
  })
  const departments = useQuery({
    queryKey: ['report-subjects', 'departments'],
    queryFn: () => organizationApi.departments({ page: 1, page_size: 100 }),
    enabled: showGenerate && reportType === 'department',
  })
  const teams = useQuery({
    queryKey: ['report-subjects', 'teams'],
    queryFn: organizationApi.teams,
    enabled: showGenerate && reportType === 'team',
  })
  const projects = useQuery({
    queryKey: ['report-subjects', 'projects'],
    queryFn: () => projectsApi.list({ page: 1, page_size: 100 }),
    enabled: showGenerate && reportType === 'project',
  })
  const preview = useQuery({
    queryKey: ['report-source-preview', start, end],
    queryFn: () => reportsApi.preview(start, end),
    enabled:
      showGenerate && reportType === 'employee' && subjectId === user?.id,
  })
  const policy = useQuery({
    queryKey: ['report-policy'],
    queryFn: reportsApi.policy,
    enabled: tab === 'policy' && permissions.has('reports.manage_policy'),
  })

  const generate = useMutation({
    mutationFn: reportsApi.generate,
    onSuccess: (created) => {
      setShowGenerate(false)
      void client.invalidateQueries({ queryKey: ['reports'] })
      void client.invalidateQueries({ queryKey: ['reporting-dashboard'] })
      void navigate({
        to: '/reports/$reportId',
        params: { reportId: created.id },
      })
    },
  })
  const updatePolicy = useMutation({
    mutationFn: reportsApi.updatePolicy,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['report-policy'] })
    },
  })

  const subjects = useMemo(() => {
    if (reportType === 'employee')
      return (people.data ?? []).map((item) => ({
        id: item.id,
        name: item.display_name,
      }))
    if (reportType === 'department')
      return (departments.data?.items ?? []).map((item) => ({
        id: item.id,
        name: item.name,
      }))
    if (reportType === 'team')
      return (teams.data ?? []).map((item) => ({
        id: item.id,
        name: item.name,
      }))
    if (reportType === 'project')
      return (projects.data?.items ?? []).map((item) => ({
        id: item.id,
        name: `${item.project_code} · ${item.name}`,
      }))
    return []
  }, [departments.data, people.data, projects.data, reportType, teams.data])
  const summary = preview.data?.snapshot.summary as
    Record<string, number> | undefined

  return (
    <main className="w-full space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">
            Management intelligence
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Reports & Intelligence
          </h1>
          <p className="mt-2 max-w-3xl text-muted-foreground">
            Turn canonical work, activity, meetings, and projects into
            reviewable historical reports—without duplicating operational
            records.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs font-semibold text-muted-foreground">
            Review window
            <select
              aria-label="Review window"
              className="control mt-1 min-w-32"
              onChange={(event) => {
                const value = event.target.value
                setInsightWindow(value)
                setHistoryPeriod(value === 'quarterly' ? '' : value)
                setPage(1)
              }}
              value={insightWindow}
            >
              <option value="weekly">This week</option>
              <option value="monthly">This month</option>
              <option value="quarterly">This quarter</option>
              <option value="custom">Custom reports</option>
            </select>
          </label>
          {(permissions.has('reports.create_own') ||
            permissions.has('reports.generate')) && (
            <button
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-semibold text-primary-foreground hover:bg-primary-hover"
              onClick={() => setShowGenerate(true)}
              type="button"
            >
              <FilePlus2 size={18} /> Generate report
            </button>
          )}
        </div>
      </header>

      <nav
        aria-label="Report sections"
        className="flex gap-2 overflow-x-auto border-b"
      >
        {[
          ['overview', 'Overview'],
          ['reports', 'Report history'],
          ...(permissions.has('reports.review_team')
            ? ([['review', 'Manager review']] as const)
            : []),
          ...(permissions.has('reports.manage_policy')
            ? ([['policy', 'Reporting policy']] as const)
            : []),
        ].map(([value, text]) => (
          <button
            className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-semibold ${
              tab === value
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground'
            }`}
            key={value}
            onClick={() => {
              const next = value as typeof tab
              setTab(next)
              setPage(1)
              const url = new URL(window.location.href)
              url.searchParams.set('tab', next)
              window.history.replaceState({}, '', url)
            }}
            type="button"
          >
            {text}
          </button>
        ))}
      </nav>

      {tab === 'overview' && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Metric
              icon={<CalendarClock size={18} />}
              label="Drafts to review"
              to="/reports?tab=review&status=pending_review"
              value={dashboard.data?.pending_my_review ?? 0}
            />
            <Metric
              icon={<ShieldCheck size={18} />}
              label="Awaiting manager"
              to="/reports?tab=reports&status=submitted"
              value={dashboard.data?.awaiting_manager_review ?? 0}
            />
            <Metric
              icon={<TriangleAlert size={18} />}
              label="Overdue tasks"
              to="/tasks?due=overdue"
              value={dashboard.data?.overdue_tasks ?? 0}
            />
            <Metric
              icon={<BarChart3 size={18} />}
              label="Projects at risk"
              to="/projects?health=at_risk"
              value={dashboard.data?.projects_at_risk ?? 0}
            />
            <Metric
              icon={<CheckCircle2 size={18} />}
              label="Reporting compliance"
              to="/reports?tab=reports"
              value={`${dashboard.data?.reporting_compliance_percent ?? 100}%`}
            />
          </section>
          <section className="grid gap-4 lg:grid-cols-2">
            <DecisionBarChart
              data={[
                {
                  label: 'Open tasks',
                  value: dashboard.data?.open_tasks ?? 0,
                  to: '/tasks?status=in_progress',
                  tone: 'primary',
                },
                {
                  label: 'Overdue tasks',
                  value: dashboard.data?.overdue_tasks ?? 0,
                  to: '/tasks?due=overdue',
                  tone: 'danger',
                },
                {
                  label: 'Unresolved blockers',
                  value: dashboard.data?.unresolved_blockers ?? 0,
                  to: '/tasks?status=blocked',
                  tone: 'warning',
                },
              ]}
              description="Current tenant-scoped workload requiring action."
              title="Work delivery"
            />
            <DecisionBarChart
              data={[
                {
                  label: 'Finalized',
                  value: dashboard.data?.finalized_this_period ?? 0,
                  to: '/reports?tab=reports&status=final',
                  tone: 'success',
                },
                {
                  label: 'Awaiting manager',
                  value: dashboard.data?.awaiting_manager_review ?? 0,
                  to: '/reports?tab=review&status=pending_review',
                  tone: 'info',
                },
                {
                  label: 'Returned',
                  value: dashboard.data?.returned ?? 0,
                  to: '/reports?tab=reports&status=returned',
                  tone: 'danger',
                },
              ]}
              description="Select a stage to inspect its report history."
              title="Reporting flow"
            />
          </section>
          <section className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <ReportList
              error={reports.isError}
              loading={reports.isLoading}
              reports={reports.data?.items ?? []}
            />
            <div className="rounded-2xl border bg-card p-5 shadow-sm">
              <h2 className="text-lg font-semibold">Department activity</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Recorded daily activity from live organization data.
              </p>
              <div className="mt-5 space-y-4">
                {(dashboard.data?.department_activity ?? []).map((item) => (
                  <div key={item.department}>
                    <div className="flex justify-between text-sm">
                      <span>{item.department}</span>
                      <strong>{item.activities}</strong>
                    </div>
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{
                          width: `${Math.min(100, Math.max(6, item.activities * 8))}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
                {!dashboard.isLoading &&
                  !dashboard.data?.department_activity.length && (
                    <p className="rounded-xl bg-muted/50 p-4 text-sm text-muted-foreground">
                      No department activity has been recorded yet.
                    </p>
                  )}
              </div>
            </div>
          </section>
        </>
      )}

      {(tab === 'reports' || tab === 'review') && (
        <section className="rounded-2xl border bg-card shadow-sm">
          <div className="flex flex-col gap-3 border-b p-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-lg font-semibold">
                {tab === 'review' ? 'Manager review queue' : 'Report history'}
              </h2>
              <p className="text-sm text-muted-foreground">
                {reports.data?.total ?? 0} tenant-scoped reports
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <label className="flex min-h-11 items-center rounded-xl border bg-background px-3">
                <span className="sr-only">Search reports</span>
                <input
                  className="min-w-0 bg-transparent text-sm outline-none"
                  onChange={(event) => {
                    setSearch(event.target.value)
                    setPage(1)
                  }}
                  placeholder="Search subject"
                  value={search}
                />
              </label>
              <label className="flex min-h-11 items-center rounded-xl border bg-background px-3">
                <span className="sr-only">Filter report type</span>
                <select
                  className="bg-transparent text-sm outline-none"
                  onChange={(event) => {
                    setHistoryType(event.target.value)
                    setPage(1)
                  }}
                  value={historyType}
                >
                  <option value="">All scopes</option>
                  {[
                    'employee',
                    'team',
                    'department',
                    'project',
                    'management',
                  ].map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex min-h-11 items-center rounded-xl border bg-background px-3">
                <span className="sr-only">Filter report period</span>
                <select
                  className="bg-transparent text-sm outline-none"
                  onChange={(event) => {
                    setHistoryPeriod(event.target.value)
                    setPage(1)
                  }}
                  value={historyPeriod}
                >
                  <option value="">All periods</option>
                  {['daily', 'weekly', 'monthly', 'custom'].map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex min-h-11 items-center gap-2 rounded-xl border bg-background px-3">
                <Filter size={16} />
                <span className="sr-only">Filter report status</span>
                <select
                  className="bg-transparent text-sm outline-none"
                  onChange={(event) => {
                    setStatus(event.target.value)
                    setPage(1)
                  }}
                  value={status}
                >
                  <option value="">All statuses</option>
                  {[
                    'generated_draft',
                    'draft',
                    'submitted',
                    'auto_submitted',
                    'returned',
                    'final',
                  ].map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          <ReportList
            error={reports.isError}
            loading={reports.isLoading}
            reports={reports.data?.items ?? []}
          />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t p-4 text-sm">
            <button
              className="rounded-lg border px-3 py-2 disabled:opacity-40"
              disabled={page <= 1}
              onClick={() => setPage((value) => value - 1)}
              type="button"
            >
              Previous
            </button>
            <span>
              Page {page} of {reports.data?.total_pages ?? 1}
            </span>
            <label className="flex items-center gap-2">
              Rows
              <select
                className="rounded-lg border bg-background px-2 py-2"
                onChange={(event) => {
                  setPageSize(Number(event.target.value))
                  setPage(1)
                }}
                value={pageSize}
              >
                {[10, 25, 50, 100].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="rounded-lg border px-3 py-2 disabled:opacity-40"
              disabled={page >= (reports.data?.total_pages ?? 1)}
              onClick={() => setPage((value) => value + 1)}
              type="button"
            >
              Next
            </button>
          </div>
        </section>
      )}

      {tab === 'policy' && policy.data && (
        <PolicyEditor
          busy={updatePolicy.isPending}
          policy={policy.data}
          onSave={(body) => updatePolicy.mutate(body)}
        />
      )}

      {showGenerate && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <form
            aria-label="Generate report"
            className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl border bg-background p-5 shadow-2xl"
            onSubmit={(event) => {
              event.preventDefault()
              generate.mutate({
                report_type: reportType,
                subject_id: reportType === 'management' ? null : subjectId,
                period_type: periodType,
                period_start: start,
                period_end: end,
              })
            }}
          >
            <h2 className="text-xl font-semibold">Generate a report</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              The generated snapshot remains historically stable even when
              source records change later.
            </p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <Field label="Report scope">
                <select
                  className="control"
                  onChange={(event) => {
                    const next = event.target.value as ReportType
                    setReportType(next)
                    setSubjectId(next === 'employee' ? (user?.id ?? '') : '')
                  }}
                  value={reportType}
                >
                  <option value="employee">Employee</option>
                  {permissions.has('reports.view_team') && (
                    <option value="team">Team</option>
                  )}
                  {permissions.has('reports.view_department') && (
                    <option value="department">Department</option>
                  )}
                  {permissions.has('projects.generate_reports') && (
                    <option value="project">Project</option>
                  )}
                  {permissions.has('reports.view_management') && (
                    <option value="management">Management</option>
                  )}
                </select>
              </Field>
              <Field label="Period">
                <select
                  className="control"
                  onChange={(event) =>
                    setPeriodType(event.target.value as PeriodType)
                  }
                  value={periodType}
                >
                  {['daily', 'weekly', 'monthly', 'custom'].map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </select>
              </Field>
              {reportType !== 'management' && (
                <Field label="Subject">
                  {reportType === 'employee' &&
                  !permissions.has('reports.view_team') ? (
                    <input
                      className="control"
                      disabled
                      value={user?.display_name ?? 'Me'}
                    />
                  ) : (
                    <select
                      className="control"
                      onChange={(event) => setSubjectId(event.target.value)}
                      required
                      value={subjectId}
                    >
                      <option value="">Select a subject</option>
                      {subjects.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  )}
                </Field>
              )}
              <Field label="Start date">
                <input
                  className="control"
                  onChange={(event) => setStart(event.target.value)}
                  required
                  type="date"
                  value={start}
                />
              </Field>
              <Field label="End date">
                <input
                  className="control"
                  min={start}
                  onChange={(event) => setEnd(event.target.value)}
                  required
                  type="date"
                  value={end}
                />
              </Field>
            </div>
            {summary && (
              <div className="mt-5 grid grid-cols-3 gap-2 rounded-xl bg-muted/50 p-4 text-center text-sm">
                <span>
                  <strong className="block text-lg">
                    {summary.tasks_total ?? 0}
                  </strong>
                  Tasks
                </span>
                <span>
                  <strong className="block text-lg">
                    {summary.activities ?? 0}
                  </strong>
                  Activities
                </span>
                <span>
                  <strong className="block text-lg">
                    {summary.meetings ?? 0}
                  </strong>
                  Meetings
                </span>
              </div>
            )}
            {generate.isError && (
              <p className="mt-4 rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
                {generate.error.message}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <button
                className="min-h-11 rounded-xl border px-4"
                onClick={() => setShowGenerate(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="min-h-11 rounded-xl bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-50"
                disabled={
                  generate.isPending ||
                  (reportType !== 'management' && !subjectId)
                }
                type="submit"
              >
                {generate.isPending ? 'Generating…' : 'Generate draft'}
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  )
}

function ReportList({
  reports,
  loading,
  error,
}: {
  reports: Awaited<ReturnType<typeof reportsApi.list>>['items']
  loading: boolean
  error: boolean
}) {
  if (loading)
    return <div className="m-4 h-40 animate-pulse rounded-xl bg-muted" />
  if (error)
    return (
      <p className="m-4 rounded-xl bg-destructive/10 p-4 text-destructive">
        Reports could not be loaded. Try again.
      </p>
    )
  if (!reports.length)
    return (
      <p className="m-4 rounded-xl bg-muted/50 p-6 text-center text-muted-foreground">
        No reports match this view.
      </p>
    )
  return (
    <div className="data-region divide-y" data-report-list>
      {reports.map((report) => (
        <Link
          className="grid min-h-12 gap-2 px-4 py-2.5 transition hover:bg-muted/40 sm:grid-cols-[1fr_auto_auto] sm:items-center"
          key={report.id}
          params={{ reportId: report.id }}
          to="/reports/$reportId"
        >
          <div>
            <p className="font-semibold">{report.subject_name}</p>
            <p className="text-sm text-muted-foreground">
              {label(report.report_type)} · {label(report.period_type)} ·{' '}
              {report.period_start} – {report.period_end}
            </p>
          </div>
          <span className="w-fit rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
            {label(report.status)}
          </span>
          <span className="text-sm text-muted-foreground">
            v{report.version}
          </span>
        </Link>
      ))}
    </div>
  )
}

function Metric({
  label: text,
  value,
  icon,
  to,
}: {
  label: string
  value: number | string
  icon: ReactNode
  to: string
}) {
  return (
    <Link
      aria-label={`${text}: ${value}. View details`}
      className="rounded-xl border bg-card p-4 shadow-sm transition hover:border-primary-border hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      to={to as never}
    >
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-sm">{text}</span>
        {icon}
      </div>
      <strong className="mt-3 block text-2xl">{value}</strong>
    </Link>
  )
}

function Field({
  label: text,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <label className="space-y-1.5 text-sm font-medium">
      <span>{text}</span>
      {children}
    </label>
  )
}

function PolicyEditor({
  policy,
  busy,
  onSave,
}: {
  policy: Awaited<ReturnType<typeof reportsApi.policy>>
  busy: boolean
  onSave: (
    body: Omit<typeof policy, 'id' | 'organization_id' | 'updated_at'>,
  ) => void
}) {
  const [value, setValue] = useState(policy)
  return (
    <form
      className="max-w-5xl rounded-2xl border bg-card p-5 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault()
        if (
          !policy.automatic_submit &&
          value.automatic_submit &&
          !window.confirm(
            'Enable automatic submission? Generated reports will be submitted after the configured review deadline.',
          )
        )
          return
        const body: Omit<
          typeof policy,
          'id' | 'organization_id' | 'updated_at'
        > = {
          daily_enabled: value.daily_enabled,
          weekly_enabled: value.weekly_enabled,
          monthly_enabled: value.monthly_enabled,
          review_before_send: value.review_before_send,
          automatic_submit: value.automatic_submit,
          week_start: value.week_start,
          week_end: value.week_end,
          generation_time: value.generation_time,
          submission_deadline_hours: value.submission_deadline_hours,
          manager_review_required: value.manager_review_required,
          reminder_hours_before: value.reminder_hours_before,
          timezone: value.timezone,
          enabled_report_types: value.enabled_report_types,
        }
        onSave(body)
      }}
    >
      <h2 className="text-xl font-semibold">Organization reporting policy</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Review before send is enabled by default. Automatic submission remains
        an explicit administrator choice.
      </p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {(
          [
            ['daily_enabled', 'Generate daily reports'],
            ['weekly_enabled', 'Generate weekly reports'],
            ['monthly_enabled', 'Generate monthly reports'],
            ['review_before_send', 'Review before submission'],
            ['automatic_submit', 'Automatically submit generated reports'],
            ['manager_review_required', 'Require manager approval'],
          ] as const
        ).map(([key, text]) => (
          <label
            className="flex min-h-12 items-center gap-3 rounded-xl border p-3"
            key={key}
          >
            <input
              checked={Boolean(value[key as keyof typeof value])}
              onChange={(event) =>
                setValue((current) => ({
                  ...current,
                  [key]: event.target.checked,
                }))
              }
              type="checkbox"
            />
            <span className="text-sm font-medium">{text}</span>
          </label>
        ))}
        <Field label="Submission deadline (hours)">
          <input
            className="control"
            max={336}
            min={1}
            onChange={(event) =>
              setValue((current) => ({
                ...current,
                submission_deadline_hours: Number(event.target.value),
              }))
            }
            type="number"
            value={value.submission_deadline_hours}
          />
        </Field>
        <Field label="Reminder lead time (hours)">
          <input
            className="control"
            max={168}
            min={0}
            onChange={(event) =>
              setValue((current) => ({
                ...current,
                reminder_hours_before: Number(event.target.value),
              }))
            }
            type="number"
            value={value.reminder_hours_before}
          />
        </Field>
        <Field label="Generation time">
          <input
            className="control"
            onChange={(event) =>
              setValue((current) => ({
                ...current,
                generation_time: event.target.value,
              }))
            }
            type="time"
            value={value.generation_time.slice(0, 5)}
          />
        </Field>
        <Field label="Timezone (IANA)">
          <input
            className="control"
            onChange={(event) =>
              setValue((current) => ({
                ...current,
                timezone: event.target.value,
              }))
            }
            placeholder="America/Chicago"
            required
            value={value.timezone}
          />
        </Field>
        <Field label="Reporting week starts">
          <select
            className="control"
            onChange={(event) =>
              setValue((current) => ({
                ...current,
                week_start: Number(event.target.value),
              }))
            }
            value={value.week_start}
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
        </Field>
        <Field label="Reporting week ends">
          <select
            className="control"
            onChange={(event) =>
              setValue((current) => ({
                ...current,
                week_end: Number(event.target.value),
              }))
            }
            value={value.week_end}
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
        </Field>
      </div>
      <fieldset className="mt-5 rounded-xl border p-4">
        <legend className="px-1 text-sm font-semibold">
          Enabled report periods
        </legend>
        <div className="mt-2 flex flex-wrap gap-4">
          {(['daily', 'weekly', 'monthly', 'custom'] as const).map((period) => (
            <label className="flex min-h-11 items-center gap-2" key={period}>
              <input
                checked={value.enabled_report_types.includes(period)}
                onChange={(event) =>
                  setValue((current) => ({
                    ...current,
                    enabled_report_types: event.target.checked
                      ? [...current.enabled_report_types, period]
                      : current.enabled_report_types.filter(
                          (item) => item !== period,
                        ),
                  }))
                }
                type="checkbox"
              />
              {label(period)}
            </label>
          ))}
        </div>
      </fieldset>
      {value.automatic_submit && (
        <p className="mt-4 rounded-xl border border-amber-400/40 bg-amber-500/10 p-3 text-sm">
          Generated reports will be submitted automatically when the configured
          review deadline passes. Automation is recorded as the actor in report
          history and audit logs.
        </p>
      )}
      <button
        className="mt-5 min-h-11 rounded-xl bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-50"
        disabled={busy}
        type="submit"
      >
        {busy ? 'Saving…' : 'Save reporting policy'}
      </button>
    </form>
  )
}
