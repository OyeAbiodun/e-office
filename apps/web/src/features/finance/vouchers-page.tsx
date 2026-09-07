import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '@/features/auth/auth-store'
import { financeApi, money, query, type Filters } from './api'
import { voucherStatuses } from './utils'
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

export function VouchersPage() {
  const { user } = useAuth()
  const permissions = new Set(user?.permissions)
  const [filters, setFilters] = useState<Filters>({ page: 1, page_size: 25 })
  const set = (key: string, value: string | number) =>
    setFilters((f) => ({
      ...f,
      [key]: value,
      ...(key === 'page' ? {} : { page: 1 }),
    }))
  const records = useQuery({
    queryKey: ['vouchers', filters],
    queryFn: () => financeApi.vouchers(filters),
    enabled: permissions.has('vouchers.view_own'),
  })
  const options = useQuery({
    queryKey: ['voucher-options'],
    queryFn: financeApi.options,
    enabled: permissions.has('vouchers.view_own'),
  })
  if (!permissions.has('vouchers.view_own'))
    return (
      <FinanceLayout title="Vouchers">
        <ErrorState
          error={new Error('You do not have permission to view vouchers.')}
        />
      </FinanceLayout>
    )
  return (
    <FinanceLayout
      title="Vouchers"
      subtitle="Request expenses, follow approvals, and track payments in one place."
      actions={
        <>
          {permissions.has('vouchers.export') && (
            <ExportButton
              path={`/vouchers/export${query(filters)}`}
              filename="vouchers.csv"
            >
              Export CSV
            </ExportButton>
          )}
          {permissions.has('vouchers.create') && (
            <Link className="finance-button finance-primary" to="/vouchers/new">
              <Plus size={16} />
              New voucher
            </Link>
          )}
        </>
      }
    >
      <Section title="Expense requests">
        <div className="finance-toolbar">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            aria-label="Search vouchers"
            placeholder="Search purpose or voucher number"
            value={String(filters.search ?? '')}
            onChange={(e) => set('search', e.target.value)}
          />
          <Field label="Status">
            <select
              value={String(filters.status ?? '')}
              onChange={(e) => set('status', e.target.value)}
            >
              <option value="">All statuses</option>
              {voucherStatuses.map((s) => (
                <option value={s} key={s}>
                  {s.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Sort">
            <select
              value={String(filters.sort ?? 'created')}
              onChange={(e) => set('sort', e.target.value)}
            >
              {['created', 'submitted', 'amount', 'status', 'number'].map(
                (v) => (
                  <option key={v}>{v}</option>
                ),
              )}
            </select>
          </Field>
          <Field label="Order">
            <select
              value={String(filters.direction ?? 'desc')}
              onChange={(e) => set('direction', e.target.value)}
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </Field>
        </div>
        <details>
          <summary>More filters</summary>
          <div className="finance-filters">
            {(['requesters', 'departments', 'approvers'] as const).map(
              (key) => {
                const field = {
                  requesters: 'requester_id',
                  departments: 'department_id',
                  approvers: 'approver_id',
                }[key]
                return (
                  <Field key={key} label={key}>
                    <select
                      value={String(filters[field] ?? '')}
                      onChange={(e) => set(field, e.target.value)}
                    >
                      <option value="">All {key}</option>
                      {options.data?.[key].map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                )
              },
            )}
            <Field label="Created from">
              <input
                type="date"
                value={String(filters.from_date ?? '')}
                onChange={(e) => set('from_date', e.target.value)}
              />
            </Field>
            <Field label="Created through">
              <input
                type="date"
                value={String(filters.to_date ?? '')}
                onChange={(e) => set('to_date', e.target.value)}
              />
            </Field>
            {['min_amount', 'max_amount'].map((key) => (
              <Field
                label={
                  key === 'min_amount' ? 'Minimum amount' : 'Maximum amount'
                }
                key={key}
              >
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={String(filters[key] ?? '')}
                  onChange={(e) => set(key, e.target.value)}
                />
              </Field>
            ))}
            <button onClick={() => setFilters({ page: 1, page_size: 25 })}>
              Reset filters
            </button>
          </div>
        </details>
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
                      'Voucher / purpose',
                      'Requester',
                      'Department',
                      'Requested',
                      'Status',
                      'Submitted',
                    ].map((v) => (
                      <th key={v}>{v}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.data?.items.map((v) => (
                    <tr key={v.id}>
                      <td data-label="Voucher">
                        <Link
                          to="/vouchers/$voucherId"
                          params={{ voucherId: v.id }}
                        >
                          {v.voucher_number}
                        </Link>
                        <small>{v.title}</small>
                      </td>
                      <td data-label="Requester">{v.requester_name}</td>
                      <td data-label="Department">
                        {v.department_name ?? '—'}
                      </td>
                      <td data-label="Requested" className="number">
                        {money(v.requested_amount, v.currency)}
                        <small>
                          Paid {money(v.disbursed_amount, v.currency)}
                        </small>
                      </td>
                      <td data-label="Status">
                        <Status value={v.status} />
                      </td>
                      <td data-label="Submitted">
                        {v.submitted_at
                          ? new Date(v.submitted_at).toLocaleDateString()
                          : 'Draft'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!records.data?.items.length && (
              <p className="finance-empty">
                No vouchers match these filters. Create a request or adjust your
                filters.
              </p>
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
    </FinanceLayout>
  )
}
