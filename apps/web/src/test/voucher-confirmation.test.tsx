import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { VoucherDetailPage } from '@/features/finance/voucher-detail'

const mocks = vi.hoisted(() => ({
  action: vi.fn(),
  categories: vi.fn(),
  confirm: vi.fn(async () => true),
  detail: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
  useParams: () => ({ voucherId: 'voucher-1' }),
}))

vi.mock('@/components/feedback/confirmation', () => ({
  useConfirmation: () => mocks.confirm,
}))

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({ user: { permissions: [] } }),
}))

vi.mock('@/features/finance/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/finance/api')>()
  return {
    ...actual,
    financeApi: {
      ...actual.financeApi,
      action: mocks.action,
      categories: mocks.categories,
      detail: mocks.detail,
    },
  }
})

test('confirms voucher identity, amount, and categories before real submission', async () => {
  mocks.categories.mockResolvedValue([
    { id: 'category-1', name: 'Travel', code: 'TRAVEL', is_active: true },
  ])
  mocks.action.mockResolvedValue({})
  mocks.detail.mockResolvedValue({
    voucher: {
      id: 'voucher-1',
      voucher_number: 'V-2026-001',
      requester_id: 'user-1',
      requester_name: 'Ada Employee',
      department_id: null,
      department_name: null,
      meeting_id: null,
      meeting_title: null,
      task_id: null,
      task_title: null,
      expense_category_id: 'category-1',
      title: 'Client workshop travel',
      description: null,
      currency: 'USD',
      status: 'draft',
      requested_amount: '1250.00',
      approved_amount: '0.00',
      disbursed_amount: '0.00',
      outstanding_amount: '1250.00',
      submitted_at: null,
      created_at: '2026-10-07T00:00:00Z',
    },
    line_items: [
      {
        description: 'Flights',
        quantity: '1.000',
        unit_price: '1250.00',
        tax_amount: '0.00',
        amount: '1250.00',
        expense_category_id: 'category-1',
      },
    ],
    allowed_actions: ['submit'],
    attachments: [],
    comments: [],
    reviews: [],
    history: [],
    disbursements: [],
    transactions: [],
  })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <VoucherDetailPage />
    </QueryClientProvider>,
  )

  const submit = await screen.findByRole('button', { name: 'Submit' })
  await waitFor(() => expect(submit).toBeEnabled())
  fireEvent.click(submit)
  await waitFor(() =>
    expect(mocks.confirm).toHaveBeenCalledWith({
      title: 'Submit voucher?',
      description:
        'Client workshop travel · USD 1,250.00 · Travel. Submit this voucher for formal review?',
      confirmLabel: 'Submit for review',
    }),
  )
  await waitFor(() =>
    expect(mocks.action).toHaveBeenCalledWith('voucher-1', 'submit', {}),
  )
})
