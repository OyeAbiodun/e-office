import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Download,
  Eye,
  Plus,
  RotateCcw,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { useConfirmation } from '@/components/feedback/confirmation'
import { useAuth } from '@/features/auth/auth-store'
import { financeApi } from '@/features/finance/api'
import {
  ErrorState,
  Field,
  FinanceLayout,
  Loading,
  Pager,
  Section,
  Status,
} from '@/features/finance/shared'
import {
  downloadPayroll,
  payrollApi,
  payrollMoney,
  type SalaryComponent,
} from './api'

type Tab =
  | 'overview'
  | 'runs'
  | 'payslips'
  | 'structures'
  | 'components'
  | 'statutory'
  | 'loans'
  | 'reports'
const today = new Date().toISOString().slice(0, 10)
const input = (form: HTMLFormElement) => Object.fromEntries(new FormData(form))
const componentInput = (form: HTMLFormElement) => {
  const values = input(form)
  const checked = (name: string) =>
    (form.elements.namedItem(name) as HTMLInputElement | null)?.checked ?? false
  return {
    ...values,
    description: values.description || null,
    effective_end: values.effective_end || null,
    taxable: checked('taxable'),
    pensionable: checked('pensionable'),
    recurring: checked('recurring'),
    is_active: checked('is_active'),
  }
}

export function PayrollPage() {
  const { user } = useAuth()
  const permissions = useMemo(() => new Set(user?.permissions ?? []), [user])
  const [tab, setTab] = useState<Tab>('overview')
  const tabs: Array<[Tab, string, string]> = [
    ['overview', 'Overview', ''],
    ['runs', 'Payroll runs', 'payroll.periods.view'],
    ['payslips', 'My payslips', 'payroll.view_own'],
    ['structures', 'Salary structures', 'payroll.salary_structure.view'],
    ['components', 'Components', 'payroll.salary_structure.view'],
    ['statutory', 'Statutory rules', 'payroll.salary_structure.view'],
    ['loans', 'Loans', 'payroll.loans.manage'],
    ['reports', 'Reports', 'payroll.reports.view'],
  ]
  if (!tabs.some(([, , permission]) => permissions.has(permission)))
    return (
      <FinanceLayout title="Payroll">
        <ErrorState
          error={new Error('You do not have permission to access payroll.')}
        />
      </FinanceLayout>
    )
  return (
    <FinanceLayout
      title="Payroll"
      subtitle="Secure salary processing, statutory deductions, approvals, payments, and payslips."
      actions={
        <span className="finance-callout">
          <ShieldCheck size={16} /> Salary data is permission restricted
        </span>
      }
    >
      <nav aria-label="Payroll sections" className="finance-tabs">
        {tabs
          .filter(
            ([key, , permission]) =>
              key === 'overview' || permissions.has(permission),
          )
          .map(([key, label]) => (
            <button
              key={key}
              aria-selected={tab === key}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
      </nav>
      {tab === 'overview' && <PayrollOverview permissions={permissions} />}
      {tab === 'runs' && <Runs permissions={permissions} />}
      {tab === 'payslips' && <Payslips />}
      {tab === 'structures' && (
        <Structures
          canManage={permissions.has('payroll.salary_structure.manage')}
        />
      )}
      {tab === 'components' && (
        <Components canManage={permissions.has('payroll.components.manage')} />
      )}
      {tab === 'statutory' && (
        <Statutory canManage={permissions.has('payroll.statutory.manage')} />
      )}
      {tab === 'loans' && <Loans />}
      {tab === 'reports' && <Reports />}
    </FinanceLayout>
  )
}

function PayrollOverview({ permissions }: { permissions: Set<string> }) {
  const canViewPeriods = permissions.has('payroll.periods.view')
  const canViewOwn = permissions.has('payroll.view_own')
  const periods = useQuery({
    queryKey: ['payroll', 'periods'],
    queryFn: payrollApi.periods,
    enabled: canViewPeriods,
  })
  const runs = useQuery({
    queryKey: ['payroll', 'runs'],
    queryFn: payrollApi.runs,
    enabled: canViewPeriods,
  })
  const payslips = useQuery({
    queryKey: ['payroll', 'payslips'],
    queryFn: payrollApi.payslips,
    enabled: canViewOwn,
  })
  const error = periods.error ?? runs.error ?? payslips.error
  if (periods.isLoading || runs.isLoading || payslips.isLoading)
    return <Loading />
  if (error)
    return (
      <ErrorState
        error={error}
        retry={() =>
          void Promise.all([
            periods.refetch(),
            runs.refetch(),
            payslips.refetch(),
          ])
        }
      />
    )
  const runRows = runs.data ?? []
  const latestRun = runRows[0]
  const pendingReview = runRows.filter(
    (row) => row.status === 'under_review',
  ).length
  const awaitingPayment = runRows.filter(
    (row) => row.status === 'approved',
  ).length
  const completed = runRows.filter((row) =>
    ['paid', 'closed'].includes(row.status),
  ).length
  const latestPayslip = payslips.data?.[0]
  return (
    <Section title="Payroll overview">
      <div className="finance-summary" aria-label="Live payroll summary">
        {canViewPeriods && (
          <>
            <Metric
              label="Payroll periods"
              value={String(periods.data?.length ?? 0)}
            />
            <Metric label="Pending review" value={String(pendingReview)} />
            <Metric label="Awaiting payment" value={String(awaitingPayment)} />
            <Metric label="Paid or closed" value={String(completed)} />
          </>
        )}
        {canViewOwn && (
          <Metric
            label="Available payslips"
            value={String(payslips.data?.length ?? 0)}
          />
        )}
      </div>
      <div className="finance-grid">
        {canViewPeriods && (
          <article className="finance-card">
            <h3>Current processing state</h3>
            {latestRun ? (
              <>
                <Status value={latestRun.status} />
                <p className="text-muted-foreground">
                  Version {latestRun.version}. Review exceptions before any
                  controlled approval or payment transition.
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">
                No payroll run has been prepared yet.
              </p>
            )}
          </article>
        )}
        {canViewOwn && (
          <article className="finance-card">
            <h3>Latest payslip</h3>
            {latestPayslip ? (
              <>
                <strong>
                  {payrollMoney(latestPayslip.net_pay, latestPayslip.currency)}
                </strong>
                <p className="text-muted-foreground">
                  {latestPayslip.period_name ?? 'Latest paid payroll period'}
                </p>
                <button
                  onClick={() =>
                    void downloadPayroll(
                      `/payroll/results/${latestPayslip.id}/payslip`,
                      'payslip.pdf',
                    )
                  }
                >
                  <Download size={16} /> Download secure PDF
                </button>
              </>
            ) : (
              <p className="text-muted-foreground">
                No paid payslip is available yet.
              </p>
            )}
          </article>
        )}
      </div>
    </Section>
  )
}

function Runs({ permissions }: { permissions: Set<string> }) {
  const client = useQueryClient()
  const [create, setCreate] = useState(false)
  const [selected, setSelected] = useState<string>()
  const periods = useQuery({
    queryKey: ['payroll', 'periods'],
    queryFn: payrollApi.periods,
  })
  const runs = useQuery({
    queryKey: ['payroll', 'runs'],
    queryFn: payrollApi.runs,
  })
  const createPeriod = useMutation({
    mutationFn: payrollApi.createPeriod,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll', 'periods'] })
      setCreate(false)
    },
  })
  const prepare = useMutation({
    mutationFn: payrollApi.prepare,
    onSuccess: async (run) => {
      await client.invalidateQueries({ queryKey: ['payroll'] })
      setSelected(run.id)
    },
  })
  if (periods.isLoading || runs.isLoading) return <Loading />
  if (periods.error || runs.error)
    return (
      <ErrorState
        error={periods.error ?? runs.error}
        retry={() => void Promise.all([periods.refetch(), runs.refetch()])}
      />
    )
  const runByPeriod = new Map(
    (runs.data ?? []).map((run) => [run.period_id, run]),
  )
  return (
    <>
      <Section
        title="Payroll periods"
        actions={
          permissions.has('payroll.periods.manage') ? (
            <button
              className="finance-primary"
              onClick={() => setCreate(!create)}
            >
              <Plus size={16} />
              {create ? 'Close' : 'New period'}
            </button>
          ) : undefined
        }
      >
        {create && (
          <form
            className="finance-filters"
            onSubmit={(event) => {
              event.preventDefault()
              createPeriod.mutate(input(event.currentTarget))
            }}
          >
            <Field label="Period name">
              <input name="name" required placeholder="September 2026" />
            </Field>
            <Field label="Start date">
              <input name="start_date" type="date" required />
            </Field>
            <Field label="End date">
              <input name="end_date" type="date" required />
            </Field>
            <Field label="Payment date">
              <input name="payment_date" type="date" required />
            </Field>
            <Field label="Currency">
              <input
                name="currency"
                defaultValue="NGN"
                pattern="[A-Z]{3}"
                required
              />
            </Field>
            <button
              className="finance-primary"
              disabled={createPeriod.isPending}
            >
              Create period
            </button>
          </form>
        )}
        {(createPeriod.error || prepare.error) && (
          <ErrorState error={createPeriod.error ?? prepare.error} />
        )}
        <div className="finance-table-wrap">
          <table className="finance-table finance-table-responsive">
            <thead>
              <tr>
                <th>Period</th>
                <th>Dates</th>
                <th>Payment</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {(periods.data ?? []).map((period) => {
                const run = runByPeriod.get(period.id)
                return (
                  <tr key={period.id}>
                    <td data-label="Period">
                      {period.name}
                      <small>{period.currency}</small>
                    </td>
                    <td data-label="Dates">
                      {period.start_date} – {period.end_date}
                    </td>
                    <td data-label="Payment">{period.payment_date}</td>
                    <td data-label="Status">
                      <Status value={run?.status ?? period.status} />
                    </td>
                    <td data-label="Action">
                      {run ? (
                        <button onClick={() => setSelected(run.id)}>
                          Open run
                        </button>
                      ) : permissions.has('payroll.prepare') ? (
                        <button
                          disabled={prepare.isPending}
                          onClick={() => prepare.mutate(period.id)}
                        >
                          Prepare payroll
                        </button>
                      ) : (
                        'Awaiting preparation'
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {(periods.data ?? []).length === 0 && (
          <p className="finance-empty">
            No payroll periods yet. Create the first period when payroll is
            ready to process.
          </p>
        )}
      </Section>
      {selected && (
        <RunPanel
          id={selected}
          permissions={permissions}
          close={() => setSelected(undefined)}
        />
      )}
    </>
  )
}

function RunPanel({
  id,
  permissions,
  close,
}: {
  id: string
  permissions: Set<string>
  close: () => void
}) {
  const client = useQueryClient()
  const confirm = useConfirmation()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [search, setSearch] = useState('')
  const [exceptionOnly, setExceptionOnly] = useState(false)
  const [sort, setSort] = useState<
    'employee' | 'gross' | 'net' | 'department' | 'status'
  >('employee')
  const [direction, setDirection] = useState<'asc' | 'desc'>('asc')
  const [payment, setPayment] = useState(false)
  const [reversal, setReversal] = useState(false)
  const [adjustment, setAdjustment] = useState(false)
  const [returning, setReturning] = useState(false)
  const [selectedResult, setSelectedResult] = useState<string>()
  const detail = useQuery({
    queryKey: [
      'payroll',
      'run',
      id,
      page,
      pageSize,
      search,
      exceptionOnly,
      sort,
      direction,
    ],
    queryFn: () =>
      payrollApi.run(id, {
        page,
        pageSize,
        search,
        exceptionOnly,
        sort,
        direction,
      }),
  })
  const accounts = useQuery({
    queryKey: ['finance', 'accounts'],
    queryFn: financeApi.accounts,
    enabled: payment,
  })
  const mutation = useMutation({
    mutationFn: ({ action, body }: { action: string; body?: unknown }) =>
      payrollApi.action(id, action, body),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll'] })
      setPayment(false)
      setReversal(false)
      setReturning(false)
    },
  })
  const recalculate = useMutation({
    mutationFn: () => payrollApi.prepare(detail.data!.period.id),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll'] })
    },
  })
  const adjustMutation = useMutation({
    mutationFn: (body: unknown) =>
      payrollApi.createAdjustment(detail.data!.period.id, body),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll'] })
      setAdjustment(false)
    },
  })
  if (detail.isLoading) return <Loading />
  if (detail.error || !detail.data)
    return (
      <ErrorState
        error={detail.error ?? new Error('Payroll run unavailable.')}
        retry={() => void detail.refetch()}
      />
    )
  const data = detail.data
  const act = async (action: string, body?: unknown) => {
    const approved = await confirm({
      title: `${action[0]?.toUpperCase()}${action.slice(1)} payroll run?`,
      description:
        'This controlled payroll transition is audit logged and may lock payroll records.',
      confirmLabel: action,
    })
    if (approved) mutation.mutate({ action, body })
  }
  return (
    <Section
      title={`${data.period.name} · version ${data.run.version}`}
      actions={<button onClick={close}>Close details</button>}
    >
      <div className="finance-summary">
        <Metric label="Employees" value={String(data.summary.employee_count)} />
        <Metric
          label="Gross payroll"
          value={payrollMoney(
            data.summary.gross_payroll,
            data.summary.currency,
          )}
        />
        <Metric
          label="Deductions"
          value={payrollMoney(
            data.summary.total_deductions,
            data.summary.currency,
          )}
        />
        <Metric
          label="PAYE"
          value={payrollMoney(data.summary.paye, data.summary.currency)}
        />
        <Metric
          label="Employee pension"
          value={payrollMoney(
            data.summary.pension_employee,
            data.summary.currency,
          )}
        />
        <Metric
          label="Employer pension"
          value={payrollMoney(
            data.summary.pension_employer,
            data.summary.currency,
          )}
        />
        <Metric
          label="NHF"
          value={payrollMoney(data.summary.nhf, data.summary.currency)}
        />
        <Metric
          label="Employer cost"
          value={payrollMoney(
            data.summary.employer_cost,
            data.summary.currency,
          )}
        />
        <Metric
          label="Net payroll"
          value={payrollMoney(data.summary.net_payroll, data.summary.currency)}
        />
        <Metric
          label="Exceptions"
          value={String(data.summary.exception_count)}
        />
      </div>
      <div className="finance-actions">
        <Status value={data.run.status} />
        {data.allowed_actions.includes('prepare') &&
          permissions.has('payroll.prepare') && (
            <button
              disabled={recalculate.isPending}
              onClick={() => recalculate.mutate()}
            >
              Recalculate
            </button>
          )}
        {['draft', 'returned', 'prepared'].includes(data.run.status) &&
          permissions.has('payroll.prepare') && (
            <button onClick={() => setAdjustment(!adjustment)}>
              {adjustment ? 'Close adjustment' : 'Add adjustment'}
            </button>
          )}
        {data.allowed_actions.includes('submit') &&
          permissions.has('payroll.prepare') && (
            <button onClick={() => void act('submit')}>
              Submit for approval
            </button>
          )}
        {data.allowed_actions.includes('return') &&
          permissions.has('payroll.review') && (
            <button onClick={() => setReturning(!returning)}>
              {returning ? 'Close return form' : 'Return'}
            </button>
          )}
        {data.allowed_actions.includes('approve') &&
          permissions.has('payroll.approve') && (
            <button
              className="finance-primary"
              onClick={() => void act('approve')}
            >
              Approve
            </button>
          )}
        {data.allowed_actions.includes('pay') &&
          permissions.has('payroll.pay') && (
            <button
              className="finance-primary"
              onClick={() => setPayment(true)}
            >
              Record payment
            </button>
          )}
        {data.allowed_actions.includes('close') &&
          permissions.has('payroll.pay') && (
            <button onClick={() => void act('close')}>Close period</button>
          )}
        {data.allowed_actions.includes('reverse') &&
          permissions.has('payroll.pay') && (
            <button onClick={() => setReversal(!reversal)}>
              <RotateCcw size={16} /> Reverse payment
            </button>
          )}
        {permissions.has('payroll.export') && (
          <button
            onClick={() =>
              void downloadPayroll(
                `/payroll/runs/${id}/export`,
                `payroll-${data.period.name}.csv`,
              )
            }
          >
            <Download size={16} />
            Export register
          </button>
        )}
      </div>
      {payment && (
        <form
          className="finance-filters"
          onSubmit={(event) => {
            event.preventDefault()
            const values = input(event.currentTarget)
            void act('pay', { ...values, idempotency_key: crypto.randomUUID() })
          }}
        >
          <Field label="Funding account">
            <select name="account_id" required>
              <option value="">Select account</option>
              {accounts.data?.map((account) => (
                <option value={account.id} key={account.id}>
                  {account.account_name} · {account.currency}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Payment date">
            <input
              name="payment_date"
              type="date"
              defaultValue={today}
              required
            />
          </Field>
          <Field label="Payment reference">
            <input name="payment_reference" required />
          </Field>
          <button className="finance-primary">Confirm payment</button>
        </form>
      )}
      {reversal && (
        <form
          className="finance-filters"
          onSubmit={(event) => {
            event.preventDefault()
            const values = input(event.currentTarget)
            void act('reverse', {
              ...values,
              idempotency_key: crypto.randomUUID(),
            })
          }}
        >
          <Field label="Reversal reason">
            <input name="reason" required minLength={3} />
          </Field>
          <button className="finance-primary">Confirm reversal</button>
        </form>
      )}
      {returning && (
        <form
          className="finance-filters"
          onSubmit={(event) => {
            event.preventDefault()
            const values = input(event.currentTarget)
            void act('return', { reason: values.reason })
          }}
        >
          <Field label="Return reason">
            <input
              name="reason"
              required
              minLength={3}
              placeholder="Explain what must be corrected"
            />
          </Field>
          <button className="finance-primary" disabled={mutation.isPending}>
            Return for correction
          </button>
        </form>
      )}
      {adjustment && (
        <form
          className="finance-filters"
          onSubmit={(event) => {
            event.preventDefault()
            adjustMutation.mutate({
              ...input(event.currentTarget),
              idempotency_key: crypto.randomUUID(),
              status: 'approved',
            })
          }}
        >
          <Field label="Employee">
            <select name="employee_id" required>
              <option value="">Select employee</option>
              {data.results.items.map((row) => (
                <option key={row.employee_id} value={row.employee_id}>
                  {row.employee_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Adjustment type">
            <select name="adjustment_type">
              <option value="bonus">Bonus</option>
              <option value="overtime">Overtime</option>
              <option value="arrears">Arrears</option>
              <option value="deduction">Deduction</option>
              <option value="salary_advance">Salary advance</option>
            </select>
          </Field>
          <Field label="Amount">
            <input
              name="amount"
              type="number"
              min="0.01"
              step="0.01"
              required
            />
          </Field>
          <Field label="Reason">
            <input name="reason" required />
          </Field>
          <button
            className="finance-primary"
            disabled={adjustMutation.isPending}
          >
            Save adjustment
          </button>
        </form>
      )}
      {(mutation.error || adjustMutation.error || recalculate.error) && (
        <ErrorState
          error={mutation.error ?? adjustMutation.error ?? recalculate.error}
        />
      )}
      <div className="finance-filters" aria-label="Payroll result filters">
        <Field label="Search employees">
          <input
            value={search}
            placeholder="Name or employee number"
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
          />
        </Field>
        <Field label="Sort by">
          <select
            value={sort}
            onChange={(event) => {
              setSort(event.target.value as typeof sort)
              setPage(1)
            }}
          >
            <option value="employee">Employee</option>
            <option value="department">Department</option>
            <option value="gross">Gross pay</option>
            <option value="net">Net pay</option>
            <option value="status">Status</option>
          </select>
        </Field>
        <Field label="Direction">
          <select
            value={direction}
            onChange={(event) => {
              setDirection(event.target.value as typeof direction)
              setPage(1)
            }}
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </Field>
        <label className="finance-check">
          <input
            type="checkbox"
            checked={exceptionOnly}
            onChange={(event) => {
              setExceptionOnly(event.target.checked)
              setPage(1)
            }}
          />
          Exceptions only
        </label>
      </div>
      <div className="finance-table-wrap">
        <table className="finance-table">
          <thead>
            <tr>
              <th>Employee</th>
              <th>Department</th>
              <th>Gross</th>
              <th>Deductions</th>
              <th>Net</th>
              <th>Status</th>
              <th>Calculation</th>
            </tr>
          </thead>
          <tbody>
            {data.results.items.map((result) => (
              <tr key={result.id}>
                <td>
                  {result.employee_name}
                  <small>
                    {result.employee_number ?? 'No employee number'}
                  </small>
                </td>
                <td>{result.department_name ?? '—'}</td>
                <td>{payrollMoney(result.gross_pay, result.currency)}</td>
                <td>
                  {payrollMoney(result.total_deductions, result.currency)}
                </td>
                <td>
                  <strong>
                    {payrollMoney(result.net_pay, result.currency)}
                  </strong>
                </td>
                <td>
                  <Status
                    value={
                      result.exceptions.length ? 'returned' : result.status
                    }
                  />
                </td>
                <td>
                  <button
                    aria-label={`View calculation for ${result.employee_name}`}
                    onClick={() => setSelectedResult(result.id)}
                  >
                    <Eye size={16} />
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager
        page={page}
        totalPages={data.results.total_pages}
        total={data.results.total}
        size={data.results.page_size}
        onPage={setPage}
        onSize={(size) => {
          setPageSize(size)
          setPage(1)
        }}
      />
      {selectedResult && (
        <CalculationDetail
          id={selectedResult}
          close={() => setSelectedResult(undefined)}
        />
      )}
    </Section>
  )
}

function Payslips() {
  const query = useQuery({
    queryKey: ['payroll', 'payslips'],
    queryFn: payrollApi.payslips,
  })
  if (query.isLoading) return <Loading />
  if (query.error)
    return <ErrorState error={query.error} retry={() => void query.refetch()} />
  return (
    <Section title="My payslips">
      <div className="finance-table-wrap">
        <table className="finance-table">
          <thead>
            <tr>
              <th>Payroll period</th>
              <th>Gross</th>
              <th>Deductions</th>
              <th>Net pay</th>
              <th>Document</th>
            </tr>
          </thead>
          <tbody>
            {query.data?.map((row) => (
              <tr key={row.id}>
                <td>
                  {row.period_name ?? 'Paid payroll'}
                  <small>
                    {row.period_start && row.period_end
                      ? `${row.period_start} – ${row.period_end}`
                      : row.employee_name}
                  </small>
                </td>
                <td>{payrollMoney(row.gross_pay, row.currency)}</td>
                <td>{payrollMoney(row.total_deductions, row.currency)}</td>
                <td>
                  <strong>{payrollMoney(row.net_pay, row.currency)}</strong>
                </td>
                <td>
                  <button
                    onClick={() =>
                      void downloadPayroll(
                        `/payroll/results/${row.id}/payslip`,
                        'payslip.pdf',
                      )
                    }
                  >
                    <Download size={16} />
                    Download
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {query.data?.length === 0 && (
        <p className="finance-empty">No paid payslips are available yet.</p>
      )}
    </Section>
  )
}

function Structures({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()
  const confirm = useConfirmation()
  const [create, setCreate] = useState(false)
  const [ending, setEnding] = useState<string>()
  const [preview, setPreview] = useState<Record<string, string>>()
  const [items, setItems] = useState<
    Array<{ component_id: string; amount: string; percentage: string }>
  >([])
  const query = useQuery({
    queryKey: ['payroll', 'structures'],
    queryFn: payrollApi.structures,
  })
  const employees = useQuery({
    queryKey: ['payroll', 'employees'],
    queryFn: payrollApi.employees,
  })
  const components = useQuery({
    queryKey: ['payroll', 'components'],
    queryFn: payrollApi.components,
  })
  const mutation = useMutation({
    mutationFn: payrollApi.createStructure,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll', 'structures'] })
      setCreate(false)
      setPreview(undefined)
      setItems([])
    },
  })
  const previewMutation = useMutation({
    mutationFn: payrollApi.previewStructure,
    onSuccess: setPreview,
  })
  const endMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: unknown }) =>
      payrollApi.endStructure(id, body),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll', 'structures'] })
      setEnding(undefined)
    },
  })
  const payload = (form: HTMLFormElement) => ({
    ...input(form),
    pension_participates: true,
    nhf_participates: true,
    paye_participates: true,
    status: 'active',
    items: items.map((item) => ({
      component_id: item.component_id,
      amount: item.amount || '0',
      percentage: item.percentage || '0',
    })),
  })
  if (query.isLoading) return <Loading />
  return (
    <Section
      title="Effective-dated salary structures"
      actions={
        canManage ? (
          <button
            className="finance-primary"
            onClick={() => setCreate(!create)}
          >
            <Plus size={16} />
            {create ? 'Close' : 'New structure'}
          </button>
        ) : undefined
      }
    >
      {create && (
        <form
          className="finance-filters"
          onSubmit={(event) => {
            event.preventDefault()
            mutation.mutate(payload(event.currentTarget))
          }}
        >
          <Field label="Employee">
            <select name="employee_id" required>
              <option value="">Select employee</option>
              {employees.data?.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.display_name}
                  {employee.employee_number
                    ? ` · ${employee.employee_number}`
                    : ''}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Basic monthly salary">
            <input
              name="basic_salary"
              type="number"
              min="0"
              step="0.01"
              required
            />
          </Field>
          <Field label="Currency">
            <input name="currency" defaultValue="NGN" required />
          </Field>
          <Field label="Effective from">
            <input
              name="effective_start"
              type="date"
              defaultValue={today}
              required
            />
          </Field>
          <Field label="Change reason">
            <input name="change_reason" required />
          </Field>
          <div className="finance-field" style={{ gridColumn: '1 / -1' }}>
            <span>Allowances and deductions</span>
            {items.map((item, index) => (
              <div
                className="finance-line"
                key={`${item.component_id}-${index}`}
              >
                <Field label="Component">
                  <select
                    value={item.component_id}
                    required
                    onChange={(event) =>
                      setItems((rows) =>
                        rows.map((row, rowIndex) =>
                          rowIndex === index
                            ? { ...row, component_id: event.target.value }
                            : row,
                        ),
                      )
                    }
                  >
                    <option value="">Select component</option>
                    {components.data
                      ?.filter((component) => component.is_active)
                      .map((component) => (
                        <option key={component.id} value={component.id}>
                          {component.name} · {component.component_kind}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label="Fixed amount">
                  <input
                    aria-label={`Component ${index + 1} fixed amount`}
                    type="number"
                    min="0"
                    step="0.01"
                    value={item.amount}
                    onChange={(event) =>
                      setItems((rows) =>
                        rows.map((row, rowIndex) =>
                          rowIndex === index
                            ? { ...row, amount: event.target.value }
                            : row,
                        ),
                      )
                    }
                  />
                </Field>
                <Field label="Percent of basic">
                  <input
                    aria-label={`Component ${index + 1} percentage`}
                    type="number"
                    min="0"
                    max="100"
                    step="0.000001"
                    value={item.percentage}
                    onChange={(event) =>
                      setItems((rows) =>
                        rows.map((row, rowIndex) =>
                          rowIndex === index
                            ? { ...row, percentage: event.target.value }
                            : row,
                        ),
                      )
                    }
                  />
                </Field>
                <button
                  type="button"
                  aria-label={`Remove component ${index + 1}`}
                  onClick={() =>
                    setItems((rows) =>
                      rows.filter((_, rowIndex) => rowIndex !== index),
                    )
                  }
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                setItems((rows) => [
                  ...rows,
                  { component_id: '', amount: '0', percentage: '0' },
                ])
              }
            >
              <Plus size={16} />
              Add component
            </button>
          </div>
          <button
            type="button"
            onClick={(event) => {
              const form = event.currentTarget.form
              if (form?.reportValidity()) previewMutation.mutate(payload(form))
            }}
          >
            Preview net pay
          </button>
          <button className="finance-primary" disabled={mutation.isPending}>
            Save structure
          </button>
        </form>
      )}
      {preview && (
        <div className="finance-summary">
          <Metric
            label="Gross pay"
            value={payrollMoney(
              preview.gross_pay ?? '0',
              preview.currency ?? 'NGN',
            )}
          />
          <Metric
            label="Deductions"
            value={payrollMoney(
              preview.total_deductions ?? '0',
              preview.currency ?? 'NGN',
            )}
          />
          <Metric
            label="Estimated net"
            value={payrollMoney(
              preview.net_pay ?? '0',
              preview.currency ?? 'NGN',
            )}
          />
        </div>
      )}
      {ending && (
        <form
          className="finance-filters"
          onSubmit={async (event) => {
            event.preventDefault()
            const approved = await confirm({
              title: 'End salary structure?',
              description:
                'The historical structure will remain immutable and future payroll periods will no longer use it.',
              confirmLabel: 'End structure',
            })
            if (approved)
              endMutation.mutate({
                id: ending,
                body: input(event.currentTarget),
              })
          }}
        >
          <Field label="Effective end date">
            <input name="effective_end" type="date" required />
          </Field>
          <Field label="Reason">
            <input name="reason" required />
          </Field>
          <button className="finance-primary">Confirm end date</button>
          <button type="button" onClick={() => setEnding(undefined)}>
            Cancel
          </button>
        </form>
      )}
      {(mutation.error ||
        previewMutation.error ||
        endMutation.error ||
        query.error) && (
        <ErrorState
          error={
            mutation.error ??
            previewMutation.error ??
            endMutation.error ??
            query.error
          }
        />
      )}
      <div className="finance-table-wrap">
        <table className="finance-table">
          <thead>
            <tr>
              <th>Employee</th>
              <th>Basic</th>
              <th>Gross</th>
              <th>Effective</th>
              <th>Status</th>
              <th>Changed by</th>
              <th>Reason</th>
              {canManage && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {query.data?.map((row) => (
              <tr key={row.id}>
                <td>{row.employee_name ?? 'Employee'}</td>
                <td>{payrollMoney(row.basic_salary, row.currency)}</td>
                <td>{payrollMoney(row.gross_salary, row.currency)}</td>
                <td>
                  {row.effective_start}
                  {row.effective_end ? ` – ${row.effective_end}` : ''}
                </td>
                <td>
                  <Status value={row.status} />
                </td>
                <td>{row.changed_by_name ?? 'Payroll administrator'}</td>
                <td>{row.change_reason}</td>
                {canManage && (
                  <td>
                    {row.status === 'active' && !row.effective_end ? (
                      <button onClick={() => setEnding(row.id)}>
                        End structure
                      </button>
                    ) : (
                      'Historical'
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

function ComponentFields({ component }: { component?: SalaryComponent }) {
  return (
    <>
      <Field label="Code">
        <input name="code" defaultValue={component?.code} required />
      </Field>
      <Field label="Name">
        <input name="name" defaultValue={component?.name} required />
      </Field>
      <Field label="Description">
        <input name="description" defaultValue={component?.description ?? ''} />
      </Field>
      <Field label="Kind">
        <select name="component_kind" defaultValue={component?.component_kind}>
          <option value="earning">Earning</option>
          <option value="deduction">Deduction</option>
        </select>
      </Field>
      <Field label="Calculation">
        <select
          name="calculation_type"
          defaultValue={component?.calculation_type}
        >
          <option value="fixed">Fixed</option>
          <option value="percentage">Percentage</option>
        </select>
      </Field>
      <Field label="Effective from">
        <input
          name="effective_start"
          type="date"
          defaultValue={component?.effective_start ?? today}
          required
        />
      </Field>
      <Field label="Effective to">
        <input
          name="effective_end"
          type="date"
          defaultValue={component?.effective_end ?? ''}
        />
      </Field>
      <label className="finance-check">
        <input
          name="taxable"
          type="checkbox"
          defaultChecked={component?.taxable ?? true}
        />
        Taxable
      </label>
      <label className="finance-check">
        <input
          name="pensionable"
          type="checkbox"
          defaultChecked={component?.pensionable ?? false}
        />
        Pensionable
      </label>
      <label className="finance-check">
        <input
          name="recurring"
          type="checkbox"
          defaultChecked={component?.recurring ?? true}
        />
        Recurring
      </label>
      <label className="finance-check">
        <input
          name="is_active"
          type="checkbox"
          defaultChecked={component?.is_active ?? true}
        />
        Active
      </label>
    </>
  )
}

function Components({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()
  const confirm = useConfirmation()
  const [create, setCreate] = useState(false)
  const [editing, setEditing] = useState<SalaryComponent>()
  const query = useQuery({
    queryKey: ['payroll', 'components'],
    queryFn: payrollApi.components,
  })
  const mutation = useMutation({
    mutationFn: payrollApi.createComponent,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll', 'components'] })
      setCreate(false)
    },
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: unknown }) =>
      payrollApi.updateComponent(id, body),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll', 'components'] })
      setEditing(undefined)
    },
  })
  const toggle = async (row: NonNullable<typeof query.data>[number]) => {
    const next = !row.is_active
    const approved = await confirm({
      title: `${next ? 'Activate' : 'Deactivate'} salary component?`,
      description: next
        ? 'The component can be selected for new effective-dated salary structures.'
        : 'Historical payroll remains unchanged; new structures cannot select this component.',
      confirmLabel: next ? 'Activate' : 'Deactivate',
    })
    if (approved)
      updateMutation.mutate({
        id: row.id,
        body: {
          code: row.code,
          name: row.name,
          description: row.description,
          component_kind: row.component_kind,
          calculation_type: row.calculation_type,
          taxable: row.taxable,
          pensionable: row.pensionable,
          recurring: row.recurring,
          is_active: next,
          effective_start: row.effective_start,
          effective_end: row.effective_end,
        },
      })
  }
  return (
    <Section
      title="Salary components"
      actions={
        canManage ? (
          <button
            className="finance-primary"
            onClick={() => setCreate(!create)}
          >
            <Plus size={16} />
            {create ? 'Close' : 'New component'}
          </button>
        ) : undefined
      }
    >
      {create && (
        <form
          className="finance-filters"
          onSubmit={(event) => {
            event.preventDefault()
            mutation.mutate(componentInput(event.currentTarget))
          }}
        >
          <ComponentFields />
          <button className="finance-primary" disabled={mutation.isPending}>
            Create component
          </button>
        </form>
      )}
      {editing && (
        <form
          className="finance-filters"
          aria-label={`Edit ${editing.name}`}
          onSubmit={(event) => {
            event.preventDefault()
            updateMutation.mutate({
              id: editing.id,
              body: componentInput(event.currentTarget),
            })
          }}
        >
          <ComponentFields component={editing} />
          <button
            className="finance-primary"
            disabled={updateMutation.isPending}
          >
            Save component
          </button>
          <button type="button" onClick={() => setEditing(undefined)}>
            Cancel
          </button>
        </form>
      )}
      {query.isLoading ? (
        <Loading />
      ) : query.error || mutation.error || updateMutation.error ? (
        <ErrorState
          error={query.error ?? mutation.error ?? updateMutation.error}
        />
      ) : (
        <div className="finance-table-wrap">
          <table className="finance-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Kind</th>
                <th>Calculation</th>
                <th>Status</th>
                {canManage && <th>Action</th>}
              </tr>
            </thead>
            <tbody>
              {query.data?.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td>{row.component_kind}</td>
                  <td>{row.calculation_type}</td>
                  <td>
                    <Status value={row.is_active ? 'active' : 'disabled'} />
                  </td>
                  {canManage && (
                    <td>
                      <button onClick={() => setEditing(row)}>Edit</button>
                      <button
                        disabled={updateMutation.isPending}
                        onClick={() => void toggle(row)}
                      >
                        {row.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}

function Statutory({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()
  const [create, setCreate] = useState(false)
  const [configurationType, setConfigurationType] = useState('paye')
  const [formError, setFormError] = useState<string>()
  const query = useQuery({
    queryKey: ['payroll', 'statutory'],
    queryFn: payrollApi.statutory,
  })
  const mutation = useMutation({
    mutationFn: payrollApi.createStatutory,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll', 'statutory'] })
      setCreate(false)
    },
  })
  return (
    <Section
      title="Statutory and payroll policy"
      actions={
        canManage ? (
          <button onClick={() => setCreate(!create)}>
            <Plus size={16} />
            New configuration
          </button>
        ) : undefined
      }
    >
      {create && (
        <form
          className="finance-filters"
          onSubmit={(event) => {
            event.preventDefault()
            const values = input(event.currentTarget)
            try {
              setFormError(undefined)
              let rules: Record<string, unknown>
              if (configurationType === 'paye')
                rules = {
                  annual_relief_fixed: values.annual_relief_fixed,
                  annual_relief_rate: values.annual_relief_rate,
                  minimum_tax_rate: values.minimum_tax_rate,
                  bands: JSON.parse(String(values.bands)),
                }
              else if (configurationType === 'pension')
                rules = {
                  basis: values.basis,
                  employee_rate: values.employee_rate,
                  employer_rate: values.employer_rate,
                }
              else if (configurationType === 'nhf')
                rules = {
                  basis: values.basis,
                  employee_rate: values.employee_rate,
                }
              else rules = { proration_method: values.proration_method }
              mutation.mutate({
                configuration_type: configurationType,
                name: values.name,
                effective_start: values.effective_start,
                change_reason: values.change_reason,
                rules,
                is_active: true,
              })
            } catch {
              setFormError(
                'PAYE bands must be a valid JSON list of annual limits and rates.',
              )
            }
          }}
        >
          <Field label="Type">
            <select
              name="configuration_type"
              value={configurationType}
              onChange={(event) => setConfigurationType(event.target.value)}
            >
              <option value="paye">PAYE</option>
              <option value="pension">Pension</option>
              <option value="nhf">NHF</option>
              <option value="payroll_policy">Payroll policy</option>
            </select>
          </Field>
          <Field label="Name">
            <input name="name" required />
          </Field>
          <Field label="Effective from">
            <input
              name="effective_start"
              type="date"
              defaultValue={today}
              required
            />
          </Field>
          <Field label="Change reason">
            <input name="change_reason" required />
          </Field>
          {configurationType === 'paye' && (
            <>
              <Field label="Annual fixed relief">
                <input
                  name="annual_relief_fixed"
                  type="number"
                  min="0"
                  step="0.01"
                  defaultValue="0"
                  required
                />
              </Field>
              <Field label="Annual relief rate (%)">
                <input
                  name="annual_relief_rate"
                  type="number"
                  min="0"
                  max="100"
                  step="0.000001"
                  defaultValue="0"
                  required
                />
              </Field>
              <Field label="Minimum tax rate (%)">
                <input
                  name="minimum_tax_rate"
                  type="number"
                  min="0"
                  max="100"
                  step="0.000001"
                  defaultValue="0"
                  required
                />
              </Field>
              <Field label="Annual tax bands">
                <textarea
                  name="bands"
                  defaultValue={'[{"limit": null, "rate": "10"}]'}
                  aria-describedby="paye-band-help"
                  required
                />
                <small id="paye-band-help">
                  Ordered JSON list. Use null for the final unlimited band.
                </small>
              </Field>
            </>
          )}
          {(configurationType === 'pension' || configurationType === 'nhf') && (
            <>
              <Field label="Earnings basis">
                <select name="basis">
                  <option
                    value={
                      configurationType === 'nhf' ? 'basic' : 'pensionable'
                    }
                  >
                    {configurationType === 'nhf'
                      ? 'Basic salary'
                      : 'Pensionable earnings'}
                  </option>
                  <option value="gross">Gross pay</option>
                </select>
              </Field>
              <Field label="Employee rate (%)">
                <input
                  name="employee_rate"
                  type="number"
                  min="0"
                  max="100"
                  step="0.000001"
                  required
                />
              </Field>
              {configurationType === 'pension' && (
                <Field label="Employer rate (%)">
                  <input
                    name="employer_rate"
                    type="number"
                    min="0"
                    max="100"
                    step="0.000001"
                    required
                  />
                </Field>
              )}
            </>
          )}
          {configurationType === 'payroll_policy' && (
            <Field label="Proration method">
              <select name="proration_method">
                <option value="calendar_days">Calendar days</option>
                <option value="working_days">Working days</option>
              </select>
            </Field>
          )}
          <button className="finance-primary">Save configuration</button>
        </form>
      )}
      {formError && (
        <div className="finance-error" role="alert">
          {formError}
        </div>
      )}
      {query.isLoading ? (
        <Loading />
      ) : query.error || mutation.error ? (
        <ErrorState error={query.error ?? mutation.error} />
      ) : (
        <div className="finance-table-wrap">
          <table className="finance-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Name</th>
                <th>Effective</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {query.data?.map((row) => (
                <tr key={row.id}>
                  <td>{row.configuration_type.toUpperCase()}</td>
                  <td>
                    {row.name}
                    <small>{row.change_reason}</small>
                  </td>
                  <td>{row.effective_start}</td>
                  <td>
                    <Status value={row.is_active ? 'active' : 'disabled'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}

function Loans() {
  const client = useQueryClient()
  const [create, setCreate] = useState(false)
  const query = useQuery({
    queryKey: ['payroll', 'loans'],
    queryFn: payrollApi.loans,
  })
  const employees = useQuery({
    queryKey: ['payroll', 'employees'],
    queryFn: payrollApi.employees,
  })
  const mutation = useMutation({
    mutationFn: payrollApi.createLoan,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll', 'loans'] })
      setCreate(false)
    },
  })
  const names = new Map(
    employees.data?.map((row) => [row.id, row.display_name]),
  )
  return (
    <Section
      title="Employee loans"
      actions={
        <button onClick={() => setCreate(!create)}>
          <Plus size={16} />
          New loan
        </button>
      }
    >
      {create && (
        <form
          className="finance-filters"
          onSubmit={(event) => {
            event.preventDefault()
            mutation.mutate({
              ...input(event.currentTarget),
              repayment_frequency: 'monthly',
            })
          }}
        >
          <Field label="Employee">
            <select name="employee_id" required>
              <option value="">Select employee</option>
              {employees.data?.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.display_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Principal">
            <input
              name="principal"
              type="number"
              min="0.01"
              step="0.01"
              required
            />
          </Field>
          <Field label="Monthly repayment">
            <input
              name="repayment_amount"
              type="number"
              min="0.01"
              step="0.01"
              required
            />
          </Field>
          <Field label="Start date">
            <input
              name="start_date"
              type="date"
              defaultValue={today}
              required
            />
          </Field>
          <Field label="Reason">
            <input name="reason" required />
          </Field>
          <button className="finance-primary">Create loan</button>
        </form>
      )}
      {query.isLoading ? (
        <Loading />
      ) : query.error || mutation.error ? (
        <ErrorState error={query.error ?? mutation.error} />
      ) : (
        <div className="finance-table-wrap">
          <table className="finance-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Principal</th>
                <th>Repayment</th>
                <th>Outstanding</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {query.data?.map((row) => (
                <tr key={row.id}>
                  <td>{names.get(row.employee_id) ?? 'Employee'}</td>
                  <td>{payrollMoney(row.principal)}</td>
                  <td>{payrollMoney(row.repayment_amount)}</td>
                  <td>{payrollMoney(row.outstanding_balance)}</td>
                  <td>
                    <Status value={row.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}

function CalculationDetail({ id, close }: { id: string; close: () => void }) {
  const query = useQuery({
    queryKey: ['payroll', 'result', id],
    queryFn: () => payrollApi.result(id),
  })
  if (query.isLoading) return <Loading />
  if (query.error || !query.data)
    return (
      <ErrorState
        error={query.error ?? new Error('Calculation unavailable.')}
      />
    )
  const result = query.data
  return (
    <aside
      className="finance-section"
      aria-label="Employee payroll calculation"
    >
      <header>
        <div>
          <h2>{result.employee_name}</h2>
          <p className="text-muted-foreground">
            Explainable payroll calculation · proration{' '}
            {result.proration_factor}
          </p>
        </div>
        <button onClick={close}>Close</button>
      </header>
      <div className="finance-summary">
        <Metric
          label="Basic salary"
          value={payrollMoney(result.basic_salary, result.currency)}
        />
        <Metric
          label="Allowances"
          value={payrollMoney(result.allowances, result.currency)}
        />
        <Metric
          label="Variable earnings"
          value={payrollMoney(result.variable_earnings, result.currency)}
        />
        <Metric
          label="Gross pay"
          value={payrollMoney(result.gross_pay, result.currency)}
        />
        <Metric
          label="PAYE"
          value={payrollMoney(result.paye, result.currency)}
        />
        <Metric
          label="Pension"
          value={payrollMoney(result.pension_employee, result.currency)}
        />
        <Metric label="NHF" value={payrollMoney(result.nhf, result.currency)} />
        <Metric
          label="Net pay"
          value={payrollMoney(result.net_pay, result.currency)}
        />
      </div>
      {result.exceptions.length > 0 && (
        <div role="alert" className="finance-error">
          {result.exceptions.length} calculation exception
          {result.exceptions.length === 1 ? '' : 's'} must be resolved before
          approval.
        </div>
      )}
      <div className="finance-table-wrap">
        <table className="finance-table finance-table-responsive">
          <thead>
            <tr>
              <th>Line</th>
              <th>Category</th>
              <th>Basis</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {result.items.map((item) => (
              <tr key={item.id}>
                <td data-label="Line">
                  {item.name}
                  <small>
                    {item.code}
                    {item.taxable ? ' · Taxable' : ''}
                    {item.pensionable ? ' · Pensionable' : ''}
                  </small>
                </td>
                <td data-label="Category">{item.category}</td>
                <td data-label="Basis">{item.basis ?? 'Fixed'}</td>
                <td data-label="Amount">
                  {payrollMoney(item.amount, result.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </aside>
  )
}

function Reports() {
  const [runId, setRunId] = useState('')
  const runs = useQuery({
    queryKey: ['payroll', 'runs'],
    queryFn: payrollApi.runs,
  })
  const periods = useQuery({
    queryKey: ['payroll', 'periods'],
    queryFn: payrollApi.periods,
  })
  const report = useQuery({
    queryKey: ['payroll', 'reports', runId],
    queryFn: () => payrollApi.reports(runId),
    enabled: Boolean(runId),
  })
  const names = new Map(periods.data?.map((row) => [row.id, row.name]))
  return (
    <Section title="Payroll reports and statutory exports">
      <div className="finance-toolbar">
        <Field label="Payroll run">
          <select
            value={runId}
            onChange={(event) => setRunId(event.target.value)}
          >
            <option value="">Select payroll period</option>
            {runs.data?.map((run) => (
              <option key={run.id} value={run.id}>
                {names.get(run.period_id) ?? 'Payroll period'} · v{run.version}{' '}
                · {run.status}
              </option>
            ))}
          </select>
        </Field>
        {runId && (
          <>
            <button
              onClick={() =>
                void downloadPayroll(
                  `/payroll/runs/${runId}/export`,
                  'payroll-register.csv',
                )
              }
            >
              <Download size={16} />
              Payroll register
            </button>
            <button
              onClick={() =>
                void downloadPayroll(
                  `/payroll/runs/${runId}/statutory-export`,
                  'statutory-summary.csv',
                )
              }
            >
              <Download size={16} />
              Statutory summary
            </button>
          </>
        )}
      </div>
      {(runs.error || periods.error || report.error) && (
        <ErrorState error={runs.error ?? periods.error ?? report.error} />
      )}
      {report.isLoading && <Loading />}
      {runId && report.data && (
        <div className="finance-table-wrap">
          <table className="finance-table finance-table-responsive">
            <thead>
              <tr>
                <th>Department</th>
                <th>Employees</th>
                <th>Gross</th>
                <th>PAYE</th>
                <th>Pension</th>
                <th>NHF</th>
                <th>Net</th>
                <th>Employer cost</th>
              </tr>
            </thead>
            <tbody>
              {report.data.map((row) => (
                <tr key={row.group}>
                  <td data-label="Department">{row.group}</td>
                  <td data-label="Employees">{row.employee_count}</td>
                  <td data-label="Gross">{payrollMoney(row.gross_pay)}</td>
                  <td data-label="PAYE">{payrollMoney(row.paye)}</td>
                  <td data-label="Pension">{payrollMoney(row.pension)}</td>
                  <td data-label="NHF">{payrollMoney(row.nhf)}</td>
                  <td data-label="Net">{payrollMoney(row.net_pay)}</td>
                  <td data-label="Employer cost">
                    {payrollMoney(row.employer_cost)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!runId && (
        <p className="finance-empty">
          Select a payroll run to view its tenant-scoped department summary and
          exports.
        </p>
      )}
    </Section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="finance-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
