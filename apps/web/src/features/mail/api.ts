import { apiRawRequest, apiRequest } from '@/features/auth/api'

export interface MailRecipient {
  email: string
  name?: string
}

export interface MailDraft {
  to_recipients: MailRecipient[]
  cc_recipients: MailRecipient[]
  bcc_recipients: MailRecipient[]
  subject: string
  body_html: string
  body_text: string
  read_receipt_requested: boolean
  reply_to_id?: string | null
}

export interface MailAttachment {
  id: string
  filename: string
  content_type: string
  size: number
  url: string
}

export interface MailMessage {
  id: string
  thread_id: string
  folder: string
  status: string
  from_email: string
  from_name: string
  to_recipients: MailRecipient[]
  cc_recipients: MailRecipient[]
  bcc_recipients: MailRecipient[]
  subject: string
  body_html: string
  body_text: string
  preview: string
  labels: string[]
  is_read: boolean
  is_starred: boolean
  read_receipt_requested: boolean
  delivery_status: string
  delivery_error: string | null
  sent_at: string | null
  read_at: string | null
  created_at: string
  updated_at: string
  attachments: MailAttachment[]
}

export interface MailPage {
  items: MailMessage[]
  total: number
  page: number
  page_size: number
  total_pages: number
  unread: number
}

export interface MailFolder {
  id: string | null
  name: string
  color: string
  system: boolean
  count: number
  unread: number
}

export interface MailTemplate {
  id: string
  name: string
  subject: string
  body_html: string
  updated_at: string
}

export interface MailSignature {
  id: string
  name: string
  body_html: string
  is_default: boolean
  updated_at: string
}

const query = (values: Record<string, string | number | undefined>) => {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return params.toString()
}

export const mailApi = {
  messages: (options: {
    folder: string
    search?: string
    label?: string
    page: number
    pageSize: number
  }) =>
    apiRequest<MailPage>(
      `/mail/messages?${query({
        folder: options.folder,
        search: options.search,
        label: options.label,
        page: options.page,
        page_size: options.pageSize,
      })}`,
      {},
      true,
    ),
  message: (id: string) =>
    apiRequest<MailMessage>(`/mail/messages/${id}`, {}, true),
  thread: (id: string) =>
    apiRequest<MailMessage[]>(`/mail/threads/${id}`, {}, true),
  folders: () => apiRequest<MailFolder[]>('/mail/folders', {}, true),
  createFolder: (values: { name: string; color: string }) =>
    apiRequest<MailFolder>(
      '/mail/folders',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  createDraft: (values: MailDraft) =>
    apiRequest<MailMessage>(
      '/mail/drafts',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  updateDraft: (id: string, values: MailDraft) =>
    apiRequest<MailMessage>(
      `/mail/drafts/${id}`,
      { method: 'PUT', body: JSON.stringify(values) },
      true,
    ),
  send: (id: string) =>
    apiRequest<MailMessage>(
      `/mail/drafts/${id}/send`,
      { method: 'POST' },
      true,
    ),
  uploadAttachment: async (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    const response = await apiRawRequest(`/mail/drafts/${id}/attachments`, {
      method: 'POST',
      body: form,
    })
    const payload = (await response.json()) as {
      data: MailAttachment
    }
    return payload.data
  },
  read: (id: string, value: boolean) =>
    apiRequest<MailMessage>(
      `/mail/messages/${id}/read?value=${value}`,
      { method: 'POST' },
      true,
    ),
  star: (id: string, value: boolean) =>
    apiRequest<MailMessage>(
      `/mail/messages/${id}/star?value=${value}`,
      { method: 'POST' },
      true,
    ),
  move: (id: string, folder: string) =>
    apiRequest<MailMessage>(
      `/mail/messages/${id}/move`,
      { method: 'POST', body: JSON.stringify({ folder }) },
      true,
    ),
  label: (id: string, label: string, enabled = true) =>
    apiRequest<MailMessage>(
      `/mail/messages/${id}/labels`,
      { method: 'POST', body: JSON.stringify({ label, enabled }) },
      true,
    ),
  templates: () => apiRequest<MailTemplate[]>('/mail/templates', {}, true),
  createTemplate: (values: Omit<MailTemplate, 'id' | 'updated_at'>) =>
    apiRequest<MailTemplate>(
      '/mail/templates',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  signatures: () => apiRequest<MailSignature[]>('/mail/signatures', {}, true),
  createSignature: (values: Omit<MailSignature, 'id' | 'updated_at'>) =>
    apiRequest<MailSignature>(
      '/mail/signatures',
      { method: 'POST', body: JSON.stringify(values) },
      true,
    ),
  status: () =>
    apiRequest<{
      internal_delivery: boolean
      external_delivery: boolean
      provider: string | null
      configuration_url: string
    }>('/mail/status', {}, true),
}
