import { fireEvent, render, screen } from '@testing-library/react'
import type { PropsWithChildren } from 'react'

import { AuthContext, type AuthContextValue } from '@/features/auth/auth-store'
import { ProfileMenu } from '@/features/auth/profile-menu'
import { resolveBreadcrumbs } from '@/lib/route-metadata'

const navigate = vi.fn()

vi.mock('@tanstack/react-router', () => ({
  Link: ({ to, children, ...props }: PropsWithChildren<{ to: string }>) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
  useNavigate: () => navigate,
}))

const auth: AuthContextValue = {
  user: {
    id: 'user-1',
    organization_id: 'organization-1',
    email: 'abiodun@example.com',
    username: 'abiodun',
    first_name: 'Abiodun',
    last_name: 'Admin',
    display_name: 'Abiodun Admin',
    avatar_url: null,
    email_verified: true,
    force_password_change: false,
    roles: ['Super Admin'],
    permissions: ['admin.manage'],
  },
  loading: false,
  login: vi.fn(),
  register: vi.fn(),
  refreshUser: vi.fn(),
  logout: vi.fn(),
}

test('the global account menu makes Profile Center discoverable', () => {
  render(
    <AuthContext.Provider value={auth}>
      <ProfileMenu />
    </AuthContext.Provider>,
  )

  fireEvent.click(
    screen.getByRole('button', { name: 'Open user account menu' }),
  )

  expect(screen.getByRole('menuitem', { name: 'My Profile' })).toHaveAttribute(
    'href',
    '/profile',
  )
  expect(
    screen.getByRole('menuitem', { name: 'Security & MFA' }),
  ).toHaveAttribute('href', '/profile/security')
  expect(
    screen.getByRole('menuitem', { name: 'Notification Preferences' }),
  ).toHaveAttribute('href', '/profile/notifications')
  expect(screen.getByText('Super Admin')).toBeInTheDocument()
})

test('breadcrumbs preserve real administrative and profile hierarchy', () => {
  expect(resolveBreadcrumbs('/profile/security', '')).toMatchObject([
    { label: 'Profile Center', path: '/profile' },
    { label: 'Security & MFA', path: '/profile/security' },
  ])
  expect(resolveBreadcrumbs('/platform', 'section=features')).toMatchObject([
    { label: 'Administration', path: '/administration' },
    { label: 'Platform Management', path: '/platform' },
    { label: 'Feature Flags', path: '/platform?section=features' },
  ])
})
