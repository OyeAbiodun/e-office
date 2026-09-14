import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Printer,
  RotateCcw,
  Send,
} from 'lucide-react'
import { useState } from 'react'

import { reportsApi } from './api'
import { useAuth } from '@/features/auth/auth-store'

const label = (value: string) =>
  value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

export function ReportDetailPage() {
  const { reportId } = useParams({ strict: false }) as { reportId: string }
  const { user } = useAuth()
  const permissions = new Set(user?.permissions ?? [])
  const client = useQueryClient()
  const [returnReason, setReturnReason] = useState('')
  const detail = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => reportsApi.detail(reportId),
  })
  const invalidate = () => {
    void client.invalidateQueries({ queryKey: ['report', reportId] })
    void client.invalidateQueries({ queryKey: ['reports'] })
    void client.invalidateQueries({ queryKey: ['reporting-dashboard'] })
  }
  const edit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, string> }) =>
      reportsApi.edit(id, body),
    onSuccess: invalidate,
  })
  const submit = useMutation({
    mutationFn: reportsApi.submit,
    onSuccess: invalidate,
  })
  const review = useMutation({
    mutationFn: ({
      action,
      comment,
    }: {
      action: 'accept' | 'return'
      comment?: string
    }) => reportsApi.review(reportId, action, comment),
    onSuccess: invalidate,
  })
  const report = detail.data?.report
  const summary = report?.authoritative_snapshot.summary as
    Record<string, number> | undefined
  const narrative = report?.narrative as Record<string, string> | undefined
  const editable =
    !!report &&
    report.owner_id === user?.id &&
    ['generated_draft', 'draft', 'returned'].includes(report.status)
  const awaitingReview =
    !!report && ['submitted', 'auto_submitted'].includes(report.status)

  const download = async (format: 'pdf' | 'csv' | 'xlsx') => {
    const blob = await reportsApi.export(reportId, format)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `report-${reportId}.${format}`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  if (detail.isLoading)
    return <main className="m-6 h-96 animate-pulse rounded-2xl bg-muted" />
  if (!report)
    return (
      <main className="p-6">
        <p className="rounded-xl bg-destructive/10 p-4 text-destructive">
          This report is unavailable or you do not have access.
        </p>
      </main>
    )

  return (
    <main className="report-document w-full space-y-6 p-4 sm:p-6 lg:p-8">
      <Link
        className="inline-flex items-center gap-2 text-sm text-primary"
        to="/reports"
      >
        <ArrowLeft size={16} /> Back to reports
      </Link>
      <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">
            {label(report.report_type)} report · Version {report.version}
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            {report.subject_name}
          </h1>
          <p className="mt-2 text-muted-foreground">
            {report.period_start} – {report.period_end} · {report.timezone}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-3 text-sm font-semibold"
            onClick={() => window.print()}
            type="button"
          >
            <Printer size={16} /> Print
          </button>
          {permissions.has('reports.export') &&
            (['pdf', 'csv', 'xlsx'] as const).map((format) => (
              <button
                className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-3 text-sm font-semibold"
                key={format}
                onClick={() => void download(format)}
                type="button"
              >
                <Download size={16} /> {format.toUpperCase()}
              </button>
            ))}
          {editable && permissions.has('reports.submit_own') && (
            <button
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-4 font-semibold text-primary-foreground"
              disabled={submit.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    `Submit this ${report.period_type} report for ${report.period_start} through ${report.period_end} for manager review?`,
                  )
                )
                  submit.mutate(report.id)
              }}
              type="button"
            >
              <Send size={16} /> Submit for review
            </button>
          )}
        </div>
      </header>

      {report.return_reason && (
        <div className="rounded-xl border border-amber-400/40 bg-amber-500/10 p-4">
          <strong>Returned for correction</strong>
          <p className="mt-1 text-sm">{report.return_reason}</p>
        </div>
      )}

      {(edit.isError || submit.isError || review.isError) && (
        <p
          role="alert"
          className="rounded-xl bg-destructive/10 p-4 text-destructive"
        >
          {(edit.error ?? submit.error ?? review.error)?.message}
        </p>
      )}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {[
          ['Tasks', summary?.tasks_total ?? 0],
          ['Completed', summary?.tasks_completed ?? 0],
          ['Overdue', summary?.tasks_overdue ?? 0],
          ['Activities', summary?.activities ?? 0],
          ['Meetings', summary?.meetings ?? 0],
          ['Projects', summary?.projects ?? 0],
        ].map(([text, value]) => (
          <div className="rounded-2xl border bg-card p-4" key={text}>
            <span className="text-sm text-muted-foreground">{text}</span>
            <strong className="mt-2 block text-2xl">{value}</strong>
          </div>
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <NarrativeEditor
          busy={edit.isPending}
          editable={editable}
          narrative={narrative ?? {}}
          onSave={(body) => edit.mutate({ id: report.id, body })}
        />
        <div className="space-y-5">
          <div className="rounded-2xl border bg-card p-5 shadow-sm">
            <h2 className="text-lg font-semibold">Workflow</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <Row name="Status" value={label(report.status)} />
              <Row
                name="Submission"
                value={label(report.submission_mode ?? 'Not submitted')}
              />
              <Row
                name="Generated"
                value={new Date(report.generated_at).toLocaleString()}
              />
              <Row
                name="Finalized"
                value={
                  report.finalized_at
                    ? new Date(report.finalized_at).toLocaleString()
                    : '—'
                }
              />
            </dl>
          </div>
          {awaitingReview && permissions.has('reports.review_team') && (
            <div className="rounded-2xl border bg-card p-5 shadow-sm">
              <h2 className="text-lg font-semibold">Manager decision</h2>
              <label className="mt-4 block text-sm font-medium">
                Return note
                <textarea
                  className="mt-1 min-h-24 w-full rounded-xl border bg-background p-3"
                  onChange={(event) => setReturnReason(event.target.value)}
                  placeholder="Required when returning the report"
                  value={returnReason}
                />
              </label>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-emerald-600 px-4 font-semibold text-white"
                  onClick={() => review.mutate({ action: 'accept' })}
                  type="button"
                >
                  <CheckCircle2 size={17} /> Accept and finalize
                </button>
                <button
                  className="inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 font-semibold disabled:opacity-50"
                  disabled={!returnReason.trim()}
                  onClick={() =>
                    review.mutate({ action: 'return', comment: returnReason })
                  }
                  type="button"
                >
                  <RotateCcw size={17} /> Return
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <Timeline
          items={(detail.data?.history ?? []).map((item) => ({
            id: item.id,
            title: label(item.action),
            detail: item.note,
            date: item.created_at,
          }))}
          title="Review history"
        />
        <Timeline
          items={(detail.data?.versions ?? []).map((item) => ({
            id: item.id,
            title: `Version ${item.version}`,
            detail: 'Historical source snapshot and narrative preserved',
            date: item.created_at,
          }))}
          title="Version history"
        />
      </section>
    </main>
  )
}

function NarrativeEditor({
  narrative,
  editable,
  busy,
  onSave,
}: {
  narrative: Record<string, string>
  editable: boolean
  busy: boolean
  onSave: (body: Record<string, string>) => void
}) {
  const [value, setValue] = useState(narrative)
  const sections: Array<[string, string]> = [
    ['accomplishments', 'Accomplishments'],
    ['challenges', 'Challenges and blockers'],
    ['explanation', 'Context and explanation'],
    ['follow_ups', 'Follow-ups'],
    ['next_priorities', 'Next priorities'],
    ['notes', 'Additional notes'],
  ]
  return (
    <form
      className="rounded-2xl border bg-card p-5 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(value)
      }}
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Report narrative</h2>
          <p className="text-sm text-muted-foreground">
            Source metrics are immutable; narrative remains editable before
            submission.
          </p>
        </div>
        <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-semibold">
          {editable ? 'Editable' : 'Read only'}
        </span>
      </div>
      <div className="mt-5 grid gap-4">
        {sections.map(([key, text]) => (
          <label className="text-sm font-medium" key={key}>
            {text}
            <textarea
              className="mt-1 min-h-24 w-full rounded-xl border bg-background p-3 disabled:opacity-70"
              disabled={!editable}
              onChange={(event) =>
                setValue((current) => ({
                  ...current,
                  [key]: event.target.value,
                }))
              }
              value={value[key] ?? ''}
            />
          </label>
        ))}
      </div>
      {editable && (
        <button
          className="mt-4 min-h-11 rounded-xl bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-50"
          disabled={busy}
          type="submit"
        >
          {busy ? 'Saving…' : 'Save draft'}
        </button>
      )}
    </form>
  )
}

function Row({ name, value }: { name: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b pb-2 last:border-0">
      <dt className="text-muted-foreground">{name}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  )
}

function Timeline({
  title,
  items,
}: {
  title: string
  items: Array<{
    id: string
    title: string
    detail: string | null
    date: string
  }>
}) {
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm">
      <h2 className="text-lg font-semibold">{title}</h2>
      <ol className="mt-4 space-y-4">
        {items.map((item) => (
          <li className="border-l-2 border-primary/30 pl-4" key={item.id}>
            <p className="font-medium">{item.title}</p>
            {item.detail && (
              <p className="text-sm text-muted-foreground">{item.detail}</p>
            )}
            <time className="text-xs text-muted-foreground">
              {new Date(item.date).toLocaleString()}
            </time>
          </li>
        ))}
      </ol>
    </section>
  )
}
