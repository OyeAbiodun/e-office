import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { useState, type FormEvent } from 'react'
import { Plus } from 'lucide-react'
import { useAuth } from '@/features/auth/auth-store'
import { useConfirmation } from '@/components/feedback/confirmation'
import {
  financeApi,
  money,
  query,
  type Account,
  type Filters,
  type Transaction,
} from './api'
import {
  ErrorState,
  ExportButton,
  Field,
  FinanceLayout,
  Loading,
  Pager,
  Section,
  Status,
} from './shared'
import { label } from './utils'

export function FinancePage() {
  const { user } = useAuth()
  const permissions = new Set(user?.permissions)
  const [tab, setTab] = useState('accounts')
  const [create, setCreate] = useState(false)
  const [transfer, setTransfer] = useState(false)
  if (!permissions.has('finance.accounts.view'))
    return (
      <FinanceLayout title="Finance Center">
        <ErrorState
          error={
            new Error('You do not have permission to view finance accounts.')
          }
        />
      </FinanceLayout>
    )
  return (
    <FinanceLayout
      title="Finance Center"
      subtitle="A clear view of accounts, payments, and reconciled records."
      actions={
        <>
          {permissions.has('finance.transactions.manage') && (
            <button onClick={() => setTransfer(!transfer)}>
              {transfer ? 'Close transfer form' : 'Transfer funds'}
            </button>
          )}
          {permissions.has('finance.accounts.manage') && (
            <button
              className="finance-primary"
              onClick={() => setCreate(!create)}
            >
              <Plus size={16} />
              {create ? 'Close account form' : 'New account'}
            </button>
          )}
        </>
      }
    >
      {create && <AccountForm done={() => setCreate(false)} />}
      {transfer && <TransferForm done={() => setTransfer(false)} />}
      <nav aria-label="Finance sections" className="finance-tabs">
        <button
          aria-current={tab === 'accounts' ? 'page' : undefined}
          onClick={() => setTab('accounts')}
        >
          Accounts
        </button>
        {permissions.has('finance.transactions.view') && (
          <button
            aria-current={tab === 'transactions' ? 'page' : undefined}
            onClick={() => setTab('transactions')}
          >
            Transactions
          </button>
        )}
      </nav>
      {tab === 'accounts' ? <Accounts /> : <Transactions />}
    </FinanceLayout>
  )
}

function TransferForm({ done }: { done: () => void }) {
  const client = useQueryClient()
  const confirm = useConfirmation()
  const accounts = useQuery({
    queryKey: ['finance', 'accounts'],
    queryFn: financeApi.accounts,
  })
  const mutation = useMutation({
    mutationFn: financeApi.transfer,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['finance'] })
      done()
    },
  })
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const approved = await confirm({
      title: 'Post account transfer?',
      description:
        'This records an immutable debit and credit entry. Use a reversal, rather than editing it, to correct a posted transfer.',
      confirmLabel: 'Post transfer',
    })
    if (!approved) return
    const values = Object.fromEntries(new FormData(event.currentTarget))
    mutation.mutate({ ...values, idempotency_key: crypto.randomUUID() })
  }
  return (
    <Section title="Transfer between accounts">
      <form onSubmit={submit} className="grid gap-4">
        <p className="finance-callout">
          This creates a paired debit and credit entry. It cannot be edited; use
          a reversal to correct a posted transfer.
        </p>
        <div className="finance-grid">
          <Field label="From account">
            <select name="source_account_id" required defaultValue="">
              <option value="" disabled>
                Select account
              </option>
              {accounts.data
                ?.filter((a) => a.status === 'active')
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.account_name} · {a.currency}
                  </option>
                ))}
            </select>
          </Field>
          <Field label="To account">
            <select name="destination_account_id" required defaultValue="">
              <option value="" disabled>
                Select account
              </option>
              {accounts.data
                ?.filter((a) => a.status === 'active')
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.account_name} · {a.currency}
                  </option>
                ))}
            </select>
          </Field>
          <Field label="Amount">
            <input
              name="amount"
              type="number"
              required
              min="0.01"
              step="0.01"
            />
          </Field>
          <Field label="Transfer date">
            <input
              name="transaction_date"
              type="date"
              required
              defaultValue={new Date().toISOString().slice(0, 10)}
            />
          </Field>
        </div>
        <Field label="Description">
          <input
            name="description"
            required
            maxLength={2000}
            placeholder="Why are funds being moved?"
          />
        </Field>
        {mutation.error && <ErrorState error={mutation.error} />}
        <div className="finance-actions">
          <button
            className="finance-primary"
            disabled={mutation.isPending || accounts.isLoading}
          >
            {mutation.isPending ? 'Posting transfer…' : 'Post transfer'}
          </button>
          <button type="button" onClick={done}>
            Cancel
          </button>
        </div>
      </form>
    </Section>
  )
}

function Accounts() {
  const records = useQuery({
    queryKey: ['finance', 'accounts'],
    queryFn: financeApi.accounts,
  })
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(25)
  const rows =
    records.data?.filter(
      (a) =>
        (!status || a.status === status) &&
        `${a.account_name} ${a.account_code} ${a.bank_name ?? ''}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    ) ?? []
  return (
    <Section title="Accounts">
      <div className="finance-toolbar">
        <Field label="Search accounts">
          <input
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
        </Field>
        <Field label="Account status">
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </Field>
      </div>
      {records.isLoading ? (
        <Loading />
      ) : records.error ? (
        <ErrorState
          error={records.error}
          retry={() => void records.refetch()}
        />
      ) : (
        <>
          <div className="finance-table-wrap">
            <table className="finance-table finance-table-responsive">
              <thead>
                <tr>
                  {['Account', 'Code / type', 'Balance', 'Status'].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice((page - 1) * size, page * size).map((a) => (
                  <tr key={a.id}>
                    <td>
                      <Link
                        to="/finance/accounts/$accountId"
                        params={{ accountId: a.id }}
                      >
                        {a.account_name}
                      </Link>
                      <small>
                        {a.bank_name} {a.account_number_masked}
                      </small>
                    </td>
                    <td data-label="Code / type">
                      {a.account_code}
                      <small>{label(a.account_type)}</small>
                    </td>
                    <td data-label="Balance" className="number">
                      {money(a.balance, a.currency)}
                    </td>
                    <td data-label="Status">
                      <Status value={a.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!rows.length && (
            <p className="finance-empty">
              No accounts match. An authorized administrator can add an account
              above.
            </p>
          )}
          <Pager
            page={page}
            size={size}
            total={rows.length}
            totalPages={Math.max(1, Math.ceil(rows.length / size))}
            onPage={setPage}
            onSize={(n) => {
              setSize(n)
              setPage(1)
            }}
          />
        </>
      )}
    </Section>
  )
}

function AccountForm({ done }: { done: () => void }) {
  const client = useQueryClient()
  const [type, setType] = useState('bank')
  const mutation = useMutation({
    mutationFn: financeApi.createAccount,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['finance'] })
      done()
    },
  })
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    mutation.mutate(Object.fromEntries(new FormData(e.currentTarget)))
  }
  return (
    <Section title="New account">
      <form onSubmit={submit} className="grid gap-4">
        <div className="finance-grid">
          <Field label="Account name">
            <input name="account_name" required maxLength={160} />
          </Field>
          <Field label="Account code">
            <input
              name="account_code"
              required
              pattern="[A-Za-z0-9_.-]+"
              maxLength={64}
            />
          </Field>
          <Field label="Account type">
            <select
              name="account_type"
              value={type}
              onChange={(e) => setType(e.target.value)}
            >
              <option value="bank">Bank</option>
              <option value="cash">Cash</option>
            </select>
          </Field>
          <Field label="Currency">
            <input
              name="currency"
              required
              defaultValue="NGN"
              pattern="[A-Z]{3}"
              maxLength={3}
            />
          </Field>
          <Field label="Opening balance">
            <input
              type="number"
              name="opening_balance"
              required
              step="0.01"
              defaultValue="0.00"
            />
          </Field>
          {type === 'bank' && (
            <>
              <Field label="Bank name">
                <input name="bank_name" maxLength={160} />
              </Field>
              <Field label="Account number (stored masked)">
                <input
                  name="account_number"
                  autoComplete="off"
                  maxLength={64}
                />
              </Field>
            </>
          )}
        </div>
        <Field label="Description">
          <textarea name="description" maxLength={2000} />
        </Field>
        <p className="finance-callout">
          The opening balance is fixed once saved. Payments and corrections are
          recorded as ledger entries.
        </p>
        {mutation.error && <ErrorState error={mutation.error} />}
        <div className="finance-actions">
          <button className="finance-primary" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving…' : 'Create account'}
          </button>
          <button type="button" onClick={done}>
            Cancel
          </button>
        </div>
      </form>
    </Section>
  )
}

export function AccountDetailPage() {
  const { accountId } = useParams({ strict: false })
  const { user } = useAuth()
  const account = useQuery({
    queryKey: ['finance', 'account', accountId],
    queryFn: () => financeApi.account(accountId!),
  })
  const [tab, setTab] = useState('transactions')
  if (account.isLoading)
    return (
      <FinanceLayout title="Account">
        <Loading />
      </FinanceLayout>
    )
  if (!account.data)
    return (
      <FinanceLayout title="Account">
        <ErrorState
          error={account.error}
          retry={() => void account.refetch()}
        />
      </FinanceLayout>
    )
  const a = account.data
  return (
    <FinanceLayout
      title={a.account_name}
      subtitle={`${a.account_code} · ${label(a.account_type)} · ${a.currency}`}
      actions={
        <>
          <Link to="/finance" className="finance-button">
            Finance Center
          </Link>
          <Status value={a.status} />
        </>
      }
    >
      <dl className="finance-totals">
        <div>
          <dt>Current balance</dt>
          <dd>{money(a.balance, a.currency)}</dd>
        </div>
        <div>
          <dt>Opening balance</dt>
          <dd>{money(a.opening_balance, a.currency)}</dd>
        </div>
        <div>
          <dt>Bank</dt>
          <dd>{a.bank_name ?? 'Cash account'}</dd>
        </div>
        <div>
          <dt>Account</dt>
          <dd>{a.account_number_masked ?? '—'}</dd>
        </div>
      </dl>
      {a.description && <p>{a.description}</p>}
      {user?.permissions.includes('finance.transactions.view') && (
        <>
          <nav aria-label="Account views" className="finance-tabs">
            {['transactions', 'statement'].map((t) => (
              <button
                key={t}
                aria-current={tab === t ? 'page' : undefined}
                onClick={() => setTab(t)}
              >
                {label(t)}
              </button>
            ))}
          </nav>
          {tab === 'transactions' ? (
            <Transactions accountId={a.id} />
          ) : (
            <StatementPanel account={a} />
          )}
        </>
      )}
    </FinanceLayout>
  )
}

export function Transactions({ accountId }: { accountId?: string }) {
  const { user } = useAuth()
  const client = useQueryClient()
  const confirm = useConfirmation()
  const [filters, setFilters] = useState<Filters>({ page: 1, page_size: 25 })
  const [selected, setSelected] = useState<Transaction | null>(null)
  const [mode, setMode] = useState('')
  const [key, setKey] = useState(() => crypto.randomUUID())
  const set = (name: string, value: string | number | boolean | undefined) =>
    setFilters((f) => ({
      ...f,
      [name]: value,
      ...(name === 'page' ? {} : { page: 1 }),
    }))
  const allFilters = { ...filters, account_id: accountId ?? filters.account_id }
  const records = useQuery({
    queryKey: ['finance', 'transactions', allFilters],
    queryFn: () => financeApi.transactions(allFilters),
  })
  const accounts = useQuery({
    queryKey: ['finance', 'accounts'],
    queryFn: financeApi.accounts,
    enabled:
      !accountId && !!user?.permissions.includes('finance.accounts.view'),
  })
  const mutation = useMutation({
    mutationFn: async (body: { reference: string; note: string }) =>
      mode === 'reverse'
        ? financeApi.reverse(selected!.id, body.note, key)
        : financeApi.reconcile(selected!.id, body.reference, body.note),
    onSuccess: async () => {
      setSelected(null)
      setKey(crypto.randomUUID())
      await client.invalidateQueries({ queryKey: ['finance'] })
      await client.invalidateQueries({ queryKey: ['voucher'] })
    },
  })
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    if (
      await confirm({
        title:
          mode === 'reverse'
            ? 'Reverse transaction?'
            : 'Reconcile transaction?',
        description:
          mode === 'reverse'
            ? 'An equal opposite entry will be recorded and linked to the original. Voucher payment totals will be recalculated.'
            : 'Confirm this transaction matches your bank or cash records.',
        confirmLabel: label(mode),
      })
    )
      mutation.mutate({
        reference: String(f.get('reference') ?? ''),
        note: String(f.get('note') ?? ''),
      })
  }
  return (
    <Section
      title="Transactions"
      actions={
        user?.permissions.includes('finance.export') && (
          <ExportButton
            path={`/finance/transactions/export${query(allFilters)}`}
            filename="transactions.csv"
          >
            Export CSV
          </ExportButton>
        )
      }
    >
      <div className="finance-filters">
        <Field label="Search transactions">
          <input
            type="search"
            value={String(filters.search ?? '')}
            onChange={(e) => set('search', e.target.value)}
          />
        </Field>
        {!accountId && (
          <Field label="Account">
            <select
              value={String(filters.account_id ?? '')}
              onChange={(e) => set('account_id', e.target.value)}
            >
              <option value="">All accounts</option>
              {accounts.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.account_name}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Reconciliation">
          <select
            value={
              filters.reconciled === undefined ? '' : String(filters.reconciled)
            }
            onChange={(e) =>
              set(
                'reconciled',
                e.target.value === '' ? undefined : e.target.value === 'true',
              )
            }
          >
            <option value="">All entries</option>
            <option value="true">Reconciled</option>
            <option value="false">Unreconciled</option>
          </select>
        </Field>
        <Field label="From date">
          <input
            type="date"
            onChange={(e) => set('from_date', e.target.value)}
          />
        </Field>
        <Field label="Through date">
          <input type="date" onChange={(e) => set('to_date', e.target.value)} />
        </Field>
      </div>
      {selected && (
        <form
          onSubmit={(e) => void submit(e)}
          className="finance-callout mt-4 grid gap-3"
        >
          <strong>
            {label(mode)} · {selected.reference}
          </strong>
          {mode === 'reconcile' && (
            <Field label="Reconciliation reference">
              <input name="reference" required maxLength={160} />
            </Field>
          )}
          <Field
            label={
              mode === 'reverse' ? 'Reason for reversal' : 'Reconciliation note'
            }
          >
            <textarea
              name="note"
              required={mode === 'reverse'}
              maxLength={2000}
            />
          </Field>
          <div className="finance-actions">
            <button disabled={mutation.isPending}>
              {mutation.isPending ? 'Processing…' : `Confirm ${mode}`}
            </button>
            <button type="button" onClick={() => setSelected(null)}>
              Cancel
            </button>
          </div>
          {mutation.error && <ErrorState error={mutation.error} />}
        </form>
      )}
      {records.isLoading ? (
        <Loading />
      ) : records.error ? (
        <ErrorState
          error={records.error}
          retry={() => void records.refetch()}
        />
      ) : (
        <>
          <div className="finance-table-wrap">
            <table className="finance-table finance-table-responsive">
              <thead>
                <tr>
                  {[
                    'Reference / account',
                    'Date',
                    'Type / source',
                    'Amount',
                    'Reconciliation',
                    'Actions',
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {records.data?.items.map((t) => (
                  <tr key={t.id}>
                    <td>
                      {t.reference}
                      <small>{t.account_name}</small>
                    </td>
                    <td data-label="Date">{t.transaction_date}</td>
                    <td data-label="Source">
                      {label(t.transaction_type)}
                      {t.voucher_id && (
                        <small>
                          <Link
                            to="/vouchers/$voucherId"
                            params={{ voucherId: t.voucher_id }}
                          >
                            {t.voucher_number ?? 'Voucher'}
                          </Link>
                        </small>
                      )}
                    </td>
                    <td className="number" data-label={label(t.direction)}>
                      {money(t.amount, t.currency)}
                    </td>
                    <td data-label="Reconciliation">
                      {t.reconciled ? 'Reconciled' : 'Unreconciled'}
                      <small>{t.reconciliation_reference}</small>
                    </td>
                    <td data-label="Actions">
                      <div className="finance-actions">
                        {!t.reconciled &&
                          user?.permissions.includes('finance.reconcile') && (
                            <button
                              onClick={() => {
                                setSelected(t)
                                setMode('reconcile')
                              }}
                            >
                              Reconcile
                            </button>
                          )}
                        {!t.reversal_of_id &&
                          user?.permissions.includes('finance.reverse') && (
                            <button
                              onClick={() => {
                                setSelected(t)
                                setMode('reverse')
                              }}
                            >
                              Reverse
                            </button>
                          )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!records.data?.items.length && (
            <p className="finance-empty">No transactions in this view.</p>
          )}
          {records.data && (
            <Pager
              page={records.data.page}
              size={records.data.page_size}
              total={records.data.total}
              totalPages={records.data.total_pages}
              onPage={(n) => set('page', n)}
              onSize={(n) => set('page_size', n)}
            />
          )}
        </>
      )}
    </Section>
  )
}

export function StatementPanel({ account }: { account: Account }) {
  const { user } = useAuth()
  const today = new Date().toISOString().slice(0, 10)
  const [dates, setDates] = useState({
    from_date: `${today.slice(0, 7)}-01`,
    to_date: today,
  })
  const records = useQuery({
    queryKey: ['finance', 'statement', account.id, dates],
    queryFn: () => financeApi.statement(account.id, dates),
    enabled: !!dates.from_date && !!dates.to_date,
  })
  const s = records.data
  return (
    <Section
      title="Account statement"
      actions={
        user?.permissions.includes('finance.export') && (
          <>
            <ExportButton
              path={`/finance/accounts/${account.id}/statement/export${query({ ...dates, format: 'csv' })}`}
              filename="statement.csv"
            >
              CSV
            </ExportButton>
            <ExportButton
              path={`/finance/accounts/${account.id}/statement/export${query({ ...dates, format: 'pdf' })}`}
              filename="statement.pdf"
            >
              Statement PDF
            </ExportButton>
          </>
        )
      }
    >
      <div className="finance-toolbar">
        <Field label="Statement start date">
          <input
            type="date"
            required
            value={dates.from_date}
            onChange={(e) => setDates({ ...dates, from_date: e.target.value })}
          />
        </Field>
        <Field label="Statement end date">
          <input
            type="date"
            required
            value={dates.to_date}
            onChange={(e) => setDates({ ...dates, to_date: e.target.value })}
          />
        </Field>
      </div>
      {records.isLoading ? (
        <Loading />
      ) : records.error ? (
        <ErrorState
          error={records.error}
          retry={() => void records.refetch()}
        />
      ) : (
        s && (
          <>
            <dl className="finance-totals mt-5">
              {(
                [
                  'opening_balance',
                  'credits',
                  'debits',
                  'closing_balance',
                ] as const
              ).map((k) => (
                <div key={k}>
                  <dt>{label(k)}</dt>
                  <dd>{money(s[k], account.currency)}</dd>
                </div>
              ))}
            </dl>
            <div className="finance-table-wrap">
              <table className="finance-table finance-table-responsive">
                <thead>
                  <tr>
                    {[
                      'Date / reference',
                      'Description',
                      'Credit',
                      'Debit',
                      'Running balance',
                    ].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {s.transactions.map((t) => (
                    <tr key={t.id}>
                      <td>
                        {t.transaction_date}
                        <small>{t.reference}</small>
                      </td>
                      <td data-label="Description">{t.description}</td>
                      <td className="number" data-label="Credit">
                        {t.direction === 'credit'
                          ? money(t.amount, account.currency)
                          : '—'}
                      </td>
                      <td className="number" data-label="Debit">
                        {t.direction === 'debit'
                          ? money(t.amount, account.currency)
                          : '—'}
                      </td>
                      <td className="number" data-label="Balance">
                        {money(t.running_balance ?? '0', account.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!s.transactions.length && (
              <p className="finance-empty">
                No transactions during this period. The opening balance carries
                forward unchanged.
              </p>
            )}
          </>
        )
      )}
    </Section>
  )
}
