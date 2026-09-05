import { apiRequest } from '@/features/auth/api'

export interface Organization {
  id: string
  name: string
  slug: string
  logo_url: string | null
  status: string
  timezone: string
  country: string | null
  default_language: string
  brand_color: string
  settings: Record<string, unknown>
}

export interface Workspace {
  id: string
  organization_id: string
  name: string
  slug: string
  description: string | null
  logo_url: string | null
  brand_color: string | null
  classification: string
  visibility: string
  data_region: string | null
  owner_id: string | null
  settings: Record<string, unknown>
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface WorkspaceOverview {
  workspace: Workspace
  team_count: number
  member_count: number
  administrator_count: number
  channel_count: number
  meeting_count: number
  calendar_count: number
  file_count: number
  storage_bytes: number
  app_count: number
  recent_activity: Array<{
    id: string
    event_type: string
    occurred_at: string
  }>
  audit_history: Array<{ id: string; action: string; created_at: string }>
}

export interface WorkspaceMember {
  id: string
  user_id: string
  display_name: string
  email: string
  role: string
  created_at: string
}

export interface WorkspaceIntegration {
  id: string
  workspace_id: string
  provider: string
  display_name: string
  enabled: boolean
  configuration: Record<string, unknown>
  created_at: string
}

export interface WorkspaceTemplate {
  id: string
  name: string
  description: string | null
  configuration: Record<string, unknown>
  created_at: string
}

export interface Team {
  id: string
  workspace_id: string
  name: string
  slug: string
  description: string | null
  color: string
  visibility: string
}

export interface Member {
  id: string
  email: string
  username: string
  display_name: string
  avatar_url: string | null
  status: string
  timezone: string
  language: string
}

export interface Invitation {
  id: string
  email: string
  role_name: string
  status: string
  expires_at: string
  resend_count: number
}

export interface OrganizationUnit {
  id: string
  organization_id: string
  parent_id: string | null
  manager_id: string | null
  unit_type: 'department' | 'branch' | 'location'
  name: string
  code: string | null
  description: string | null
  address: Record<string, unknown>
  timezone: string | null
  working_hours: Record<string, unknown>
  status: 'active' | 'inactive'
  created_at: string
  updated_at: string
}

export interface DepartmentDetail extends OrganizationUnit {
  employee_count: number
  team_count: number
  manager_name: string | null
  recent_activity: Array<{ id: string; action: string; created_at: string }>
}

export interface OrganizationOverview {
  organization: Organization
  member_count: number
  active_member_count: number
  workspace_count: number
  team_count: number
  pending_invitation_count: number
  department_count: number
  branch_count: number
  location_count: number
  administrators: Array<{
    id: string
    display_name: string
    email: string
    role: string
  }>
  recent_activity: Array<{
    id: string
    event_type: string
    subject_type: string
    occurred_at: string
  }>
  audit_history: Array<{
    id: string
    action: string
    resource: string
    created_at: string
  }>
}

export const organizationApi = {
  organization: () =>
    apiRequest<Organization>('/organizations/current', {}, true),
  updateOrganization: (body: object) =>
    apiRequest<Organization>(
      '/organizations/current',
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  organizationOverview: () =>
    apiRequest<OrganizationOverview>(
      '/organizations/current/overview',
      {},
      true,
    ),
  organizationUnits: () =>
    apiRequest<OrganizationUnit[]>('/organizations/current/units', {}, true),
  createOrganizationUnit: (body: object) =>
    apiRequest<OrganizationUnit>(
      '/organizations/current/units',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  updateOrganizationUnit: (id: string, body: object) =>
    apiRequest<OrganizationUnit>(
      `/organizations/current/units/${id}`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  departmentDetail: (id: string) =>
    apiRequest<DepartmentDetail>(
      `/organizations/current/departments/${id}`,
      {},
      true,
    ),
  deleteOrganizationUnit: (id: string) =>
    apiRequest(
      `/organizations/current/units/${id}`,
      { method: 'DELETE' },
      true,
    ),
  organizationPolicies: () =>
    apiRequest<Record<string, Record<string, unknown>>>(
      '/organizations/current/policies',
      {},
      true,
    ),
  updateOrganizationPolicy: (
    category: string,
    values: Record<string, unknown>,
  ) =>
    apiRequest<Record<string, unknown>>(
      `/organizations/current/policies/${category}`,
      { method: 'PUT', body: JSON.stringify({ values }) },
      true,
    ),
  workspaces: () => apiRequest<Workspace[]>('/workspaces', {}, true),
  searchWorkspaces: (filters?: {
    search?: string
    archived?: boolean
    classification?: string
  }) => {
    const query = new URLSearchParams()
    if (filters?.search) query.set('search', filters.search)
    if (filters?.archived !== undefined)
      query.set('archived', String(filters.archived))
    if (filters?.classification)
      query.set('classification', filters.classification)
    const suffix = query.size ? `?${query}` : ''
    return apiRequest<Workspace[]>(`/workspaces${suffix}`, {}, true)
  },
  createWorkspace: (body: object) =>
    apiRequest<Workspace>(
      '/workspaces',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  workspace: (id: string) =>
    apiRequest<Workspace>(`/workspaces/${id}`, {}, true),
  workspaceOverview: (id: string) =>
    apiRequest<WorkspaceOverview>(`/workspaces/${id}/overview`, {}, true),
  updateWorkspace: (id: string, body: object) =>
    apiRequest<Workspace>(
      `/workspaces/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  archiveWorkspace: (id: string) =>
    apiRequest<Workspace>(
      `/workspaces/${id}/archive`,
      { method: 'POST' },
      true,
    ),
  restoreWorkspace: (id: string) =>
    apiRequest<Workspace>(
      `/workspaces/${id}/restore`,
      { method: 'POST' },
      true,
    ),
  bulkWorkspaceLifecycle: (
    workspaceIds: string[],
    action: 'archive' | 'restore',
  ) =>
    apiRequest<{ updated_ids: string[]; skipped_ids: string[] }>(
      '/workspaces/bulk/lifecycle',
      {
        method: 'POST',
        body: JSON.stringify({ workspace_ids: workspaceIds, action }),
      },
      true,
    ),
  workspaceMembers: (id: string) =>
    apiRequest<WorkspaceMember[]>(`/workspaces/${id}/members`, {}, true),
  assignWorkspaceMember: (id: string, body: object) =>
    apiRequest<WorkspaceMember>(
      `/workspaces/${id}/members`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  removeWorkspaceMember: (id: string, userId: string) =>
    apiRequest(
      `/workspaces/${id}/members/${userId}`,
      { method: 'DELETE' },
      true,
    ),
  workspaceIntegrations: (id: string) =>
    apiRequest<WorkspaceIntegration[]>(
      `/workspaces/${id}/integrations`,
      {},
      true,
    ),
  updateWorkspaceIntegration: (id: string, body: object) =>
    apiRequest<WorkspaceIntegration>(
      `/workspaces/${id}/integrations`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
  workspaceTemplates: () =>
    apiRequest<WorkspaceTemplate[]>('/workspaces/templates/catalog', {}, true),
  createWorkspaceTemplate: (body: object) =>
    apiRequest<WorkspaceTemplate>(
      '/workspaces/templates/catalog',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  teams: () => apiRequest<Team[]>('/teams', {}, true),
  createTeam: (body: object) =>
    apiRequest<Team>(
      '/teams',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
  members: () => apiRequest<Member[]>('/users', {}, true),
  invitations: () => apiRequest<Invitation[]>('/invitations', {}, true),
  invite: (body: object) =>
    apiRequest<Invitation>(
      '/invitations',
      { method: 'POST', body: JSON.stringify(body) },
      true,
    ),
}
