import { createContext, useContext } from 'react'

export interface Confirmation {
  title: string
  description: string
  confirmLabel?: string
  tone?: 'danger' | 'primary'
}

export type ConfirmFunction = (options: Confirmation) => Promise<boolean>
export const ConfirmContext = createContext<ConfirmFunction>(async () => false)

export function useConfirmation() {
  return useContext(ConfirmContext)
}
