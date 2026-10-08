import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'

import { OrganizationSettingsPage } from '@/features/organizations/settings-page'

const mocks = vi.hoisted(() => ({
  organization: vi.fn(),
  updateOrganization: vi.fn(),
}))

vi.mock('@/features/organizations/api', () => ({
  organizationApi: mocks,
}))

vi.mock('@/components/feedback/events', () => ({ notify: vi.fn() }))

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <OrganizationSettingsPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.organization.mockResolvedValue({
    id: 'organization-1',
    name: 'Acme',
    slug: 'acme',
    logo_url: null,
    status: 'active',
    timezone: 'UTC',
    country: 'US',
    default_language: 'en',
    brand_color: '#7c3aed',
    settings: { session_timeout_minutes: 60 },
  })
  mocks.updateOrganization.mockResolvedValue({})
})

test('persists bounded inactivity timeout and tenant branding controls', async () => {
  renderPage()

  expect(await screen.findByDisplayValue('60')).toBeVisible()
  expect(screen.getByLabelText('Brand color picker')).toHaveValue('#7c3aed')
  fireEvent.change(
    screen.getByRole('spinbutton', { name: /inactivity timeout/i }),
    {
      target: { value: '120' },
    },
  )
  fireEvent.click(screen.getByLabelText('Use #0f766e'))
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

  await vi.waitFor(() =>
    expect(mocks.updateOrganization).toHaveBeenCalledWith(
      expect.objectContaining({
        brand_color: '#0f766e',
        settings: expect.objectContaining({ session_timeout_minutes: 120 }),
      }),
    ),
  )
})
