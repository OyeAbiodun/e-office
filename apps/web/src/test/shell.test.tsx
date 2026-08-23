import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'

import { queryClient } from '@/app/query-client'
import { router } from '@/app/router'
import { ThemeProvider } from '@/components/theme-provider'
import { AuthProvider } from '@/features/auth/auth-context'

test('renders the unauthenticated login experience', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ error: { message: 'Unauthenticated' } }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  await router.navigate({ to: '/login' })

  render(
    <ThemeProvider>
      <AuthProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AuthProvider>
    </ThemeProvider>,
  )

  expect(
    await screen.findByRole(
      'heading',
      { name: 'Welcome back' },
      { timeout: 5000 },
    ),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('Work email')).toBeInTheDocument()
  expect(screen.getByLabelText('Password')).toBeInTheDocument()
  expect(screen.queryByLabelText(/organization/i)).not.toBeInTheDocument()
  expect(
    screen.queryByRole('link', { name: /create an organization/i }),
  ).not.toBeInTheDocument()
})
