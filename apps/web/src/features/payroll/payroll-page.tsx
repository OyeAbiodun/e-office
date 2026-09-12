import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Plus, ShieldCheck } from 'lucide-react'
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
import { downloadPayroll, payrollApi, payrollMoney } from './api'

type Tab =
  'runs' | 'payslips' | 'structures' | 'components' | 'statutory' | 'loans'
const today = new Date().toISOString().slice(0, 10)
const input = (form: HTMLFormElement) => Object.fromEntries(new FormData(form))

export function PayrollPage() {
  const { user } = useAuth()
  const permissions = useMemo(() => new Set(user?.permissions ?? []), [user])
  const [tab, setTab] = useState<Tab>(
    permissions.has('payroll.periods.view') ? 'runs' : 'payslips',
  )
  const tabs: Array<[Tab, string, string]> = [
    ['runs', 'Payroll runs', 'payroll.periods.view'],
    ['payslips', 'My payslips', 'payroll.view_own'],
    ['structures', 'Salary structures', 'payroll.salary_structure.view'],
    ['components', 'Components', 'payroll.salary_structure.view'],
    ['statutory', 'Statutory rules', 'payroll.salary_structure.view'],
    ['loans', 'Loans', 'payroll.loans.manage'],
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
          .filter(([, , permission]) => permissions.has(permission))
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
    </FinanceLayout>
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
      {permissions.has('payroll.periods.manage') && (
        <Section
          title="Payroll periods"
          actions={
            <button
              className="finance-primary"
              onClick={() => setCreate(!create)}
            >
              <Plus size={16} />
              {create ? 'Close' : 'New period'}
            </button>
          }
        >
          {create && (
            <form
              className="finance-filters"
              onSubmit={(event) => {
                event.preventDefault()
                const values = input(event.currentTarget)
                createPeriod.mutate(values)
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
          {createPeriod.error && <ErrorState error={createPeriod.error} />}
          <div className="finance-table-wrap">
            <table className="finance-table">
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
                      <td>
                        {period.name}
                        <small>{period.currency}</small>
                      </td>
                      <td>
                        {period.start_date} – {period.end_date}
                      </td>
                      <td>{period.payment_date}</td>
                      <td>
                        <Status value={run?.status ?? period.status} />
                      </td>
                      <td>
                        {run ? (
                          <button onClick={() => setSelected(run.id)}>
                            Open run
                          </button>
                        ) : permissions.has('payroll.prepare') ? (
                          <button
                            disabled={prepare.isPending}
                            onClick={() => prepare.mutate(period.id)}
                          >
                            Prepare
                          </button>
                        ) : (
                          'Not prepared'
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
      )}
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
  const [payment, setPayment] = useState(false)
  const detail = useQuery({
    queryKey: ['payroll', 'run', id, page],
    queryFn: () => payrollApi.run(id, page),
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
        {data.allowed_actions.includes('submit') &&
          permissions.has('payroll.prepare') && (
            <button onClick={() => void act('submit')}>
              Submit for approval
            </button>
          )}
        {data.allowed_actions.includes('return') &&
          permissions.has('payroll.review') && (
            <button
              onClick={() => {
                const reason = window.prompt('Reason for returning payroll')
                if (reason) void act('return', { reason })
              }}
            >
              Return
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
      {mutation.error && <ErrorState error={mutation.error} />}
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
        onSize={() => setPage(1)}
      />
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
              <th>Employee</th>
              <th>Gross</th>
              <th>Deductions</th>
              <th>Net pay</th>
              <th>Document</th>
            </tr>
          </thead>
          <tbody>
            {query.data?.map((row) => (
              <tr key={row.id}>
                <td>{row.employee_name}</td>
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
  const [create, setCreate] = useState(false)
  const [preview, setPreview] = useState<Record<string, string>>()
  const query = useQuery({
    queryKey: ['payroll', 'structures'],
    queryFn: payrollApi.structures,
  })
  const employees = useQuery({
    queryKey: ['payroll', 'employees'],
    queryFn: payrollApi.employees,
  })
  const mutation = useMutation({
    mutationFn: payrollApi.createStructure,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['payroll', 'structures'] })
      setCreate(false)
      setPreview(undefined)
    },
  })
  const previewMutation = useMutation({
    mutationFn: payrollApi.previewStructure,
    onSuccess: setPreview,
  })
  const payload = (form: HTMLFormElement) => ({
    ...input(form),
    pension_participates: true,
    nhf_participates: true,
    paye_participates: true,
    status: 'active',
    items: [],
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
      {(mutation.error || previewMutation.error || query.error) && (
        <ErrorState
          error={mutation.error ?? previewMutation.error ?? query.error}
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

function Components({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()
  const [create, setCreate] = useState(false)
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
            const values = input(event.currentTarget)
            mutation.mutate({
              ...values,
              taxable: true,
              pensionable: false,
              recurring: true,
              is_active: true,
            })
          }}
        >
          <Field label="Code">
            <input name="code" required />
          </Field>
          <Field label="Name">
            <input name="name" required />
          </Field>
          <Field label="Kind">
            <select name="component_kind">
              <option value="earning">Earning</option>
              <option value="deduction">Deduction</option>
            </select>
          </Field>
          <Field label="Calculation">
            <select name="calculation_type">
              <option value="fixed">Fixed</option>
              <option value="percentage">Percentage</option>
            </select>
          </Field>
          <Field label="Effective from">
            <input
              name="effective_start"
              type="date"
              defaultValue={today}
              required
            />
          </Field>
          <button className="finance-primary">Create component</button>
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
                <th>Code</th>
                <th>Name</th>
                <th>Kind</th>
                <th>Calculation</th>
                <th>Status</th>
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
            mutation.mutate({
              ...values,
              rules: JSON.parse(String(values.rules)),
              is_active: true,
            })
          }}
        >
          <Field label="Type">
            <select name="configuration_type">
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
          <Field label="Rules (JSON)">
            <textarea name="rules" defaultValue="{}" required />
          </Field>
          <button className="finance-primary">Save configuration</button>
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="finance-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
