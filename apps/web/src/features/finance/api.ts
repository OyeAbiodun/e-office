import { apiRequest, apiRawRequest } from '@/features/auth/api'

export type Filters = Record<string, string | number | boolean | undefined>
export const query = (filters: Filters = {}) => {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters))
    if (value !== undefined && value !== '') params.set(key, String(value))
  return params.size ? `?${params}` : ''
}
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
export interface Voucher {
  id: string
  voucher_number: string
  requester_id: string
  requester_name: string | null
  department_id: string | null
  department_name: string | null
  meeting_id: string | null
  meeting_title: string | null
  task_id: string | null
  task_title: string | null
  expense_category_id: string | null
  title: string
  description: string | null
  currency: string
  status: string
  requested_amount: string
  approved_amount: string
  disbursed_amount: string
  outstanding_amount: string
  submitted_at: string | null
  created_at: string
}
export interface LineItem {
  description: string
  quantity: string
  unit_price: string
  tax_amount: string
  amount?: string
  expense_category_id?: string | null
  notes?: string | null
}
export interface VoucherDetail {
  voucher: Voucher
  line_items: LineItem[]
  allowed_actions: string[]
  attachments: Array<{
    id: string
    filename: string
    size: number
    content_type: string
    url: string
    actor_name: string | null
    created_at: string
  }>
  comments: Array<{
    id: string
    body: string
    actor_name: string | null
    created_at: string
  }>
  reviews: Array<{
    id: string
    decision: string
    approved_amount: string | null
    comment: string | null
    actor_name: string | null
    created_at: string
  }>
  history: Array<{
    id: string
    event_type: string
    reason: string | null
    actor_name: string | null
    created_at: string
  }>
  disbursements: Array<{
    id: string
    amount: string
    payment_reference: string | null
    payment_date: string
    payment_method: string
    actor_name: string | null
  }>
  transactions: Transaction[]
}
export interface Account {
  id: string
  account_name: string
  account_code: string
  account_type: string
  currency: string
  opening_balance: string
  balance: string
  status: string
  bank_name: string | null
  account_number_masked: string | null
  description: string | null
}
export interface Transaction {
  id: string
  account_id: string
  account_name: string | null
  voucher_id: string | null
  voucher_number: string | null
  transfer_group_id: string | null
  reversal_of_id: string | null
  reference: string
  transaction_type: string
  direction: string
  amount: string
  currency: string
  transaction_date: string
  description: string
  reconciled: boolean
  reconciliation_reference: string | null
  reconciliation_note: string | null
  running_balance: string | null
}
export interface Statement {
  account: Account
  from_date: string
  to_date: string
  opening_balance: string
  credits: string
  debits: string
  closing_balance: string
  transactions: Transaction[]
}
export interface Option {
  id: string
  name: string
}
const get = <T>(path: string) => apiRequest<T>(path, {}, true)
const write = <T>(path: string, body: unknown, method = 'POST') =>
  apiRequest<T>(path, { method, body: JSON.stringify(body) }, true)
export const financeApi = {
  vouchers: (filters: Filters) =>
    get<Page<Voucher>>(`/vouchers${query(filters)}`),
  detail: (id: string) => get<VoucherDetail>(`/vouchers/${id}`),
  options: () =>
    get<{ requesters: Option[]; departments: Option[]; approvers: Option[] }>(
      '/vouchers/options',
    ),
  categories: () => get<Option[]>('/finance/categories'),
  create: (body: unknown) => write<Voucher>('/vouchers', body),
  edit: (id: string, body: unknown) =>
    write<Voucher>(`/vouchers/${id}`, body, 'PATCH'),
  action: (id: string, action: string, body: unknown = {}) =>
    write<Voucher>(`/vouchers/${id}/${action}`, body),
  comment: (id: string, body: string) =>
    write(`/vouchers/${id}/comments`, { body }),
  upload: (id: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return apiRequest(
      `/vouchers/${id}/attachments`,
      { method: 'POST', body },
      true,
    )
  },
  removeAttachment: (id: string, attachmentId: string) =>
    apiRequest(
      `/vouchers/${id}/attachments/${attachmentId}`,
      { method: 'DELETE' },
      true,
    ),
  accounts: () => get<Account[]>('/finance/accounts'),
  account: (id: string) => get<Account>(`/finance/accounts/${id}`),
  createAccount: (body: unknown) => write<Account>('/finance/accounts', body),
  adjust: (body: unknown) =>
    write<Transaction>('/finance/transactions/adjustments', body),
  transfer: (body: unknown) => write<Transaction[]>('/finance/transfers', body),
  transactions: (filters: Filters) =>
    get<Page<Transaction>>(`/finance/transactions/page${query(filters)}`),
  reverse: (id: string, reason: string, idempotency_key: string) =>
    write(`/finance/transactions/${id}/reverse`, { reason, idempotency_key }),
  reconcile: (id: string, reference: string, note: string) =>
    write(`/finance/transactions/${id}/reconcile`, { reference, note }),
  statement: (id: string, filters: Filters) =>
    get<Statement>(`/finance/accounts/${id}/statement${query(filters)}`),
  summary: () =>
    get<{
      groups: Array<{
        status: string
        currency: string
        count: number
        outstanding: string
      }>
    }>('/vouchers/summary'),
}

export async function downloadFinance(path: string, filename: string) {
  const response = await apiRawRequest(path)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// Money is serialized as decimal text. Preserve cents even above Number.MAX_SAFE_INTEGER.
export function money(value: string, currency = 'NGN') {
  const [whole, fraction = ''] = value.split('.')
  return `${currency} ${BigInt(whole || '0').toLocaleString()}.${fraction.padEnd(2, '0').slice(0, 2)}`
}
export function subtractMoney(left: string, right: string) {
  const cents = (v: string) => {
    const [w, f = ''] = v.split('.')
    return BigInt(w || '0') * 100n + BigInt(f.padEnd(2, '0').slice(0, 2))
  }
  const n = cents(left) - cents(right)
  return `${n < 0n ? '-' : ''}${(n < 0n ? -n : n) / 100n}.${((n < 0n ? -n : n) % 100n).toString().padStart(2, '0')}`
}
