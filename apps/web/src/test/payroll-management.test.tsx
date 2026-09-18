import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
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
  run: vi.fn(),
  updateComponent: vi.fn(),
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
      run: mocks.run,
      action: vi.fn(),
      createStructure: vi.fn(),
      previewStructure: vi.fn(),
      createComponent: vi.fn(),
      updateComponent: mocks.updateComponent,
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
  mocks.run.mockResolvedValue(undefined)
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
  mocks.updateComponent.mockResolvedValue({})
})

it('shows employees only their own secure payslips', async () => {
  renderPage(<PayrollPage />)
  expect(await screen.findByText('Latest payslip')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: 'My payslips' }))
  expect(await screen.findByText('Ada Employee')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: /new period/i }),
  ).not.toBeInTheDocument()
  expect(screen.getAllByRole('tab').map((tab) => tab.textContent)).toEqual([
    'Overview',
    'My payslips',
  ])
})

it('renders actionable payroll KPIs and a structured administrator empty state', async () => {
  mocks.permissions = [
    'payroll.periods.view',
    'payroll.periods.manage',
    'payroll.prepare',
  ]
  renderPage(<PayrollPage />)
  expect(
    await screen.findByRole('button', {
      name: 'Payroll periods: 0. Open details',
    }),
  ).toBeVisible()
  expect(screen.getByText('No payroll run has been prepared yet')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: /prepare payroll/i }))
  expect(await screen.findByText('Payroll periods')).toBeVisible()
})

it('shows permission-aware payroll administration sections', async () => {
  mocks.permissions = [
    'payroll.periods.view',
    'payroll.periods.manage',
    'payroll.salary_structure.view',
  ]
  renderPage(<PayrollPage />)
  expect(await screen.findByText('Current payroll cycle')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: 'Payroll runs' }))
  expect(await screen.findByText(/no payroll periods yet/i)).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: /new period/i }),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: 'Salary structures' }))
  expect(
    await screen.findByText('Effective-dated salary structures'),
  ).toBeInTheDocument()
})

it('formats decimal payroll amounts without floating point loss', () => {
  expect(payrollMoney('9007199254740993.5', 'NGN')).toBe(
    'NGN 9,007,199,254,740,993.50',
  )
})

it('edits salary component policy without replacing payroll history', async () => {
  mocks.permissions = [
    'payroll.salary_structure.view',
    'payroll.components.manage',
  ]
  mocks.components.mockResolvedValue([
    {
      id: 'component-1',
      code: 'TRAVEL',
      name: 'Travel allowance',
      description: 'Monthly travel support',
      component_kind: 'earning',
      calculation_type: 'fixed',
      taxable: true,
      pensionable: false,
      recurring: true,
      is_active: true,
      effective_start: '2026-01-01',
      effective_end: null,
    },
  ])
  renderPage(<PayrollPage />)
  const componentsTab = await screen.findByRole('tab', { name: 'Components' })
  fireEvent.click(componentsTab)
  await screen.findByText('Travel allowance')
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
  const form = screen.getByRole('form', { name: 'Edit Travel allowance' })
  fireEvent.change(within(form).getByLabelText('Name'), {
    target: { value: 'Travel benefit' },
  })
  fireEvent.click(within(form).getByLabelText('Pensionable'))
  fireEvent.submit(form)
  await waitFor(() =>
    expect(mocks.updateComponent).toHaveBeenCalledWith(
      'component-1',
      expect.objectContaining({
        name: 'Travel benefit',
        pensionable: true,
        taxable: true,
        recurring: true,
        is_active: true,
      }),
    ),
  )
})

it('shows payroll reports only when the report permission is granted', async () => {
  mocks.permissions = ['payroll.periods.view', 'payroll.reports.view']
  renderPage(<PayrollPage />)
  await screen.findByText('Current payroll cycle')
  fireEvent.click(screen.getByRole('tab', { name: 'Reports' }))
  expect(
    await screen.findByText(/select a payroll run to view/i),
  ).toBeInTheDocument()
})
