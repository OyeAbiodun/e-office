import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import {
  ArrowRight,
  CalendarCheck,
  Clock3,
  FileText,
  History,
  Plus,
  Umbrella,
} from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'

import {
  leaveApi,
  type LeaveAttachment,
  type LeaveBalance,
  type LeaveRequest,
  type LeaveType,
} from './api'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  PageHeader,
  Pagination,
  StatusBadge,
} from './shared'
import { formatDateTime, formatDay, formatDays } from './utils'
import { notify } from '@/components/feedback/events'
import { useConfirmation } from '@/components/feedback/confirmation'
import { useAuth } from '@/features/auth/auth-store'

function balanceType(balance: LeaveBalance, types: LeaveType[]) {
  return types.find((item) => item.id === balance.leave_type_id)
}

export function LeavePage() {
  const { user } = useAuth()
  const client = useQueryClient()
  const canRequest = user?.permissions.includes('leave.request') ?? false
  const canManageTeam = user?.permissions.includes('leave.view_team') ?? false
  const canAdmin =
    user?.permissions.includes('leave.types.manage') ||
    user?.permissions.includes('leave.balances.adjust') ||
    user?.permissions.includes('leave.reports.view')
  const [requestOpen, setRequestOpen] = useState(false)
  const [historyBalance, setHistoryBalance] = useState<LeaveBalance | null>(
    null,
  )
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const summary = useQuery({
    queryKey: ['leave', 'my-summary'],
    queryFn: leaveApi.mySummary,
  })
  const types = useQuery({
    queryKey: ['leave', 'types', 'active'],
    queryFn: () => leaveApi.types({ active: true }),
  })
  const requests = useQuery({
    queryKey: ['leave', 'requests', 'mine', status, page],
    queryFn: () =>
      leaveApi.requests({
        scope: 'mine',
        request_status: status,
        page,
        page_size: 10,
      }),
  })
  const loading = summary.isLoading || types.isLoading || requests.isLoading
  const error = summary.isError || types.isError || requests.isError
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['leave'] }),
      client.invalidateQueries({ queryKey: ['calendar-events'] }),
      client.invalidateQueries({ queryKey: ['notifications'] }),
    ])
  }
  if (loading)
    return (
      <div className="p-5 sm:p-8">
        <LoadingState />
      </div>
    )
  if (error || !summary.data || !types.data || !requests.data)
    return (
      <div className="p-5 sm:p-8">
        <ErrorState retry={() => void refresh()} />
      </div>
    )

  const upcoming = summary.data.upcoming_approved
  const pending = summary.data.pending_requests
  return (
    <div className="mx-auto max-w-[1480px] space-y-7 p-4 sm:p-6 lg:p-8">
      <PageHeader
        actions={
          <>
            {canManageTeam && (
              <Link
                className="rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold hover:bg-muted"
                to="/leave/team"
              >
                Team leave
              </Link>
            )}
            {canAdmin && (
              <Link
                className="rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold hover:bg-muted"
                to="/leave/admin"
              >
                Administration
              </Link>
            )}
            {canRequest && (
              <button
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
                onClick={() => setRequestOpen(true)}
                type="button"
              >
                <Plus className="size-4" /> Request leave
              </button>
            )}
          </>
        }
        description="Understand your balance, request time away, and follow every decision in one place."
        eyebrow="Time away"
        title="My Leave"
      />

      {summary.data.balances.length ? (
        <section
          aria-label="Leave balances"
          className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
        >
          {summary.data.balances.map((balance) => {
            const type = balanceType(balance, types.data)
            return (
              <article
                className="rounded-2xl border bg-card p-5 shadow-sm"
                key={balance.entitlement_id}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">
                      {type?.name ?? 'Leave balance'}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {type?.is_paid === false ? 'Unpaid leave' : 'Paid leave'}
                    </p>
                  </div>
                  <span
                    className="size-3 rounded-full"
                    style={{
                      backgroundColor: type?.color ?? 'hsl(var(--primary))',
                    }}
                  />
                </div>
                <div className="mt-5 flex items-end gap-2">
                  <strong className="text-3xl tracking-tight">
                    {Number(balance.available_after_pending)}
                  </strong>
                  <span className="pb-1 text-sm text-muted-foreground">
                    days available
                  </span>
                </div>
                <dl className="mt-5 grid grid-cols-3 gap-2 border-t pt-4 text-sm">
                  <div>
                    <dt className="text-xs text-muted-foreground">Entitled</dt>
                    <dd className="mt-1 font-semibold">
                      {Number(balance.entitled)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Used</dt>
                    <dd className="mt-1 font-semibold">
                      {Number(balance.used)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Pending</dt>
                    <dd className="mt-1 font-semibold">
                      {Number(balance.pending)}
                    </dd>
                  </div>
                </dl>
                {(Number(balance.carried_forward) > 0 ||
                  Number(balance.expired) > 0) && (
                  <p className="mt-3 text-xs text-muted-foreground">
                    {Number(balance.carried_forward)} carried over
                    {Number(balance.expired)
                      ? ` · ${Number(balance.expired)} expired`
                      : ''}
                  </p>
                )}
                <button
                  className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-primary"
                  onClick={() => setHistoryBalance(balance)}
                  type="button"
                >
                  <History className="size-4" /> View history
                </button>
              </article>
            )
          })}
        </section>
      ) : (
        <EmptyState
          detail="An administrator can allocate your entitlement for the active leave period."
          title="No leave balances are available"
        />
      )}

      <section className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
        <article className="overflow-hidden rounded-2xl border bg-card shadow-sm">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b p-5">
            <div>
              <h2 className="font-semibold">My requests</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Drafts, decisions, and upcoming leave.
              </p>
            </div>
            <label className="text-sm">
              <span className="sr-only">Filter by status</span>
              <select
                className="rounded-xl border bg-background px-3 py-2"
                onChange={(event) => {
                  setStatus(event.target.value)
                  setPage(1)
                }}
                value={status}
              >
                <option value="">All statuses</option>
                {[
                  'draft',
                  'submitted',
                  'approved',
                  'rejected',
                  'withdrawn',
                  'cancelled',
                ].map((value) => (
                  <option key={value} value={value}>
                    {value[0]?.toUpperCase()}
                    {value.slice(1)}
                  </option>
                ))}
              </select>
            </label>
          </header>
          {requests.data.items.length ? (
            <div className="divide-y">
              {requests.data.items.map((request) => (
                <RequestRow key={request.id} request={request} />
              ))}
            </div>
          ) : (
            <div className="p-5">
              <EmptyState
                action={
                  canRequest ? (
                    <button
                      className="text-sm font-semibold text-primary"
                      onClick={() => setRequestOpen(true)}
                      type="button"
                    >
                      Request leave
                    </button>
                  ) : undefined
                }
                detail="Your leave requests will appear here."
                title={
                  status
                    ? 'No requests match this status'
                    : 'You have not requested leave yet'
                }
              />
            </div>
          )}
          <Pagination
            onPage={setPage}
            page={page}
            pageSize={10}
            total={requests.data.total}
          />
        </article>
        <div className="space-y-5">
          <SummaryPanel
            icon={Clock3}
            items={pending}
            title="Pending requests"
            empty="No requests are awaiting review"
          />
          <SummaryPanel
            icon={CalendarCheck}
            items={upcoming}
            title="Upcoming approved leave"
            empty="You have no upcoming leave"
          />
        </div>
      </section>

      {requestOpen && (
        <RequestLeaveDialog
          balances={summary.data.balances}
          onClose={() => setRequestOpen(false)}
          onSaved={refresh}
          types={types.data}
        />
      )}
      {historyBalance && (
        <BalanceHistoryDialog
          balance={historyBalance}
          onClose={() => setHistoryBalance(null)}
          type={balanceType(historyBalance, types.data)}
        />
      )}
    </div>
  )
}

function RequestRow({ request }: { request: LeaveRequest }) {
  return (
    <Link
      className="flex flex-col gap-3 p-4 transition hover:bg-muted/40 sm:flex-row sm:items-center"
      params={{ requestId: request.id }}
      to="/leave/requests/$requestId"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
        <Umbrella className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">
          {request.leave_type_name ??
            request.leave_type_code ??
            'Leave request'}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {formatDay(request.start_date)} – {formatDay(request.end_date)} ·{' '}
          {formatDays(Number(request.duration_days))}
        </p>
      </div>
      <div className="flex items-center justify-between gap-3 sm:justify-end">
        <StatusBadge value={request.status} />
        <ArrowRight className="size-4 text-muted-foreground" />
      </div>
    </Link>
  )
}

function SummaryPanel({
  icon: Icon,
  items,
  title,
  empty,
}: {
  icon: typeof Clock3
  items: LeaveRequest[]
  title: string
  empty: string
}) {
  return (
    <article className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">{title}</h2>
        <Icon className="size-5 text-primary" />
      </div>
      {items.length ? (
        <div className="mt-3 space-y-2">
          {items.slice(0, 4).map((item) => (
            <Link
              className="block rounded-xl bg-muted/45 p-3 hover:bg-muted"
              key={item.id}
              params={{ requestId: item.id }}
              to="/leave/requests/$requestId"
            >
              <p className="text-sm font-semibold">
                {item.leave_type_name ?? 'Leave request'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatDay(item.start_date)} ·{' '}
                {formatDays(Number(item.duration_days))}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-4 rounded-xl border border-dashed p-5 text-center text-sm text-muted-foreground">
          {empty}
        </p>
      )}
    </article>
  )
}

function RequestLeaveDialog({
  balances,
  types,
  onClose,
  onSaved,
}: {
  balances: LeaveBalance[]
  types: LeaveType[]
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const [leaveTypeId, setLeaveTypeId] = useState(types[0]?.id ?? '')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [halfDay, setHalfDay] = useState(false)
  const [reason, setReason] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const intent = useRef<'draft' | 'submit'>('submit')
  const selectedType = types.find((type) => type.id === leaveTypeId)
  const balance = balances.find((item) => item.leave_type_id === leaveTypeId)
  const preview = useQuery({
    queryKey: ['leave', 'preview', startDate, endDate, halfDay],
    queryFn: () =>
      leaveApi.preview({
        start_date: startDate,
        end_date: endDate,
        half_day: halfDay,
      }),
    enabled: Boolean(startDate && endDate && endDate >= startDate),
  })
  const exceeds = Boolean(
    preview.data &&
    balance &&
    Number(preview.data.chargeable_days) >
      Number(balance.available_after_pending),
  )
  const save = useMutation({
    mutationFn: async () => {
      const draft = await leaveApi.createRequest({
        leave_type_id: leaveTypeId,
        start_date: startDate,
        end_date: endDate,
        half_day: halfDay,
        reason: reason || null,
      })
      if (file) await leaveApi.uploadAttachment(draft.id, file)
      return intent.current === 'submit' ? leaveApi.submit(draft.id) : draft
    },
    onSuccess: async () => {
      notify({
        tone: 'success',
        title:
          intent.current === 'submit'
            ? 'Leave request submitted'
            : 'Draft saved',
        description:
          intent.current === 'submit'
            ? 'Your manager can now review the request.'
            : 'You can submit the request from its detail page.',
      })
      await onSaved()
      onClose()
    },
  })
  const invalidBase =
    !leaveTypeId ||
    !startDate ||
    !endDate ||
    endDate < startDate ||
    exceeds ||
    preview.isFetching
  const invalidSubmit =
    invalidBase || Boolean(selectedType?.attachment_required && !file)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!(intent.current === 'submit' ? invalidSubmit : invalidBase))
      save.mutate()
  }
  return (
    <Modal
      description="Choose dates and review the authoritative working-day calculation before submitting."
      onClose={onClose}
      title="Request leave"
    >
      <form className="space-y-5" onSubmit={submit}>
        <section className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium sm:col-span-2">
            Leave type
            <select
              className="mt-1.5 w-full rounded-xl border bg-background px-3 py-2.5"
              onChange={(event) => setLeaveTypeId(event.target.value)}
              required
              value={leaveTypeId}
            >
              <option value="">Choose an eligible leave type</option>
              {types.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name} · {type.is_paid ? 'Paid' : 'Unpaid'}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Start date
            <input
              className="mt-1.5 w-full rounded-xl border bg-background px-3 py-2.5"
              onChange={(event) => {
                setStartDate(event.target.value)
                if (halfDay) setEndDate(event.target.value)
              }}
              required
              type="date"
              value={startDate}
            />
          </label>
          <label className="text-sm font-medium">
            End date
            <input
              className="mt-1.5 w-full rounded-xl border bg-background px-3 py-2.5"
              disabled={halfDay}
              min={startDate}
              onChange={(event) => setEndDate(event.target.value)}
              required
              type="date"
              value={endDate}
            />
          </label>
        </section>
        {selectedType?.half_day_supported && (
          <label className="flex items-center gap-3 rounded-xl border p-3 text-sm font-medium">
            <input
              checked={halfDay}
              onChange={(event) => {
                setHalfDay(event.target.checked)
                if (event.target.checked && startDate) setEndDate(startDate)
              }}
              type="checkbox"
            />{' '}
            Request a half day
          </label>
        )}
        {preview.isFetching && (
          <p className="text-sm text-muted-foreground">
            Calculating chargeable leave days…
          </p>
        )}
        {preview.data && (
          <section
            aria-live="polite"
            className="rounded-2xl border bg-muted/35 p-4"
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <PreviewValue
                label="Calendar span"
                value={`${preview.data.calendar_span} days`}
              />
              <PreviewValue
                label="Chargeable"
                value={formatDays(Number(preview.data.chargeable_days))}
              />
              <PreviewValue
                label="Expected remaining"
                value={
                  balance
                    ? formatDays(
                        Number(balance.available_after_pending) -
                          Number(preview.data.chargeable_days),
                      )
                    : 'No entitlement'
                }
              />
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              {preview.data.excluded_non_working_days} non-working day(s) and{' '}
              {preview.data.excluded_holidays} public holiday(s) excluded by
              organization policy.
            </p>
          </section>
        )}
        {exceeds && (
          <p
            className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm font-medium text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
            role="alert"
          >
            You have{' '}
            {balance
              ? formatDays(Number(balance.available_after_pending))
              : 'no leave'}{' '}
            available, but this request requires{' '}
            {preview.data
              ? formatDays(Number(preview.data.chargeable_days))
              : 'more'}
            .
          </p>
        )}
        <label className="block text-sm font-medium">
          Reason or note
          <textarea
            className="mt-1.5 min-h-24 w-full rounded-xl border bg-background px-3 py-2.5"
            maxLength={4000}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Add context for your manager"
            value={reason}
          />
        </label>
        <label className="block rounded-xl border border-dashed p-4 text-sm font-medium">
          Supporting document{' '}
          {selectedType?.attachment_required ? (
            <span className="text-destructive">required</span>
          ) : (
            <span className="text-muted-foreground">optional</span>
          )}
          <input
            accept=".pdf,.txt,.csv,.jpg,.jpeg,.png,.webp"
            className="mt-2 block w-full text-sm"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            type="file"
          />
          {file && (
            <span className="mt-2 block text-xs text-muted-foreground">
              {file.name} · {(file.size / 1024).toFixed(0)} KB
            </span>
          )}
        </label>
        {save.error && (
          <p
            className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive"
            role="alert"
          >
            {save.error.message}
          </p>
        )}
        <footer className="flex flex-col-reverse gap-2 border-t pt-4 sm:flex-row sm:justify-end">
          <button
            className="rounded-xl border px-4 py-2.5 text-sm font-semibold"
            disabled={invalidBase || save.isPending}
            onClick={() => {
              intent.current = 'draft'
            }}
            type="submit"
          >
            Save draft
          </button>
          <button
            className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={invalidSubmit || save.isPending}
            onClick={() => {
              intent.current = 'submit'
            }}
            type="submit"
          >
            {save.isPending ? 'Saving…' : 'Submit request'}
          </button>
        </footer>
      </form>
    </Modal>
  )
}

function PreviewValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  )
}

function BalanceHistoryDialog({
  balance,
  type,
  onClose,
}: {
  balance: LeaveBalance
  type?: LeaveType
  onClose: () => void
}) {
  const history = useQuery({
    queryKey: ['leave', 'ledger', balance.entitlement_id],
    queryFn: () =>
      leaveApi.ledger({
        employee_id: balance.employee_id,
        leave_type_id: balance.leave_type_id,
        leave_period_id: balance.leave_period_id,
        page: 1,
        page_size: 50,
      }),
  })
  return (
    <Modal
      description="An immutable record of allocations, accruals, usage, reversals, adjustments, and expiry."
      onClose={onClose}
      title={`${type?.name ?? 'Leave'} history`}
    >
      {history.isLoading ? (
        <LoadingState label="Loading balance history" />
      ) : history.isError || !history.data ? (
        <ErrorState retry={() => void history.refetch()} />
      ) : history.data.items.length ? (
        <div className="space-y-2">
          {history.data.items.map((entry) => (
            <div className="flex gap-3 rounded-xl border p-3" key={entry.id}>
              <span
                className={`mt-1 size-2 shrink-0 rounded-full ${Number(entry.amount) >= 0 ? 'bg-emerald-500' : 'bg-amber-500'}`}
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap justify-between gap-2">
                  <p className="font-semibold capitalize">
                    {entry.entry_type.replaceAll('_', ' ')}
                  </p>
                  <p
                    className={`font-semibold ${Number(entry.amount) >= 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}`}
                  >
                    {Number(entry.amount) > 0 ? '+' : ''}
                    {formatDays(Number(entry.amount))}
                  </p>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {entry.reason || 'No additional note'} ·{' '}
                  {formatDay(entry.effective_date)}
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          detail="Ledger entries will appear when entitlement or usage changes."
          title="No balance history yet"
        />
      )}
    </Modal>
  )
}

export function LeaveRequestDetailPage() {
  const { requestId } = useParams({ strict: false }) as { requestId: string }
  const { user } = useAuth()
  const confirmation = useConfirmation()
  const client = useQueryClient()
  const detail = useQuery({
    queryKey: ['leave', 'request', requestId],
    queryFn: () => leaveApi.request(requestId),
  })
  const [rejectReason, setRejectReason] = useState('')
  const [rejectOpen, setRejectOpen] = useState(false)
  const mutate = useMutation({
    mutationFn: async (
      action: 'submit' | 'withdraw' | 'cancel' | 'approve' | 'reject',
    ) => {
      if (action === 'submit') return leaveApi.submit(requestId)
      if (action === 'withdraw') return leaveApi.withdraw(requestId)
      if (action === 'cancel') return leaveApi.cancel(requestId)
      if (action === 'approve') return leaveApi.approve(requestId)
      return leaveApi.reject(requestId, rejectReason)
    },
    onSuccess: async () => {
      setRejectOpen(false)
      await client.invalidateQueries({ queryKey: ['leave'] })
    },
  })
  const perform = async (
    action: 'submit' | 'withdraw' | 'cancel' | 'approve',
  ) => {
    const descriptions = {
      submit: 'This sends the request to your manager for review.',
      withdraw: 'The request will leave your manager’s approval queue.',
      cancel: 'The approved absence and its calendar event will be cancelled.',
      approve:
        'This confirms the employee’s absence and updates their calendar and balance.',
    }
    if (
      await confirmation({
        title: `${action[0]?.toUpperCase()}${action.slice(1)} leave request?`,
        description: descriptions[action],
        confirmLabel: action[0]?.toUpperCase() + action.slice(1),
        tone: action === 'cancel' ? 'danger' : 'primary',
      })
    )
      mutate.mutate(action)
  }
  if (detail.isLoading)
    return (
      <div className="p-5 sm:p-8">
        <LoadingState label="Loading leave request" />
      </div>
    )
  if (detail.isError || !detail.data)
    return (
      <div className="p-5 sm:p-8">
        <ErrorState retry={() => void detail.refetch()} />
      </div>
    )
  const item = detail.data
  const own = user?.id === item.employee_id
  const canApprove =
    user?.permissions.includes('leave.approve') && item.status === 'submitted'
  const canReject =
    user?.permissions.includes('leave.reject') && item.status === 'submitted'
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6 lg:p-8">
      <PageHeader
        actions={
          <>
            <Link
              className="rounded-xl border px-4 py-2.5 text-sm font-semibold"
              to={own ? '/leave' : '/leave/team'}
            >
              Back to leave
            </Link>
            {own && item.status === 'draft' && (
              <button
                className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
                onClick={() => void perform('submit')}
                type="button"
              >
                Submit
              </button>
            )}
            {own && item.status === 'submitted' && (
              <button
                className="rounded-xl border border-destructive px-4 py-2.5 text-sm font-semibold text-destructive"
                onClick={() => void perform('withdraw')}
                type="button"
              >
                Withdraw
              </button>
            )}
            {own && item.status === 'approved' && (
              <button
                className="rounded-xl border border-destructive px-4 py-2.5 text-sm font-semibold text-destructive"
                onClick={() => void perform('cancel')}
                type="button"
              >
                Cancel leave
              </button>
            )}
            {canReject && (
              <button
                className="rounded-xl border border-destructive px-4 py-2.5 text-sm font-semibold text-destructive"
                onClick={() => setRejectOpen(true)}
                type="button"
              >
                Reject
              </button>
            )}
            {canApprove && (
              <button
                className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
                onClick={() => void perform('approve')}
                type="button"
              >
                Approve
              </button>
            )}
          </>
        }
        description={`${formatDay(item.start_date)} – ${formatDay(item.end_date)} · ${formatDays(Number(item.duration_days))}`}
        eyebrow="Leave request"
        title={item.leave_type_name}
      />
      <div className="grid gap-5 lg:grid-cols-[1.45fr_1fr]">
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Request details</h2>
            <StatusBadge value={item.status} />
          </div>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            <Detail label="Employee" value={item.employee_name} />
            <Detail
              label="Employee number"
              value={item.employee_number || 'Not assigned'}
            />
            <Detail
              label="Department"
              value={item.department_name || 'Not assigned'}
            />
            <Detail
              label="Manager"
              value={item.manager_name || 'Not assigned'}
            />
            <Detail label="Leave period" value={item.leave_period_name} />
            <Detail
              label="Balance impact"
              value={formatDays(Number(item.balance_effect))}
            />
            <Detail label="Half day" value={item.half_day ? 'Yes' : 'No'} />
            <Detail label="Submitted" value={formatDateTime(item.created_at)} />
          </dl>
          <section className="mt-5 border-t pt-5">
            <h3 className="text-sm font-semibold">Reason</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
              {item.reason || 'No reason provided.'}
            </p>
          </section>
          {item.review_comment && (
            <section className="mt-5 rounded-xl bg-muted/45 p-4">
              <h3 className="text-sm font-semibold">Review note</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {item.review_comment}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                {item.reviewer_name ?? 'Reviewer'}
                {item.reviewed_at
                  ? ` · ${formatDateTime(item.reviewed_at)}`
                  : ''}
              </p>
            </section>
          )}
        </article>
        <div className="space-y-5">
          <article className="rounded-2xl border bg-card p-5 shadow-sm">
            <h2 className="flex items-center gap-2 font-semibold">
              <FileText className="size-4 text-primary" /> Supporting documents
            </h2>
            {item.attachments.length ? (
              <div className="mt-3 space-y-2">
                {item.attachments.map((attachment) => (
                  <AttachmentRow
                    attachment={attachment}
                    key={attachment.id}
                    requestId={item.id}
                  />
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                No supporting documents.
              </p>
            )}
          </article>
          <article className="rounded-2xl border bg-card p-5 shadow-sm">
            <h2 className="flex items-center gap-2 font-semibold">
              <History className="size-4 text-primary" /> Timeline
            </h2>
            <ol className="mt-4 space-y-4">
              {item.history.map((event) => (
                <li className="relative border-l pl-4" key={event.id}>
                  <span className="absolute -left-1.5 top-1 size-3 rounded-full border-2 border-background bg-primary" />
                  <p className="text-sm font-semibold capitalize">
                    {event.event_type.replaceAll('_', ' ')}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {formatDateTime(event.created_at)}
                  </p>
                  {event.comment && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {event.comment}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          </article>
        </div>
      </div>
      {rejectOpen && (
        <Modal
          description="A clear reason is required and will be visible to the employee."
          onClose={() => setRejectOpen(false)}
          title="Reject leave request"
        >
          <label className="text-sm font-medium">
            Reason for rejection
            <textarea
              autoFocus
              className="mt-1.5 min-h-28 w-full rounded-xl border bg-background p-3"
              onChange={(event) => setRejectReason(event.target.value)}
              value={rejectReason}
            />
          </label>
          <div className="mt-5 flex justify-end gap-2">
            <button
              className="rounded-xl border px-4 py-2 text-sm font-semibold"
              onClick={() => setRejectOpen(false)}
              type="button"
            >
              Keep reviewing
            </button>
            <button
              className="rounded-xl bg-destructive px-4 py-2 text-sm font-semibold text-destructive-foreground disabled:opacity-50"
              disabled={!rejectReason.trim() || mutate.isPending}
              onClick={() => mutate.mutate('reject')}
              type="button"
            >
              Reject request
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-semibold">{value}</dd>
    </div>
  )
}
function AttachmentRow({
  attachment,
  requestId,
}: {
  attachment: LeaveAttachment
  requestId: string
}) {
  return (
    <button
      className="flex w-full items-center gap-3 rounded-xl border p-3 text-left hover:bg-muted"
      onClick={() => void leaveApi.downloadAttachment(requestId, attachment)}
      type="button"
    >
      <FileText className="size-5 text-primary" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold">
          {attachment.filename}
        </span>
        <span className="block text-xs text-muted-foreground">
          {Math.ceil(attachment.size / 1024)} KB · Secure download
        </span>
      </span>
    </button>
  )
}
