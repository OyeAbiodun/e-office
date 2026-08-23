import { apiRequest } from '@/features/auth/api'

export interface FeatureFlag {
  id: string
  key: string
  name: string
  description: string | null
  enabled: boolean
  hidden: boolean
  maintenance_mode: boolean
  release_stage: 'internal' | 'beta' | 'public'
  availability_status:
    | 'available'
    | 'beta'
    | 'preview'
    | 'coming_soon'
    | 'deprecated'
    | 'disabled'
  implementation_status: string
  planned_version: string | null
  estimated_availability: string | null
  dependencies: string[]
  navigation_path: string | null
  documentation_path: string | null
  ui_available: boolean
  backend_available: boolean
  navigation_available: boolean
  search_available: boolean
  permissions_available: boolean
  installed: boolean
  updated_at: string
}

export interface MenuDefinition {
  id: string
  key: string
  label: string
  path: string
  icon: string
  permission: string
  required_role: string | null
  feature_key: string | null
  badge: string | null
  parent_key: string | null
  section: string
  position: number
  enabled: boolean
  hidden: boolean
}

export interface ConfigurationEntry {
  id: string
  key: string
  value: Record<string, unknown>
  category: string
  is_secret: boolean
  updated_at: string
}

export const platformApi = {
  navigation: () =>
    apiRequest<MenuDefinition[]>('/platform/navigation', {}, true),
  features: () => apiRequest<FeatureFlag[]>('/platform/features', {}, true),
  updateFeature: (key: string, body: Partial<FeatureFlag>) =>
    apiRequest<FeatureFlag>(
      `/platform/features/${key}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  menus: () => apiRequest<MenuDefinition[]>('/platform/menus', {}, true),
  updateMenu: (key: string, body: Partial<MenuDefinition>) =>
    apiRequest<MenuDefinition>(
      `/platform/menus/${key}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      true,
    ),
  previewMenus: (items: Array<Partial<MenuDefinition> & { key: string }>) =>
    apiRequest<MenuDefinition[]>(
      '/platform/menus/preview',
      { method: 'POST', body: JSON.stringify({ items }) },
      true,
    ),
  publishMenus: (items: Array<Partial<MenuDefinition> & { key: string }>) =>
    apiRequest<MenuDefinition[]>(
      '/platform/menus/publish',
      { method: 'PUT', body: JSON.stringify({ items }) },
      true,
    ),
  resetMenus: () =>
    apiRequest<MenuDefinition[]>(
      '/platform/menus/reset',
      { method: 'POST' },
      true,
    ),
  exportMenus: () =>
    apiRequest<{
      version: number
      exported_at: string
      items: MenuDefinition[]
    }>('/platform/menus/export', {}, true),
  importMenus: (items: Array<Partial<MenuDefinition> & { key: string }>) =>
    apiRequest<MenuDefinition[]>(
      '/platform/menus/import',
      { method: 'POST', body: JSON.stringify({ version: 1, items }) },
      true,
    ),
  configuration: () =>
    apiRequest<ConfigurationEntry[]>('/platform/configuration', {}, true),
  setConfiguration: (
    key: string,
    body: {
      value: Record<string, unknown>
      category: string
      is_secret?: boolean
    },
  ) =>
    apiRequest<ConfigurationEntry>(
      `/platform/configuration/${key}`,
      { method: 'PUT', body: JSON.stringify(body) },
      true,
    ),
}
