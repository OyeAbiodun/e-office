import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  BarChart3,
  CalendarRange,
  CalendarX2,
  Download,
  History,
  Pencil,
  Plus,
  Search,
  Settings2,
  ShieldAlert,
  SlidersHorizontal,
  Users,
} from 'lucide-react'
import { type FormEvent, useMemo, useState } from 'react'

import {
  leaveApi,
  type LeaveBalanceRow,
  type LeavePeriod,
  type LeaveType,
} from './api'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  PageHeader,
  Pagination,
  PersonMark,
  StatusBadge,
} from './shared'
import { formatDateTime, formatDay, formatDays } from './utils'
import { useConfirmation } from '@/components/feedback/confirmation'
import { calendarApi } from '@/features/calendar/api'
import { useAuth } from '@/features/auth/auth-store'
import { organizationApi } from '@/features/organizations/api'
import { userAdminApi } from '@/features/users/api'

type AdminSection = 'types' | 'balances' | 'periods' | 'calendar' | 'reports'

export function LeaveAdminPage() {
  const { user } = useAuth()
  const permissions = useMemo(
    () => new Set(user?.permissions ?? []),
    [user?.permissions],
  )
  const sections = useMemo(
    () => [
      ...(permissions.has('leave.types.view')
        ? [['types', 'Leave Types', SlidersHorizontal] as const]
        : []),
      ...(permissions.has('leave.balances.adjust')
        ? [['balances', 'Leave Balances', Users] as const]
        : []),
      ...(permissions.has('leave.types.view')
        ? [['periods', 'Leave Periods', CalendarRange] as const]
        : []),
      ...(permissions.has('leave.holidays.manage') ||
      permissions.has('leave.types.view')
        ? [['calendar', 'Holidays & Working Days', CalendarX2] as const]
        : []),
      ...(permissions.has('leave.reports.view')
        ? [['reports', 'Reports', BarChart3] as const]
        : []),
    ],
    [permissions],
  )
  const [section, setSection] = useState<AdminSection>(
    (sections[0]?.[0] as AdminSection | undefined) ?? 'types',
  )
  if (!sections.length)
    return (
      <div className="grid min-h-[60vh] place-items-center p-5 text-center sm:p-8">
        <div
          className="max-w-md rounded-2xl border bg-card p-8 shadow-sm"
          role="alert"
        >
          <ShieldAlert className="mx-auto size-10 text-primary" />
          <h1 className="mt-4 text-2xl font-semibold">Access denied</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            You do not have permission to manage leave configuration or reports.
          </p>
          <Link
            className="mt-5 inline-block rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
            to="/leave"
          >
            Return to My Leave
          </Link>
        </div>
      </div>
    )
  return (
    <div className="mx-auto max-w-[1540px] space-y-6 p-4 sm:p-6 lg:p-8">
      <PageHeader
        actions={
          <Link
            className="rounded-xl border bg-card px-4 py-2.5 text-sm font-semibold"
            to="/leave"
          >
            My Leave
          </Link>
        }
        description="Configure policy, maintain auditable balances, and monitor leave across your organization."
        eyebrow="People administration"
        title="Leave Administration"
      />
      <nav
        aria-label="Leave administration"
        className="flex gap-1 overflow-x-auto rounded-2xl border bg-card p-2 shadow-sm"
      >
        {sections.map(([value, label, Icon]) => (
          <button
            aria-current={section === value ? 'page' : undefined}
            className={`flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold ${section === value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
            key={value}
            onClick={() => setSection(value)}
            type="button"
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </nav>
      {section === 'types' && (
        <LeaveTypesPanel canManage={permissions.has('leave.types.manage')} />
      )}
      {section === 'balances' && <BalanceManagementPanel />}
      {section === 'periods' && (
        <LeavePeriodsPanel canManage={permissions.has('leave.types.manage')} />
      )}
      {section === 'calendar' && (
        <WorkingCalendarPanel
          canManage={
            permissions.has('leave.holidays.manage') ||
            permissions.has('leave.types.manage')
          }
        />
      )}
      {section === 'reports' && (
        <ReportsPanel canExport={permissions.has('leave.export')} />
      )}
    </div>
  )
}

function LeaveTypesPanel({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()
  const confirmation = useConfirmation()
  const [search, setSearch] = useState('')
  const [active, setActive] = useState<'all' | 'true' | 'false'>('all')
  const [editing, setEditing] = useState<LeaveType | 'new' | null>(null)
  const types = useQuery({
    queryKey: ['leave', 'types', search, active],
    queryFn: () =>
      leaveApi.types({
        search,
        active: active === 'all' ? undefined : active === 'true',
      }),
  })
  const toggle = useMutation({
    mutationFn: ({ item, next }: { item: LeaveType; next: boolean }) =>
      leaveApi.setTypeActive(item.id, next),
    onSuccess: () => client.invalidateQueries({ queryKey: ['leave', 'types'] }),
  })
  const toggleType = async (item: LeaveType) => {
    if (
      !item.is_active ||
      (await confirmation({
        title: `Deactivate ${item.name}?`,
        description:
          'Employees will no longer be able to create new requests for this leave type. Existing history remains unchanged.',
        confirmLabel: 'Deactivate',
        tone: 'danger',
      }))
    )
      toggle.mutate({ item, next: !item.is_active })
  }
  return (
    <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      <header className="flex flex-col gap-4 border-b p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Leave Types</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Policies employees see when requesting time away.
          </p>
        </div>
        {canManage && (
          <button
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
            onClick={() => setEditing('new')}
            type="button"
          >
            <Plus className="size-4" /> New leave type
          </button>
        )}
      </header>
      <div className="grid gap-3 border-b p-4 sm:grid-cols-[minmax(220px,1fr)_180px_auto]">
        <label className="relative">
          <span className="sr-only">Search leave types</span>
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <input
            className="w-full rounded-xl border bg-background py-2 pl-9 pr-3 text-sm"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name or code"
            value={search}
          />
        </label>
        <label>
          <span className="sr-only">Status filter</span>
          <select
            className="w-full rounded-xl border bg-background px-3 py-2 text-sm"
            onChange={(event) => setActive(event.target.value as typeof active)}
            value={active}
          >
            <option value="all">All statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </label>
        <button
          className="rounded-xl border px-3 py-2 text-sm font-semibold"
          onClick={() => {
            setSearch('')
            setActive('all')
          }}
          type="button"
        >
          Reset
        </button>
      </div>
      {types.isLoading ? (
        <div className="p-5">
          <LoadingState />
        </div>
      ) : types.isError || !types.data ? (
        <div className="p-5">
          <ErrorState retry={() => void types.refetch()} />
        </div>
      ) : types.data.length ? (
        <div className="grid gap-3 p-4 lg:grid-cols-2">
          {types.data.map((item) => (
            <article className="rounded-2xl border p-5" key={item.id}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3">
                  <span
                    className="size-3 shrink-0 rounded-full"
                    style={{ backgroundColor: item.color ?? '#64748b' }}
                  />
                  <div>
                    <h3 className="font-semibold">{item.name}</h3>
                    <p className="mt-0.5 text-xs uppercase tracking-wide text-muted-foreground">
                      {item.code} · {item.is_paid ? 'Paid' : 'Unpaid'}
                    </p>
                  </div>
                </div>
                <StatusBadge value={item.is_active ? 'active' : 'inactive'} />
              </div>
              <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">
                {item.description || 'No policy description provided.'}
              </p>
              <dl className="mt-4 grid grid-cols-2 gap-3 border-t pt-4 text-sm sm:grid-cols-4">
                <PolicyValue
                  label="Entitlement"
                  value={formatDays(Number(item.default_entitlement))}
                />
                <PolicyValue
                  label="Accrual"
                  value={
                    item.accrual_enabled
                      ? (item.accrual_frequency ?? 'Enabled')
                      : 'None'
                  }
                />
                <PolicyValue
                  label="Carryover"
                  value={
                    item.carryover_enabled
                      ? `Up to ${item.carryover_limit ?? 0}`
                      : 'None'
                  }
                />
                <PolicyValue
                  label="Documents"
                  value={item.attachment_required ? 'Required' : 'Optional'}
                />
              </dl>
              {canManage && (
                <div className="mt-4 flex gap-2">
                  <button
                    className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm font-semibold"
                    onClick={() => setEditing(item)}
                    type="button"
                  >
                    <Pencil className="size-3.5" /> Edit
                  </button>
                  <button
                    className="rounded-lg border px-3 py-1.5 text-sm font-semibold"
                    onClick={() => void toggleType(item)}
                    type="button"
                  >
                    {item.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <div className="p-5">
          <EmptyState
            detail="Create a policy employees can select when requesting leave."
            title="No leave types match these filters"
          />
        </div>
      )}
      {editing && (
        <LeaveTypeDialog
          item={editing === 'new' ? undefined : editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null)
            await client.invalidateQueries({ queryKey: ['leave', 'types'] })
          }}
        />
      )}
    </section>
  )
}

function PolicyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-semibold capitalize">{value}</dd>
    </div>
  )
}

function LeaveTypeDialog({
  item,
  onClose,
  onSaved,
}: {
  item?: LeaveType
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const [form, setForm] = useState({
    name: item?.name ?? '',
    code: item?.code ?? '',
    description: item?.description ?? '',
    is_active: item?.is_active ?? true,
    is_paid: item?.is_paid ?? true,
    default_entitlement: Number(item?.default_entitlement ?? 0),
    accrual_enabled: item?.accrual_enabled ?? false,
    accrual_frequency: item?.accrual_frequency ?? 'monthly',
    carryover_enabled: item?.carryover_enabled ?? false,
    carryover_limit: Number(item?.carryover_limit ?? 0),
    carryover_expiry_months: item?.carryover_expiry_months ?? 12,
    minimum_notice_days: item?.minimum_notice_days ?? 0,
    maximum_consecutive_days: item?.maximum_consecutive_days ?? '',
    attachment_required: item?.attachment_required ?? false,
    half_day_supported: item?.half_day_supported ?? false,
    eligible_employment_types: item?.eligible_employment_types ?? '',
    probation_eligible: item?.probation_eligible ?? true,
    color: item?.color ?? '#3b82f6',
  })
  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...form,
        accrual_frequency: form.accrual_enabled ? form.accrual_frequency : null,
        carryover_limit: form.carryover_enabled ? form.carryover_limit : null,
        carryover_expiry_months: form.carryover_enabled
          ? form.carryover_expiry_months
          : null,
        maximum_consecutive_days:
          form.maximum_consecutive_days === ''
            ? null
            : Number(form.maximum_consecutive_days),
        eligible_employment_types: form.eligible_employment_types
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
      }
      return item
        ? leaveApi.updateType(item.id, body)
        : leaveApi.createType(body)
    },
    onSuccess: onSaved,
  })
  const change = (name: keyof typeof form, value: string | number | boolean) =>
    setForm((current) => ({ ...current, [name]: value }))
  return (
    <Modal
      description="Policy sections reveal only the settings relevant to the options you enable."
      onClose={onClose}
      size="max-w-4xl"
      title={item ? `Edit ${item.name}` : 'Create leave type'}
    >
      <form
        className="space-y-6"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <FormSection title="Profile">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Name"
              onChange={(value) => change('name', value)}
              required
              value={form.name}
            />
            <TextField
              label="Code"
              onChange={(value) => change('code', value.toUpperCase())}
              required
              value={form.code}
            />
            <label className="text-sm font-medium sm:col-span-2">
              Description
              <textarea
                className="mt-1.5 min-h-20 w-full rounded-xl border bg-background p-3"
                onChange={(event) => change('description', event.target.value)}
                value={form.description}
              />
            </label>
            <TextField
              label="Brand color"
              onChange={(value) => change('color', value)}
              type="color"
              value={form.color}
            />
            <div className="flex flex-wrap gap-4 pt-6">
              <CheckField
                checked={form.is_paid}
                label="Paid leave"
                onChange={(value) => change('is_paid', value)}
              />
              <CheckField
                checked={form.is_active}
                label="Active"
                onChange={(value) => change('is_active', value)}
              />
            </div>
          </div>
        </FormSection>
        <FormSection title="Entitlement & accrual">
          <div className="grid gap-4 sm:grid-cols-3">
            <NumberField
              label="Default entitlement (days)"
              min={0}
              onChange={(value) => change('default_entitlement', value)}
              value={form.default_entitlement}
            />
            <div className="pt-7">
              <CheckField
                checked={form.accrual_enabled}
                label="Accrual enabled"
                onChange={(value) => change('accrual_enabled', value)}
              />
            </div>
            {form.accrual_enabled && (
              <label className="text-sm font-medium">
                Frequency
                <select
                  className="mt-1.5 w-full rounded-xl border bg-background px-3 py-2.5"
                  onChange={(event) =>
                    change('accrual_frequency', event.target.value)
                  }
                  value={form.accrual_frequency}
                >
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="yearly">Yearly</option>
                </select>
              </label>
            )}
          </div>
        </FormSection>
        <FormSection title="Carryover">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="pt-7">
              <CheckField
                checked={form.carryover_enabled}
                label="Carryover enabled"
                onChange={(value) => change('carryover_enabled', value)}
              />
            </div>
            {form.carryover_enabled && (
              <>
                <NumberField
                  label="Maximum carryover"
                  min={0}
                  onChange={(value) => change('carryover_limit', value)}
                  value={form.carryover_limit}
                />
                <NumberField
                  label="Expires after (months)"
                  min={1}
                  onChange={(value) => change('carryover_expiry_months', value)}
                  value={form.carryover_expiry_months}
                />
              </>
            )}
          </div>
        </FormSection>
        <FormSection title="Eligibility & request rules">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <TextField
              label="Employment types"
              onChange={(value) => change('eligible_employment_types', value)}
              placeholder="permanent, contract"
              value={form.eligible_employment_types}
            />
            <NumberField
              label="Minimum notice (days)"
              min={0}
              onChange={(value) => change('minimum_notice_days', value)}
              value={form.minimum_notice_days}
            />
            <TextField
              label="Maximum consecutive days"
              onChange={(value) => change('maximum_consecutive_days', value)}
              type="number"
              value={String(form.maximum_consecutive_days)}
            />
            <div className="flex flex-wrap gap-4 sm:col-span-2 lg:col-span-3">
              <CheckField
                checked={form.probation_eligible}
                label="Available during probation"
                onChange={(value) => change('probation_eligible', value)}
              />
              <CheckField
                checked={form.half_day_supported}
                label="Half days supported"
                onChange={(value) => change('half_day_supported', value)}
              />
              <CheckField
                checked={form.attachment_required}
                label="Supporting document required"
                onChange={(value) => change('attachment_required', value)}
              />
            </div>
          </div>
        </FormSection>
        {save.error && (
          <p
            className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive"
            role="alert"
          >
            {save.error.message}
          </p>
        )}
        <footer className="flex justify-end gap-2 border-t pt-5">
          <button
            className="rounded-xl border px-4 py-2.5 text-sm font-semibold"
            onClick={onClose}
            type="button"
          >
            Cancel
          </button>
          <button
            className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={save.isPending || !form.name || !form.code}
            type="submit"
          >
            {save.isPending
              ? 'Saving…'
              : item
                ? 'Save policy'
                : 'Create policy'}
          </button>
        </footer>
      </form>
    </Modal>
  )
}

function FormSection({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <fieldset className="rounded-2xl border p-4">
      <legend className="px-2 text-sm font-semibold">{title}</legend>
      {children}
    </fieldset>
  )
}
function TextField({
  label,
  value,
  onChange,
  required = false,
  type = 'text',
  placeholder,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  required?: boolean
  type?: string
  placeholder?: string
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <input
        className="mt-1.5 w-full rounded-xl border bg-background px-3 py-2.5"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        type={type}
        value={value}
      />
    </label>
  )
}
function NumberField({
  label,
  value,
  onChange,
  min,
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <input
        className="mt-1.5 w-full rounded-xl border bg-background px-3 py-2.5"
        min={min}
        onChange={(event) => onChange(Number(event.target.value))}
        step="0.5"
        type="number"
        value={value}
      />
    </label>
  )
}
function CheckField({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label className="flex items-center gap-2 text-sm font-medium">
      <input
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />{' '}
      {label}
    </label>
  )
}

function BalanceManagementPanel() {
  const [search, setSearch] = useState('')
  const [employee, setEmployee] = useState('')
  const [department, setDepartment] = useState('')
  const [leaveType, setLeaveType] = useState('')
  const [period, setPeriod] = useState('')
  const [sort, setSort] = useState('employee')
  const [page, setPage] = useState(1)
  const [adjusting, setAdjusting] = useState<LeaveBalanceRow | null>(null)
  const [history, setHistory] = useState<LeaveBalanceRow | null>(null)
  const types = useQuery({
    queryKey: ['leave', 'types', 'balance'],
    queryFn: () => leaveApi.types(),
  })
  const periods = useQuery({
    queryKey: ['leave', 'periods'],
    queryFn: leaveApi.periods,
  })
  const employees = useQuery({
    queryKey: ['leave', 'employees'],
    queryFn: () =>
      userAdminApi.employees({
        page: 1,
        page_size: 100,
        employment_status: 'active',
      }),
  })
  const departments = useQuery({
    queryKey: ['leave', 'departments'],
    queryFn: () =>
      organizationApi.departments({
        status: 'active',
        page: 1,
        page_size: 100,
      }),
  })
  const filters = {
    search,
    employee_id: employee,
    department_id: department,
    leave_type_id: leaveType,
    leave_period_id: period,
    sort_by: sort,
    page,
    page_size: 25,
  }
  const balances = useQuery({
    queryKey: ['leave', 'balances', filters],
    queryFn: () => leaveApi.balances(filters),
  })
  const reset = () => {
    setSearch('')
    setEmployee('')
    setDepartment('')
    setLeaveType('')
    setPeriod('')
    setSort('employee')
    setPage(1)
  }
  return (
    <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b p-5">
        <div>
          <h2 className="text-lg font-semibold">Leave Balance Management</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Find an employee quickly, then inspect or adjust their immutable
            ledger.
          </p>
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold"
          onClick={() => void leaveApi.exportBalances(filters)}
          type="button"
        >
          <Download className="size-4" /> Export CSV
        </button>
      </header>
      <div className="grid gap-3 border-b p-4 md:grid-cols-2 xl:grid-cols-6">
        <label className="relative xl:col-span-2">
          <span className="sr-only">Search balances</span>
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <input
            className="w-full rounded-xl border bg-background py-2 pl-9 pr-3 text-sm"
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
            placeholder="Search name or employee number"
            value={search}
          />
        </label>
        <FilterSelect
          label="Employee"
          onChange={(value) => {
            setEmployee(value)
            setPage(1)
          }}
          value={employee}
        >
          <option value="">All employees</option>
          {employees.data?.items.map((person) => (
            <option key={person.id} value={person.id}>
              {person.display_name}
              {person.employee_number ? ` · ${person.employee_number}` : ''}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect
          label="Department"
          onChange={(value) => {
            setDepartment(value)
            setPage(1)
          }}
          value={department}
        >
          <option value="">All departments</option>
          {departments.data?.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect
          label="Leave type"
          onChange={(value) => {
            setLeaveType(value)
            setPage(1)
          }}
          value={leaveType}
        >
          <option value="">All leave types</option>
          {types.data?.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect
          label="Period"
          onChange={(value) => {
            setPeriod(value)
            setPage(1)
          }}
          value={period}
        >
          <option value="">All periods</option>
          {periods.data?.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect label="Sort" onChange={setSort} value={sort}>
          <option value="employee">Employee</option>
          <option value="department">Department</option>
          <option value="leave_type">Leave type</option>
          <option value="period">Period</option>
          <option value="available">Available</option>
        </FilterSelect>
        <button
          className="rounded-xl border px-3 py-2 text-sm font-semibold"
          onClick={reset}
          type="button"
        >
          Reset filters
        </button>
      </div>
      {balances.isLoading ? (
        <div className="p-5">
          <LoadingState label="Loading leave balances" />
        </div>
      ) : balances.isError || !balances.data ? (
        <div className="p-5">
          <ErrorState retry={() => void balances.refetch()} />
        </div>
      ) : balances.data.items.length ? (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1120px] text-left text-sm">
              <thead className="bg-muted/45 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  {[
                    'Employee',
                    'Department',
                    'Leave Type',
                    'Entitled',
                    'Accrued',
                    'Carryover',
                    'Used',
                    'Pending',
                    'Expired',
                    'Available',
                    'Actions',
                  ].map((label) => (
                    <th
                      className="px-4 py-3 font-semibold"
                      key={label}
                      scope="col"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {balances.data.items.map((row) => (
                  <tr className="hover:bg-muted/30" key={row.entitlement_id}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <PersonMark name={row.employee_name} />
                        <div>
                          <p className="font-semibold">{row.employee_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {row.employee_number || 'No employee number'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">{row.department_name || '—'}</td>
                    <td className="px-4 py-3">
                      <p className="font-semibold">{row.leave_type_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {row.period_name}
                      </p>
                    </td>
                    {[
                      row.entitled,
                      row.accrued,
                      row.carried_forward,
                      row.used,
                      row.pending,
                      row.expired,
                    ].map((value, index) => (
                      <td className="px-4 py-3 tabular-nums" key={index}>
                        {Number(value)}
                      </td>
                    ))}
                    <td className="px-4 py-3 text-base font-bold tabular-nums">
                      {Number(row.available)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          aria-label={`View ${row.employee_name} balance history`}
                          className="rounded-lg border p-2"
                          onClick={() => setHistory(row)}
                          title="View history"
                          type="button"
                        >
                          <History className="size-4" />
                        </button>
                        <button
                          aria-label={`Adjust ${row.employee_name} balance`}
                          className="rounded-lg border p-2"
                          onClick={() => setAdjusting(row)}
                          title="Adjust balance"
                          type="button"
                        >
                          <Settings2 className="size-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            onPage={setPage}
            page={page}
            pageSize={25}
            total={balances.data.total}
          />
        </>
      ) : (
        <div className="p-5">
          <EmptyState
            detail="Try removing one or more filters."
            title="No leave balance records match these filters"
          />
        </div>
      )}
      {adjusting && (
        <AdjustmentDialog onClose={() => setAdjusting(null)} row={adjusting} />
      )}
      {history && (
        <AdminBalanceHistoryDialog
          onClose={() => setHistory(null)}
          row={history}
        />
      )}
    </section>
  )
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  children: React.ReactNode
}) {
  return (
    <label>
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        className="w-full rounded-xl border bg-background px-3 py-2 text-sm"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {children}
      </select>
    </label>
  )
}

function AdjustmentDialog({
  row,
  onClose,
}: {
  row: LeaveBalanceRow
  onClose: () => void
}) {
  const client = useQueryClient()
  const confirmation = useConfirmation()
  const [operation, setOperation] = useState<'add' | 'deduct' | 'correction'>(
    'add',
  )
  const [amount, setAmount] = useState(1)
  const [effectiveDate, setEffectiveDate] = useState(
    new Date().toISOString().slice(0, 10),
  )
  const [reason, setReason] = useState('')
  const signed = operation === 'deduct' ? -Math.abs(amount) : amount
  const result = Number(row.available) + signed
  const adjust = useMutation({
    mutationFn: () =>
      leaveApi.adjust({
        operation,
        amount,
        effective_date: effectiveDate,
        reason,
        employee_id: row.employee_id,
        leave_type_id: row.leave_type_id,
        leave_period_id: row.leave_period_id,
      }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['leave', 'balances'] })
      onClose()
    },
  })
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (
      await confirmation({
        title: `Adjust ${row.employee_name}’s balance?`,
        description: `${row.leave_type_name} will change from ${formatDays(Number(row.available))} to approximately ${formatDays(result)}. The ledger entry cannot be edited or deleted.`,
        confirmLabel: 'Record adjustment',
        tone: result < 0 ? 'danger' : 'primary',
      })
    )
      adjust.mutate()
  }
  return (
    <Modal
      description="Every change creates an immutable ledger and audit entry."
      onClose={onClose}
      title="Adjust leave balance"
    >
      <form className="space-y-5" onSubmit={(event) => void submit(event)}>
        <section className="rounded-2xl bg-muted/45 p-4">
          <p className="font-semibold">{row.employee_name}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {row.leave_type_name} · {row.period_name}
          </p>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <PolicyValue
              label="Current"
              value={formatDays(Number(row.available))}
            />
            <PolicyValue
              label="Adjustment"
              value={`${signed > 0 ? '+' : ''}${formatDays(signed)}`}
            />
            <PolicyValue label="Result" value={formatDays(result)} />
          </div>
        </section>
        <div className="grid gap-4 sm:grid-cols-3">
          <FilterSelect
            label="Adjustment type"
            onChange={(value) => setOperation(value as typeof operation)}
            value={operation}
          >
            <option value="add">Add</option>
            <option value="deduct">Deduct</option>
            <option value="correction">Correction</option>
          </FilterSelect>
          <NumberField
            label="Amount"
            min={0.5}
            onChange={setAmount}
            value={amount}
          />
          <TextField
            label="Effective date"
            onChange={setEffectiveDate}
            required
            type="date"
            value={effectiveDate}
          />
        </div>
        <label className="block text-sm font-medium">
          Reason
          <textarea
            className="mt-1.5 min-h-24 w-full rounded-xl border bg-background p-3"
            onChange={(event) => setReason(event.target.value)}
            required
            value={reason}
          />
        </label>
        {adjust.error && (
          <p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
            {adjust.error.message}
          </p>
        )}
        <footer className="flex justify-end gap-2 border-t pt-4">
          <button
            className="rounded-xl border px-4 py-2.5 text-sm font-semibold"
            onClick={onClose}
            type="button"
          >
            Cancel
          </button>
          <button
            className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={!reason.trim() || !amount || adjust.isPending}
            type="submit"
          >
            Record adjustment
          </button>
        </footer>
      </form>
    </Modal>
  )
}

function AdminBalanceHistoryDialog({
  row,
  onClose,
}: {
  row: LeaveBalanceRow
  onClose: () => void
}) {
  const history = useQuery({
    queryKey: ['leave', 'ledger', row.entitlement_id],
    queryFn: () =>
      leaveApi.ledger({
        employee_id: row.employee_id,
        leave_type_id: row.leave_type_id,
        leave_period_id: row.leave_period_id,
        page: 1,
        page_size: 100,
      }),
  })
  return (
    <Modal
      description={`${row.employee_name} · ${row.leave_type_name} · ${row.period_name}`}
      onClose={onClose}
      size="max-w-3xl"
      title="Balance history"
    >
      {history.isLoading ? (
        <LoadingState />
      ) : history.isError || !history.data ? (
        <ErrorState retry={() => void history.refetch()} />
      ) : history.data.items.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b text-xs uppercase text-muted-foreground">
                {[
                  'Date',
                  'Entry type',
                  'Amount',
                  'Reason',
                  'Actor',
                  'Recorded',
                ].map((label) => (
                  <th className="px-3 py-2" key={label}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {history.data.items.map((entry) => (
                <tr key={entry.id}>
                  <td className="px-3 py-3">
                    {formatDay(entry.effective_date)}
                  </td>
                  <td className="px-3 py-3 font-semibold capitalize">
                    {entry.entry_type.replaceAll('_', ' ')}
                  </td>
                  <td
                    className={`px-3 py-3 font-semibold ${Number(entry.amount) >= 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}`}
                  >
                    {Number(entry.amount) > 0 ? '+' : ''}
                    {Number(entry.amount)}
                  </td>
                  <td className="max-w-72 px-3 py-3 text-muted-foreground">
                    {entry.reason || '—'}
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">
                    {entry.actor_name || 'System'}
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">
                    {formatDateTime(entry.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          detail="Ledger entries appear after allocation, usage, or adjustment."
          title="No balance history"
        />
      )}
    </Modal>
  )
}

function LeavePeriodsPanel({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()
  const confirmation = useConfirmation()
  const [creating, setCreating] = useState(false)
  const periods = useQuery({
    queryKey: ['leave', 'periods'],
    queryFn: leaveApi.periods,
  })
  const changeStatus = useMutation({
    mutationFn: ({
      item,
      status,
    }: {
      item: LeavePeriod
      status: 'open' | 'closed'
    }) => leaveApi.setPeriodStatus(item.id, status),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ['leave', 'periods'] }),
  })
  const toggle = async (item: LeavePeriod) => {
    const status = item.status === 'open' ? 'closed' : 'open'
    if (
      await confirmation({
        title: `${status === 'closed' ? 'Close' : 'Reopen'} ${item.name}?`,
        description:
          status === 'closed'
            ? 'New leave requests cannot use this period after it closes.'
            : 'The period will become available for eligible requests again.',
        confirmLabel: status === 'closed' ? 'Close period' : 'Reopen period',
        tone: status === 'closed' ? 'danger' : 'primary',
      })
    )
      changeStatus.mutate({ item, status })
  }
  return (
    <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      <header className="flex items-center justify-between gap-3 border-b p-5">
        <div>
          <h2 className="text-lg font-semibold">Leave Periods</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Control the time boundaries used for entitlements and requests.
          </p>
        </div>
        {canManage && (
          <button
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
            onClick={() => setCreating(true)}
            type="button"
          >
            <Plus className="size-4" /> New period
          </button>
        )}
      </header>
      {periods.isLoading ? (
        <div className="p-5">
          <LoadingState />
        </div>
      ) : periods.isError || !periods.data ? (
        <div className="p-5">
          <ErrorState retry={() => void periods.refetch()} />
        </div>
      ) : periods.data.length ? (
        <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
          {periods.data.map((item) => (
            <article
              className={`rounded-2xl border p-5 ${item.status === 'open' ? 'border-primary/40' : ''}`}
              key={item.id}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold">{item.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {formatDay(item.start_date)} – {formatDay(item.end_date)}
                  </p>
                </div>
                <StatusBadge value={item.status} />
              </div>
              {item.status === 'open' && (
                <p className="mt-4 rounded-xl bg-primary/10 px-3 py-2 text-xs font-semibold text-primary">
                  Current/open period
                </p>
              )}
              {canManage && (
                <button
                  className="mt-4 rounded-lg border px-3 py-1.5 text-sm font-semibold"
                  onClick={() => void toggle(item)}
                  type="button"
                >
                  {item.status === 'open' ? 'Close period' : 'Reopen period'}
                </button>
              )}
            </article>
          ))}
        </div>
      ) : (
        <div className="p-5">
          <EmptyState
            detail="Create the organization’s first entitlement period."
            title="No leave periods configured"
          />
        </div>
      )}
      {creating && (
        <PeriodDialog
          onClose={() => setCreating(false)}
          onSaved={async () => {
            setCreating(false)
            await client.invalidateQueries({ queryKey: ['leave', 'periods'] })
          }}
        />
      )}
    </section>
  )
}

function PeriodDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const [name, setName] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const create = useMutation({
    mutationFn: () =>
      leaveApi.createPeriod({
        name,
        start_date: start,
        end_date: end,
        status: 'open',
      }),
    onSuccess: onSaved,
  })
  return (
    <Modal
      description="Periods cannot overlap an existing leave period."
      onClose={onClose}
      title="Create leave period"
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <TextField
          label="Period name"
          onChange={setName}
          required
          value={name}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Start date"
            onChange={setStart}
            required
            type="date"
            value={start}
          />
          <TextField
            label="End date"
            onChange={setEnd}
            required
            type="date"
            value={end}
          />
        </div>
        {create.error && (
          <p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
            {create.error.message}
          </p>
        )}
        <footer className="flex justify-end gap-2 border-t pt-4">
          <button
            className="rounded-xl border px-4 py-2.5 text-sm font-semibold"
            onClick={onClose}
            type="button"
          >
            Cancel
          </button>
          <button
            className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={
              !name || !start || !end || end < start || create.isPending
            }
            type="submit"
          >
            Create period
          </button>
        </footer>
      </form>
    </Modal>
  )
}

function WorkingCalendarPanel({ canManage }: { canManage: boolean }) {
  const client = useQueryClient()
  const [holidayOpen, setHolidayOpen] = useState(false)
  const week = useQuery({
    queryKey: ['leave', 'working-week'],
    queryFn: leaveApi.workingWeek,
  })
  const holidays = useQuery({
    queryKey: ['calendar-holidays'],
    queryFn: calendarApi.holidays,
  })
  const updateWeek = useMutation({
    mutationFn: leaveApi.updateWorkingWeek,
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ['leave', 'working-week'] }),
  })
  const names = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
  ]
  if (week.isLoading || holidays.isLoading) return <LoadingState />
  if (week.isError || holidays.isError || !week.data || !holidays.data)
    return (
      <ErrorState
        retry={() => {
          void week.refetch()
          void holidays.refetch()
        }}
      />
    )
  const toggleDay = (day: number) => {
    const current = week.data!
    const weekdays = current.weekdays.includes(day)
      ? current.weekdays.filter((value) => value !== day)
      : [...current.weekdays, day].sort()
    if (weekdays.length) updateWeek.mutate({ ...current, weekdays })
  }
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_1.25fr]">
      <section className="rounded-2xl border bg-card p-5 shadow-sm">
        <h2 className="text-lg font-semibold">Working week</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          One canonical schedule controls chargeable leave days.
        </p>
        <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-2 2xl:grid-cols-4">
          {names.map((name, day) => (
            <button
              aria-pressed={week.data!.weekdays.includes(day)}
              className={`rounded-xl border p-3 text-left text-sm font-semibold ${week.data!.weekdays.includes(day) ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground'}`}
              disabled={!canManage}
              key={name}
              onClick={() => toggleDay(day)}
              type="button"
            >
              {name}
            </button>
          ))}
        </div>
        <label className="mt-5 flex items-center gap-3 rounded-xl border p-4 text-sm font-medium">
          <input
            checked={week.data.exclude_holidays}
            disabled={!canManage}
            onChange={(event) =>
              updateWeek.mutate({
                ...week.data!,
                exclude_holidays: event.target.checked,
              })
            }
            type="checkbox"
          />{' '}
          Exclude public holidays from chargeable leave
        </label>
      </section>
      <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
        <header className="flex items-center justify-between border-b p-5">
          <div>
            <h2 className="text-lg font-semibold">Public holidays</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Shared with the organization Calendar.
            </p>
          </div>
          {canManage && (
            <button
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
              onClick={() => setHolidayOpen(true)}
              type="button"
            >
              <Plus className="size-4" /> Add holiday
            </button>
          )}
        </header>
        {holidays.data.length ? (
          <div className="divide-y">
            {holidays.data.map((holiday) => (
              <div
                className="flex items-center justify-between gap-3 p-4"
                key={holiday.id}
              >
                <div>
                  <p className="font-semibold">{holiday.name}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {formatDay(holiday.date)}
                    {holiday.recurring ? ' · Repeats yearly' : ''}
                  </p>
                </div>
                {canManage && (
                  <button
                    className="rounded-lg border px-3 py-1.5 text-sm font-semibold text-destructive"
                    onClick={() =>
                      void calendarApi.deleteHoliday(holiday.id).then(() =>
                        client.invalidateQueries({
                          queryKey: ['calendar-holidays'],
                        }),
                      )
                    }
                    type="button"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="p-5">
            <EmptyState
              detail="Add organization holidays to exclude them from working-day calculations."
              title="No public holidays configured"
            />
          </div>
        )}
      </section>
      {holidayOpen && (
        <HolidayDialog
          onClose={() => setHolidayOpen(false)}
          onSaved={async () => {
            setHolidayOpen(false)
            await client.invalidateQueries({ queryKey: ['calendar-holidays'] })
          }}
        />
      )}
    </div>
  )
}

function HolidayDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const [name, setName] = useState('')
  const [date, setDate] = useState('')
  const [recurring, setRecurring] = useState(false)
  const create = useMutation({
    mutationFn: () => calendarApi.createHoliday({ name, date, recurring }),
    onSuccess: onSaved,
  })
  return (
    <Modal
      description="The holiday is shared with Calendar and Leave working-day calculations."
      onClose={onClose}
      title="Add public holiday"
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <TextField
          label="Holiday name"
          onChange={setName}
          required
          value={name}
        />
        <TextField
          label="Date"
          onChange={setDate}
          required
          type="date"
          value={date}
        />
        <CheckField
          checked={recurring}
          label="Repeat every year"
          onChange={setRecurring}
        />
        {create.error && (
          <p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
            {create.error.message}
          </p>
        )}
        <footer className="flex justify-end gap-2 border-t pt-4">
          <button
            className="rounded-xl border px-4 py-2.5 text-sm font-semibold"
            onClick={onClose}
            type="button"
          >
            Cancel
          </button>
          <button
            className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
            disabled={!name || !date || create.isPending}
            type="submit"
          >
            Add holiday
          </button>
        </footer>
      </form>
    </Modal>
  )
}

function ReportsPanel({ canExport }: { canExport: boolean }) {
  const [report, setReport] = useState<
    'department' | 'leave_type' | 'pending' | 'current' | 'upcoming' | 'all'
  >('department')
  const isUsage = report === 'department' || report === 'leave_type'
  const usage = useQuery({
    queryKey: ['leave', 'report', report],
    queryFn: () => leaveApi.usageReport(report as 'department' | 'leave_type'),
    enabled: isUsage,
  })
  const status = useQuery({
    queryKey: ['leave', 'report', report],
    queryFn: () =>
      leaveApi.statusReport(
        report as 'pending' | 'current' | 'upcoming' | 'all',
      ),
    enabled: !isUsage,
  })
  const rows = isUsage ? usage.data : status.data
  const loading = isUsage ? usage.isLoading : status.isLoading
  const error = isUsage ? usage.isError : status.isError
  const options: Array<[typeof report, string]> = [
    ['department', 'Usage by Department'],
    ['leave_type', 'Usage by Leave Type'],
    ['pending', 'Pending Requests'],
    ['current', 'Currently on Leave'],
    ['upcoming', 'Upcoming Leave'],
    ['all', 'Balance Summary'],
  ]
  return (
    <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      <header className="flex flex-col gap-4 border-b p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Leave Reports</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Decision-oriented summaries from live organization records.
          </p>
        </div>
        {canExport && isUsage && (
          <button
            className="inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold"
            onClick={() =>
              void leaveApi.exportUsage(report as 'department' | 'leave_type')
            }
            type="button"
          >
            <Download className="size-4" /> Export CSV
          </button>
        )}
      </header>
      <div className="flex gap-2 overflow-x-auto border-b p-3">
        {options.map(([value, label]) => (
          <button
            className={`shrink-0 rounded-xl px-3 py-2 text-sm font-semibold ${report === value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
            key={value}
            onClick={() => setReport(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>
      {loading ? (
        <div className="p-5">
          <LoadingState label="Loading report" />
        </div>
      ) : error ? (
        <div className="p-5">
          <ErrorState
            retry={() => void (isUsage ? usage.refetch() : status.refetch())}
          />
        </div>
      ) : rows?.length ? (
        <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
          {rows.map((row) => (
            <article
              className="rounded-2xl border p-5"
              key={'key' in row ? row.key : row.status}
            >
              <p className="text-sm font-semibold">
                {'label' in row ? row.label : row.status.replaceAll('_', ' ')}
              </p>
              <div className="mt-4 flex items-end justify-between gap-3">
                <div>
                  <p className="text-3xl font-semibold">{row.request_count}</p>
                  <p className="text-xs text-muted-foreground">requests</p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-semibold">
                    {Number(row.total_days)}
                  </p>
                  <p className="text-xs text-muted-foreground">leave days</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="p-5">
          <EmptyState
            detail="This report will populate from submitted and approved leave records."
            title="No report data is available"
          />
        </div>
      )}
    </section>
  )
}
