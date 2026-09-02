import { apiRequest } from '@/features/auth/api'

export type IntegrationHealth = 'healthy' | 'attention' | 'disabled'

export interface IntegrationProvider {
  key: string
  name: string
  category: string
  description: string
  auth_type: string
  enabled: boolean
  configured: boolean
  validated: boolean
  health: IntegrationHealth
  updated_at: string | null
  last_tested_at: string | null
}

export interface IntegrationTestResult {
  key: string
  status: 'healthy' | 'attention'
  message: string
  latency_ms: number
  checked_at: string
}

export interface IntegrationAudit {
  action: string
  status: string
  created_at: string
  actor_id: string | null
  latency_ms: number | null
  diagnostic: string | null
  recipient: string | null
  revision: number | null
  template_key: string | null
  template_version: string | null
}

export interface SmtpConfiguration {
  provider_display_name: string
  host: string
  port: number
  security_mode: 'starttls' | 'ssl_tls' | 'none'
  allow_insecure: boolean
  connection_timeout: number
  authentication_enabled: boolean
  authentication_method: 'password'
  username: string | null
  password_configured: boolean
  password_mask: string | null
  from_email: string
  from_name: string
  reply_to: string | null
  return_path: string | null
  enabled: boolean
  max_retry_attempts: number
  retry_delay_seconds: number
  timeout_seconds: number
  default_priority: 'low' | 'normal' | 'high'
  state:
    | 'not_configured'
    | 'configured'
    | 'testing'
    | 'healthy'
    | 'degraded'
    | 'failed'
    | 'disabled'
  revision: number
  updated_at: string | null
  last_validated_at: string | null
}

export type SmtpConfigurationUpdate = Omit<
  SmtpConfiguration,
  | 'password_configured'
  | 'password_mask'
  | 'state'
  | 'revision'
  | 'updated_at'
  | 'last_validated_at'
> & { password?: string }

export interface SmtpTestEmailResult {
  status: 'accepted' | 'failed'
  message: string
  recipient: string
  message_id: string | null
  latency_ms: number
  accepted_at: string | null
}

export type TransactionalTemplateKey =
  | 'auth.password_reset'
  | 'auth.email_verification'
  | 'user.invitation'
  | 'user.temporary_password'
  | 'meeting.invitation'
  | 'meeting.updated'
  | 'meeting.cancelled'
  | 'meeting.reminder'
  | 'smtp.test'

export interface EmailTemplatePreview {
  key: TransactionalTemplateKey
  version: string
  subject: string
  text: string
  html: string
}

export const integrationApi = {
  list: () => apiRequest<IntegrationProvider[]>('/integrations', {}, true),
  configure: (key: string, values: Record<string, unknown>) =>
    apiRequest<IntegrationProvider>(
      `/integrations/${key}`,
      { method: 'PUT', body: JSON.stringify({ values }) },
      true,
    ),
  disconnect: (key: string) =>
    apiRequest<{ key: string; configured: boolean; message: string }>(
      `/integrations/${key}`,
      { method: 'DELETE' },
      true,
    ),
  test: (key: string) =>
    apiRequest<IntegrationTestResult>(
      `/integrations/${key}/test`,
      { method: 'POST' },
      true,
    ),
  synchronize: (key: string) =>
    apiRequest<{ key: string; configured: boolean; message: string }>(
      `/integrations/${key}/synchronize`,
      { method: 'POST' },
      true,
    ),
  audit: (key: string) =>
    apiRequest<IntegrationAudit[]>(`/integrations/${key}/audit`, {}, true),
  smtpConfiguration: () =>
    apiRequest<SmtpConfiguration>('/integrations/smtp/configuration', {}, true),
  configureSmtp: (values: SmtpConfigurationUpdate) =>
    apiRequest<SmtpConfiguration>(
      '/integrations/smtp/configuration',
      { method: 'PUT', body: JSON.stringify(values) },
      true,
    ),
  sendSmtpTestEmail: (recipient: string) =>
    apiRequest<SmtpTestEmailResult>(
      '/integrations/smtp/test-email',
      { method: 'POST', body: JSON.stringify({ recipient }) },
      true,
      false,
    ),
  smtpTemplatePreview: (key: TransactionalTemplateKey) =>
    apiRequest<EmailTemplatePreview>(
      `/integrations/smtp/templates/${key}/preview`,
      {},
      true,
    ),
}
