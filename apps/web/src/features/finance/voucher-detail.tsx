import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { useState, type FormEvent } from 'react'
import { useAuth } from '@/features/auth/auth-store'
import { useConfirmation } from '@/components/feedback/confirmation'
import { financeApi, money, subtractMoney, type VoucherDetail } from './api'
import {
  ErrorState,
  ExportButton,
  Field,
  FinanceLayout,
  Loading,
  Section,
  Status,
} from './shared'
import { label } from './utils'

export function VoucherDetailPage() {
  const { voucherId } = useParams({ strict: false })
  const client = useQueryClient()
  const { user } = useAuth()
  const detail = useQuery({
    queryKey: ['voucher', voucherId],
    queryFn: () => financeApi.detail(voucherId!),
  })
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ['voucher', voucherId] })
    await client.invalidateQueries({ queryKey: ['vouchers'] })
    await client.invalidateQueries({ queryKey: ['finance'] })
    await client.invalidateQueries({ queryKey: ['voucher-summary'] })
  }
  if (detail.isLoading)
    return (
      <FinanceLayout title="Voucher">
        <Loading />
      </FinanceLayout>
    )
  if (!detail.data)
    return (
      <FinanceLayout title="Voucher">
        <ErrorState error={detail.error} retry={() => void detail.refetch()} />
        <Link to="/vouchers">Back to vouchers</Link>
      </FinanceLayout>
    )
  const d = detail.data,
    v = d.voucher
  return (
    <FinanceLayout
      title={v.voucher_number}
      subtitle={v.title}
      actions={
        <>
          <Link className="finance-button" to="/vouchers">
            All vouchers
          </Link>
          {user?.permissions.includes('vouchers.export') && (
            <ExportButton
              path={`/vouchers/${v.id}/pdf`}
              filename={`${v.voucher_number}.pdf`}
            >
              Voucher PDF
            </ExportButton>
          )}
          {d.allowed_actions.includes('edit') && (
            <Link
              className="finance-button"
              to="/vouchers/$voucherId/edit"
              params={{ voucherId: v.id }}
            >
              Edit draft
            </Link>
          )}
          <Status value={v.status} />
        </>
      }
    >
      <dl className="finance-totals">
        {(
          [
            ['Requested', v.requested_amount],
            ['Approved', v.approved_amount],
            ['Disbursed', v.disbursed_amount],
            ['Outstanding', v.outstanding_amount],
          ] as const
        ).map(([name, value]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>{money(value, v.currency)}</dd>
          </div>
        ))}
      </dl>
      <VoucherActions detail={d} refresh={refresh} />
      <div className="finance-grid">
        <Section title="Request details">
          <dl className="grid gap-3 text-sm">
            <div>
              <dt className="text-muted-foreground">Requester</dt>
              <dd>{v.requester_name}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Department</dt>
              <dd>{v.department_name ?? 'Not assigned'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Purpose</dt>
              <dd className="whitespace-pre-wrap">
                {v.description || v.title}
              </dd>
            </div>
            {v.meeting_id && (
              <div>
                <dt className="text-muted-foreground">Related meeting</dt>
                <dd>
                  <Link
                    className="text-primary"
                    to="/meetings/$meetingId"
                    params={{ meetingId: v.meeting_id }}
                  >
                    {v.meeting_title ?? 'Open meeting'}
                  </Link>
                </dd>
              </div>
            )}
            {v.task_id && (
              <div>
                <dt className="text-muted-foreground">Related task</dt>
                <dd>
                  <Link
                    className="text-primary"
                    to="/tasks/$taskId"
                    params={{ taskId: v.task_id }}
                  >
                    {v.task_title ?? 'Open task'}
                  </Link>
                </dd>
              </div>
            )}
          </dl>
        </Section>
        <Documents detail={d} refresh={refresh} />
      </div>
      <Section title="Line items">
        <div className="finance-table-wrap">
          <table className="finance-table finance-table-responsive">
            <thead>
              <tr>
                {['Description', 'Quantity', 'Unit price', 'Tax', 'Amount'].map(
                  (v) => (
                    <th key={v}>{v}</th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {d.line_items.map((line, i) => (
                <tr key={i}>
                  <td>{line.description}</td>
                  <td data-label="Quantity">{line.quantity}</td>
                  <td data-label="Unit price" className="number">
                    {money(line.unit_price, v.currency)}
                  </td>
                  <td data-label="Tax" className="number">
                    {money(line.tax_amount, v.currency)}
                  </td>
                  <td data-label="Amount" className="number">
                    {money(line.amount ?? '0', v.currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <div className="finance-grid">
        <Section title="Review history">
          {d.reviews.length ? (
            <ul className="finance-history">
              {d.reviews.map((r) => (
                <li key={r.id}>
                  <Status value={r.decision} />
                  <p className="mt-2">
                    {r.actor_name}
                    {r.approved_amount &&
                      ` · ${money(r.approved_amount, v.currency)}`}
                  </p>
                  {r.comment && (
                    <p className="whitespace-pre-wrap">{r.comment}</p>
                  )}
                  <small>{new Date(r.created_at).toLocaleString()}</small>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No review yet.</p>
          )}
        </Section>
        <Section title="Payment history">
          {d.disbursements.length ? (
            <ul className="finance-history">
              {d.disbursements.map((p) => (
                <li key={p.id}>
                  <strong>{money(p.amount, v.currency)}</strong>
                  <p>
                    {p.payment_reference ?? 'No payment reference'} ·{' '}
                    {label(p.payment_method)}
                  </p>
                  <small>
                    {p.actor_name} · {p.payment_date}
                  </small>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              No payment recorded.
            </p>
          )}
        </Section>
      </div>
      {d.transactions.length > 0 && (
        <Section title="Ledger & reconciliation">
          <div className="finance-table-wrap">
            <table className="finance-table finance-table-responsive">
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Date</th>
                  <th>Entry</th>
                  <th>Amount</th>
                  <th>Reconciliation</th>
                </tr>
              </thead>
              <tbody>
                {d.transactions.map((t) => (
                  <tr key={t.id}>
                    <td>
                      {t.reference}
                      {t.reversal_of_id && <small>Reversal entry</small>}
                    </td>
                    <td data-label="Date">{t.transaction_date}</td>
                    <td data-label="Entry">{label(t.direction)}</td>
                    <td data-label="Amount">{money(t.amount, t.currency)}</td>
                    <td data-label="Reconciliation">
                      {t.reconciled
                        ? t.reconciliation_reference
                        : 'Unreconciled'}
                      {t.reconciliation_note && (
                        <small>{t.reconciliation_note}</small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
      <div className="finance-grid">
        <Comments detail={d} refresh={refresh} />
        <Section title="Lifecycle">
          <ol className="finance-history">
            {d.history.map((h) => (
              <li key={h.id}>
                <strong>{label(h.event_type)}</strong>
                <p>{h.reason}</p>
                <small>
                  {h.actor_name} · {new Date(h.created_at).toLocaleString()}
                </small>
              </li>
            ))}
          </ol>
        </Section>
      </div>
    </FinanceLayout>
  )
}
function VoucherActions({
  detail: d,
  refresh,
}: {
  detail: VoucherDetail
  refresh: () => Promise<void>
}) {
  const [mode, setMode] = useState('')
  const [amount, setAmount] = useState(d.voucher.outstanding_amount)
  const [paymentKey, setPaymentKey] = useState(() => crypto.randomUUID())
  const confirm = useConfirmation()
  const accounts = useQuery({
    queryKey: ['finance', 'accounts'],
    queryFn: financeApi.accounts,
    enabled: d.allowed_actions.includes('disburse'),
  })
  const mutation = useMutation({
    mutationFn: ({
      action,
      body,
    }: {
      action: string
      body: Record<string, unknown>
    }) => financeApi.action(d.voucher.id, action, body),
    onSuccess: async () => {
      setMode('')
      setPaymentKey(crypto.randomUUID())
      await refresh()
    },
  })
  const act = async (action: string, body: Record<string, unknown>) => {
    if (
      await confirm({
        title: `${label(action)} voucher?`,
        description:
          action === 'disburse'
            ? `Record ${money(String(body.amount), d.voucher.currency)} against this voucher and its finance account. Check the payment reference before confirming.`
            : `This will ${action} ${d.voucher.voucher_number}. The decision is recorded in its history.`,
        confirmLabel: label(action),
      })
    )
      mutation.mutate({ action, body })
  }
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    const body: Record<string, unknown> = Object.fromEntries(f)
    if (mode === 'disburse') body.idempotency_key = paymentKey
    void act(mode, body)
  }
  const actions = d.allowed_actions.filter((a) =>
    ['submit', 'approve', 'return', 'reject', 'disburse'].includes(a),
  )
  if (!actions.length) return null
  return (
    <Section title="Next action">
      <div className="finance-actions">
        {actions.map((a) => (
          <button
            type="button"
            key={a}
            disabled={mutation.isPending}
            className={
              a === 'approve' || a === 'submit' || a === 'disburse'
                ? 'finance-primary'
                : ''
            }
            onClick={() => (a === 'submit' ? void act(a, {}) : setMode(a))}
          >
            {label(a)}
          </button>
        ))}
      </div>
      {mode && (
        <form className="mt-5 grid gap-4" onSubmit={submit}>
          <h3 className="font-semibold">{label(mode)} voucher</h3>
          {mode === 'approve' && (
            <Field label="Approved amount">
              <input
                name="approved_amount"
                type="number"
                required
                min="0.01"
                max={d.voucher.requested_amount}
                step="0.01"
                defaultValue={d.voucher.requested_amount}
              />
            </Field>
          )}
          {mode !== 'disburse' ? (
            <Field
              label={
                mode === 'approve'
                  ? 'Review comment (optional)'
                  : 'Reason (required)'
              }
            >
              <textarea
                name="comment"
                required={mode !== 'approve'}
                maxLength={10000}
              />
            </Field>
          ) : (
            <>
              <div className="finance-callout">
                Approved {money(d.voucher.approved_amount, d.voucher.currency)}{' '}
                · Previously paid{' '}
                {money(d.voucher.disbursed_amount, d.voucher.currency)} ·
                Outstanding{' '}
                {money(d.voucher.outstanding_amount, d.voucher.currency)}
              </div>
              {accounts.error && <ErrorState error={accounts.error} />}
              <div className="finance-grid">
                <Field label="Pay from account">
                  <select name="account_id" required>
                    <option value="">Select an account</option>
                    {accounts.data
                      ?.filter(
                        (a) =>
                          a.status === 'active' &&
                          a.currency === d.voucher.currency,
                      )
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.account_name} · {money(a.balance, a.currency)}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label="Current payment amount">
                  <input
                    name="amount"
                    required
                    type="number"
                    min="0.01"
                    max={d.voucher.outstanding_amount}
                    step="0.01"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                  />
                </Field>
                <Field label="Payment method">
                  <select name="payment_method">
                    <option value="bank_transfer">Bank transfer</option>
                    <option value="cash">Cash</option>
                    <option value="cheque">Cheque</option>
                  </select>
                </Field>
                <Field label="Payment reference">
                  <input name="payment_reference" required maxLength={160} />
                </Field>
                <Field label="Payment date">
                  <input
                    type="date"
                    name="payment_date"
                    required
                    defaultValue={new Date().toISOString().slice(0, 10)}
                  />
                </Field>
                <Field label="Beneficiary">
                  <input
                    name="beneficiary"
                    defaultValue={d.voucher.requester_name ?? ''}
                    maxLength={240}
                  />
                </Field>
              </div>
              <Field label="Payment note">
                <textarea name="note" maxLength={10000} />
              </Field>
              <p className="text-sm">
                Outstanding after payment:{' '}
                <strong>
                  {money(
                    subtractMoney(d.voucher.outstanding_amount, amount || '0'),
                    d.voucher.currency,
                  )}
                </strong>
              </p>
            </>
          )}
          <div className="finance-actions">
            <button className="finance-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Processing…' : `Review and ${mode}`}
            </button>
            <button type="button" onClick={() => setMode('')}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {mutation.error && (
        <div className="mt-4">
          <ErrorState error={mutation.error} />
        </div>
      )}
    </Section>
  )
}
function Documents({
  detail: d,
  refresh,
}: {
  detail: VoucherDetail
  refresh: () => Promise<void>
}) {
  const confirm = useConfirmation()
  const upload = useMutation({
    mutationFn: (file: File) => financeApi.upload(d.voucher.id, file),
    onSuccess: refresh,
  })
  const remove = useMutation({
    mutationFn: (id: string) => financeApi.removeAttachment(d.voucher.id, id),
    onSuccess: refresh,
  })
  return (
    <Section title="Supporting documents">
      {d.attachments.map((a) => (
        <div className="finance-document" key={a.id}>
          <div>
            <p>{a.filename}</p>
            <small>
              {Math.ceil(a.size / 1024)} KB · {a.actor_name} ·{' '}
              {new Date(a.created_at).toLocaleDateString()}
            </small>
          </div>
          <div className="finance-actions">
            <ExportButton
              path={a.url.replace('/api/v1', '')}
              filename={a.filename}
            >
              Download
            </ExportButton>
            {d.allowed_actions.includes('edit') && (
              <button
                type="button"
                disabled={remove.isPending}
                onClick={async () => {
                  if (
                    await confirm({
                      title: 'Remove document?',
                      description:
                        'The document will be removed from this draft. Its history remains available.',
                      confirmLabel: 'Remove',
                    })
                  )
                    remove.mutate(a.id)
                }}
              >
                Remove
              </button>
            )}
          </div>
        </div>
      ))}
      {!d.attachments.length && (
        <p className="text-sm text-muted-foreground">
          No supporting documents attached.
        </p>
      )}
      {d.allowed_actions.includes('edit') && (
        <div className="mt-5">
          <Field label="Upload receipt or document (up to 25 MB)">
            <input
              type="file"
              disabled={upload.isPending}
              accept=".pdf,.png,.jpg,.jpeg,.txt,.csv"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) upload.mutate(f)
                e.target.value = ''
              }}
            />
          </Field>
          {upload.isPending && <p role="status">Uploading…</p>}
        </div>
      )}
      {(upload.error || remove.error) && (
        <ErrorState error={upload.error || remove.error} />
      )}
    </Section>
  )
}
function Comments({
  detail: d,
  refresh,
}: {
  detail: VoucherDetail
  refresh: () => Promise<void>
}) {
  const [body, setBody] = useState('')
  const mutation = useMutation({
    mutationFn: () => financeApi.comment(d.voucher.id, body),
    onSuccess: async () => {
      setBody('')
      await refresh()
    },
  })
  return (
    <Section title="Comments">
      {d.comments.map((c) => (
        <article className="border-b border-border py-3 text-sm" key={c.id}>
          <strong>{c.actor_name}</strong>
          <p className="whitespace-pre-wrap my-2">{c.body}</p>
          <small className="text-muted-foreground">
            {new Date(c.created_at).toLocaleString()}
          </small>
        </article>
      ))}
      {!d.comments.length && (
        <p className="text-sm text-muted-foreground">No comments yet.</p>
      )}
      {d.allowed_actions.includes('comment') && (
        <form
          className="mt-4 grid gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            mutation.mutate()
          }}
        >
          <Field label="Add a comment">
            <textarea
              required
              maxLength={20000}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </Field>
          <button disabled={mutation.isPending || !body.trim()}>
            {mutation.isPending ? 'Adding…' : 'Add comment'}
          </button>
        </form>
      )}
      {mutation.error && <ErrorState error={mutation.error} />}
    </Section>
  )
}
