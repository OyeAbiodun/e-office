import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { FinancePage } from '@/features/finance/finance-page'

const mocks = vi.hoisted(() => ({
  categories: vi.fn(),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
  useParams: () => ({}),
  useSearch: () => ({ tab: 'categories' }),
}))

vi.mock('@/features/auth/auth-store', () => ({
  useAuth: () => ({
    user: {
      permissions: ['finance.accounts.view', 'finance.accounts.manage'],
    },
  }),
}))

vi.mock('@/features/finance/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/finance/api')>()
  return {
    ...actual,
    financeApi: {
      ...actual.financeApi,
      categories: mocks.categories,
      createCategory: mocks.createCategory,
      updateCategory: mocks.updateCategory,
    },
  }
})

test('shows tenant categories and creates only through the authorized contract', async () => {
  mocks.categories.mockResolvedValue([
    {
      id: 'category-1',
      name: 'Travel',
      code: 'TRAVEL',
      description: 'Approved travel costs',
      is_active: true,
    },
    {
      id: 'category-2',
      name: 'Legacy supplies',
      code: null,
      description: null,
      is_active: false,
    },
  ])
  mocks.createCategory.mockResolvedValue({ id: 'category-3', name: 'Meals' })
  mocks.updateCategory.mockResolvedValue({})
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <FinancePage />
    </QueryClientProvider>,
  )

  expect(await screen.findByText('Travel')).toBeVisible()
  expect(screen.getByText('Legacy supplies')).toBeVisible()
  expect(screen.getByText(/inactive/i)).toBeVisible()

  fireEvent.change(screen.getByLabelText('Category name'), {
    target: { value: 'Meals' },
  })
  fireEvent.change(screen.getByLabelText('Description'), {
    target: { value: 'Staff meals' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Create category' }))

  await waitFor(() => expect(mocks.createCategory).toHaveBeenCalledTimes(1))
  expect(mocks.createCategory.mock.calls[0]?.[0]).toEqual({
    name: 'Meals',
    code: null,
    description: 'Staff meals',
    is_active: true,
  })
  fireEvent.click(screen.getAllByRole('button', { name: 'Edit' })[1]!)
  fireEvent.click(
    await screen.findByRole('button', { name: 'Activate category' }),
  )
  await waitFor(() =>
    expect(mocks.updateCategory).toHaveBeenCalledWith('category-2', {
      is_active: true,
    }),
  )
})
