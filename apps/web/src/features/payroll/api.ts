import { apiRawRequest, apiRequest } from '@/features/auth/api'

export interface PayrollEmployee {
  id: string
  display_name: string
  employee_number: string | null
  department: string | null
  job_title: string | null
  employment_status: string
}
export interface SalaryComponent {
  id: string
  code: string
  name: string
  description: string | null
  component_kind: 'earning' | 'deduction'
  calculation_type: 'fixed' | 'percentage'
  taxable: boolean
  pensionable: boolean
  recurring: boolean
  is_active: boolean
  effective_start: string
  effective_end: string | null
}
export interface SalaryStructure {
  id: string
  employee_id: string
  employee_name: string | null
  currency: string
  basic_salary: string
  gross_salary: string
  effective_start: string
  effective_end: string | null
  status: string
  change_reason: string
  changed_by_name: string | null
  created_at: string
  items: Array<{
    id: string
    component_name: string | null
    amount: string
    percentage: string
  }>
}
export interface PayrollPeriod {
  id: string
  name: string
  start_date: string
  end_date: string
  payment_date: string
  currency: string
  status: string
  locked: boolean
}
export interface PayrollRun {
  id: string
  period_id: string
  status: string
  version: number
  prepared_at: string | null
  submitted_at: string | null
  approved_at: string | null
  paid_at: string | null
  closed_at: string | null
  return_reason: string | null
}
export interface PayrollResult {
  id: string
  employee_id: string
  employee_name: string
  employee_number: string | null
  department_name: string | null
  job_title: string | null
  period_name: string | null
  period_start: string | null
  period_end: string | null
  payment_date: string | null
  currency: string
  status: string
  gross_pay: string
  basic_salary: string
  allowances: string
  variable_earnings: string
  taxable_pay: string
  paye: string
  pension_employee: string
  pension_employer: string
  nhf: string
  loan_deductions: string
  other_deductions: string
  total_deductions: string
  net_pay: string
  employer_cost: string
  proration_factor: string
  calculation_snapshot: Record<string, unknown>
  exceptions: Array<Record<string, unknown>>
  items: Array<{
    id: string
    code: string
    name: string
    category: string
    amount: string
    taxable: boolean
    pensionable: boolean
    basis: string | null
    position: number
  }>
}
export interface RunDetail {
  run: PayrollRun
  period: PayrollPeriod
  summary: {
    employee_count: number
    exception_count: number
    currency: string
    gross_payroll: string
    paye: string
    pension_employee: string
    pension_employer: string
    nhf: string
    loan_deductions: string
    other_deductions: string
    total_deductions: string
    net_payroll: string
    employer_cost: string
  }
  results: {
    items: PayrollResult[]
    total: number
    page: number
    page_size: number
    total_pages: number
  }
  history: Array<Record<string, unknown>>
  allowed_actions: string[]
}
export interface PayrollLoan {
  id: string
  employee_id: string
  principal: string
  repayment_amount: string
  outstanding_balance: string
  start_date: string
  status: string
  reason: string
}
export interface StatutoryConfiguration {
  id: string
  configuration_type: string
  name: string
  effective_start: string
  effective_end: string | null
  is_active: boolean
  change_reason: string
}
export interface PayrollReportRow {
  group: string
  employee_count: number
  gross_pay: string
  paye: string
  pension: string
  nhf: string
  deductions: string
  net_pay: string
  employer_cost: string
}

export interface PayrollRunFilters {
  page?: number
  pageSize?: number
  search?: string
  exceptionOnly?: boolean
  sort?: 'employee' | 'gross' | 'net' | 'department' | 'status'
  direction?: 'asc' | 'desc'
}

const get = <T>(path: string) => apiRequest<T>(path, {}, true)
const post = <T>(path: string, body: unknown = {}) =>
  apiRequest<T>(path, { method: 'POST', body: JSON.stringify(body) }, true)
export const payrollApi = {
  employees: () => get<PayrollEmployee[]>('/payroll/employees'),
  components: () => get<SalaryComponent[]>('/payroll/components'),
  createComponent: (body: unknown) =>
    post<SalaryComponent>('/payroll/components', body),
  updateComponent: (id: string, body: unknown) =>
    apiRequest<SalaryComponent>(
      `/payroll/components/${id}`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  structures: () => get<SalaryStructure[]>('/payroll/salary-structures'),
  createStructure: (body: unknown) =>
    post<SalaryStructure>('/payroll/salary-structures', body),
  previewStructure: (body: unknown) =>
    post<Record<string, string>>('/payroll/salary-structures/preview', body),
  endStructure: (id: string, body: unknown) =>
    post<SalaryStructure>(`/payroll/salary-structures/${id}/end`, body),
  periods: () => get<PayrollPeriod[]>('/payroll/periods'),
  createPeriod: (body: unknown) =>
    post<PayrollPeriod>('/payroll/periods', body),
  prepare: (periodId: string) =>
    post<PayrollRun>(`/payroll/periods/${periodId}/prepare`),
  createAdjustment: (periodId: string, body: unknown) =>
    post<{ id: string; status: string; amount: string }>(
      `/payroll/periods/${periodId}/adjustments`,
      body,
    ),
  runs: () => get<PayrollRun[]>('/payroll/runs'),
  run: (id: string, filters: PayrollRunFilters = {}) => {
    const params = new URLSearchParams({
      page: String(filters.page ?? 1),
      page_size: String(filters.pageSize ?? 25),
      sort: filters.sort ?? 'employee',
      direction: filters.direction ?? 'asc',
    })
    if (filters.search?.trim()) params.set('search', filters.search.trim())
    if (filters.exceptionOnly) params.set('exception_only', 'true')
    return get<RunDetail>(`/payroll/runs/${id}?${params}`)
  },
  result: (id: string) => get<PayrollResult>(`/payroll/results/${id}`),
  reports: (id: string) =>
    get<PayrollReportRow[]>(`/payroll/runs/${id}/reports`),
  action: (id: string, action: string, body: unknown = {}) =>
    post<PayrollRun>(`/payroll/runs/${id}/${action}`, body),
  statutory: () => get<StatutoryConfiguration[]>('/payroll/statutory'),
  createStatutory: (body: unknown) =>
    post<StatutoryConfiguration>('/payroll/statutory', body),
  loans: () => get<PayrollLoan[]>('/payroll/loans'),
  createLoan: (body: unknown) => post<PayrollLoan>('/payroll/loans', body),
  payslips: () => get<PayrollResult[]>('/payroll/my/payslips'),
}
export async function downloadPayroll(path: string, filename: string) {
  const response = await apiRawRequest(path)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function payrollMoney(value: string, currency = 'NGN') {
  const [whole, fraction = ''] = value.split('.')
  return `${currency} ${BigInt(whole || '0').toLocaleString()}.${fraction.padEnd(2, '0').slice(0, 2)}`
}
