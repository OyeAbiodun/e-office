import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'

import { PayrollPage } from '@/features/payroll/payroll-page'
import { payrollMoney } from '@/features/payroll/api'

const mocks = vi.hoisted(() => ({
  permissions: ['payroll.view_own', 'payroll.payslip.download_own'],
  periods: vi.fn(),
  runs: vi.fn(),
  payslips: vi.fn(),
  structures: vi.fn(),
  employees: vi.fn(),
  components: vi.fn(),
  statutory: vi.fn(),
  loans: vi.fn(),
  reports: vi.fn(),
}))

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({ user: { permissions: mocks.permissions } }),
}))
vi.mock('@/components/feedback/confirmation', () => ({
  useConfirmation: () => vi.fn().mockResolvedValue(true),
}))
vi.mock('@/features/finance/api', () => ({
  financeApi: { accounts: vi.fn().mockResolvedValue([]) },
}))
vi.mock('@/features/payroll/api', async (original) => {
  const actual = await original<typeof import('@/features/payroll/api')>()
  return {
    ...actual,
    payrollApi: {
      periods: mocks.periods,
      runs: mocks.runs,
      payslips: mocks.payslips,
      structures: mocks.structures,
      employees: mocks.employees,
      components: mocks.components,
      statutory: mocks.statutory,
      loans: mocks.loans,
      createPeriod: vi.fn(),
      prepare: vi.fn(),
      run: vi.fn(),
      action: vi.fn(),
      createStructure: vi.fn(),
      previewStructure: vi.fn(),
      createComponent: vi.fn(),
      updateComponent: vi.fn(),
      createStatutory: vi.fn(),
      createLoan: vi.fn(),
      endStructure: vi.fn(),
      createAdjustment: vi.fn(),
      result: vi.fn(),
      reports: mocks.reports,
    },
    downloadPayroll: vi.fn(),
  }
})

function renderPage(node: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.permissions = ['payroll.view_own', 'payroll.payslip.download_own']
  mocks.periods.mockResolvedValue([])
  mocks.runs.mockResolvedValue([])
  mocks.payslips.mockResolvedValue([
    {
      id: 'result-1',
      employee_name: 'Ada Employee',
      currency: 'NGN',
      gross_pay: '125000.50',
      total_deductions: '25000.10',
      net_pay: '100000.40',
    },
  ])
  mocks.structures.mockResolvedValue([])
  mocks.employees.mockResolvedValue([])
  mocks.components.mockResolvedValue([])
  mocks.statutory.mockResolvedValue([])
  mocks.loans.mockResolvedValue([])
  mocks.reports.mockResolvedValue([])
})

it('shows employees only their own secure payslips', async () => {
  renderPage(<PayrollPage />)
  expect(await screen.findByText('Latest payslip')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'My payslips' }))
  expect(await screen.findByText('Ada Employee')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: /new period/i }),
  ).not.toBeInTheDocument()
})

it('shows permission-aware payroll administration sections', async () => {
  mocks.permissions = [
    'payroll.periods.view',
    'payroll.periods.manage',
    'payroll.salary_structure.view',
  ]
  renderPage(<PayrollPage />)
  expect(await screen.findByText('Payroll overview')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Payroll runs' }))
  expect(await screen.findByText(/no payroll periods yet/i)).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: /new period/i }),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Salary structures' }))
  expect(
    await screen.findByText('Effective-dated salary structures'),
  ).toBeInTheDocument()
})

it('formats decimal payroll amounts without floating point loss', () => {
  expect(payrollMoney('9007199254740993.5', 'NGN')).toBe(
    'NGN 9,007,199,254,740,993.50',
  )
})

it('shows payroll reports only when the report permission is granted', async () => {
  mocks.permissions = ['payroll.periods.view', 'payroll.reports.view']
  renderPage(<PayrollPage />)
  await screen.findByText('Payroll overview')
  fireEvent.click(screen.getByRole('button', { name: 'Reports' }))
  expect(
    await screen.findByText(/select a payroll run to view/i),
  ).toBeInTheDocument()
})
