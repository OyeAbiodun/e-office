import { fireEvent, render, screen } from '@testing-library/react'

import { allowsAuthenticatedPublicAccess } from '@/features/auth/public-route-policy'
import { ResetPasswordPage } from '@/features/auth/reset-password-page'

vi.mock('@tanstack/react-router', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-router')>(
    '@tanstack/react-router',
  )
  return { ...actual, useSearch: () => ({ token: 'test-reset-token' }) }
})

test('allows a password-reset link to open in an authenticated browser', () => {
  expect(allowsAuthenticatedPublicAccess('/reset-password')).toBe(true)
  expect(allowsAuthenticatedPublicAccess('/login')).toBe(false)
})

test('requires password confirmation before completing a reset', async () => {
  render(<ResetPasswordPage />)

  fireEvent.input(screen.getByLabelText('New password'), {
    target: { value: 'Changed!Password456' },
  })
  fireEvent.input(screen.getByLabelText('Confirm new password'), {
    target: { value: 'Different!Password456' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Reset password' }))

  expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
})

test('validates the full password policy before sending a reset request', async () => {
  render(<ResetPasswordPage />)

  fireEvent.input(screen.getByLabelText('New password'), {
    target: { value: 'NoSymbolPassword456' },
  })
  fireEvent.input(screen.getByLabelText('Confirm new password'), {
    target: { value: 'NoSymbolPassword456' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Reset password' }))

  expect(await screen.findByText('Include a symbol')).toBeInTheDocument()
})
