import { createContext, useContext } from 'react'

import type { AuthUser } from '@/features/auth/api'

export interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  login: (values: object) => Promise<AuthUser>
  register: (values: object) => Promise<void>
  refreshUser: () => Promise<AuthUser>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
