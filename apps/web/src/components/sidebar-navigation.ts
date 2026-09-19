import type { MenuDefinition } from '@/features/platform/api'

export interface SidebarGroup {
  key: string
  label: string
  items: MenuDefinition[]
}

const GROUPS: Array<{ key: string; label: string; itemKeys: string[] }> = [
  {
    key: 'my-work',
    label: 'My work',
    itemKeys: ['my-space', 'projects', 'tasks', 'calendar'],
  },
  {
    key: 'communication',
    label: 'Communication',
    itemKeys: ['mail', 'chat', 'meetings', 'notifications'],
  },
  {
    key: 'people',
    label: 'People',
    itemKeys: ['members', 'leave'],
  },
  {
    key: 'finance-payroll',
    label: 'Finance & payroll',
    itemKeys: ['finance', 'vouchers', 'payroll'],
  },
  {
    key: 'intelligence',
    label: 'Intelligence',
    itemKeys: ['reports'],
  },
]

const DIRECT_KEYS = new Set(['dashboard', 'administration', 'help'])

/**
 * Creates a presentation hierarchy from the already authorized server menu.
 * It never introduces a capability: hidden, disabled, feature-gated and
 * permission-gated entries have already been removed by the navigation API.
 */
export function buildSidebarNavigation(items: MenuDefinition[]) {
  const roots = items
    .filter(
      (item) =>
        !item.parent_key ||
        !items.some((entry) => entry.key === item.parent_key),
    )
    .sort((left, right) => left.position - right.position)
  const byKey = new Map(roots.map((item) => [item.key, item]))
  const consumed = new Set<string>()
  const direct = roots.filter((item) => {
    if (!DIRECT_KEYS.has(item.key)) return false
    consumed.add(item.key)
    return true
  })
  const groups = GROUPS.map((definition) => {
    const groupItems = definition.itemKeys
      .map((key) => byKey.get(key))
      .filter((item): item is MenuDefinition => Boolean(item))
    definition.itemKeys.forEach((key) => {
      if (byKey.has(key)) consumed.add(key)
    })
    return { key: definition.key, label: definition.label, items: groupItems }
  }).filter((group) => group.items.length > 0)
  const ungrouped = roots.filter((item) => !consumed.has(item.key))
  if (ungrouped.length)
    groups.push({ key: 'more', label: 'More', items: ungrouped })
  return { direct, groups }
}

export const sidebarGroupStorageKey = 'officeflow.sidebar.groups.v1'

export function toggleSidebarGroup(current: Set<string>, key: string) {
  return current.has(key) ? new Set<string>() : new Set([key])
}

export function itemIsActive(
  item: MenuDefinition,
  pathname: string,
  search = '',
) {
  const [itemPathname, itemSearch = ''] = item.path.split('?')
  const pathMatches =
    pathname === itemPathname ||
    (itemPathname !== '/' && pathname.startsWith(`${itemPathname}/`))
  if (!pathMatches) return false
  if (!itemSearch) return true

  const expected = new URLSearchParams(itemSearch)
  const current = new URLSearchParams(
    search.startsWith('?') ? search.slice(1) : search,
  )
  if (expected.size !== current.size) return false
  return [...expected].every(([key, value]) => current.get(key) === value)
}

export function groupIsActive(group: SidebarGroup, pathname: string) {
  return group.items.some(
    (item) =>
      pathname === item.path.split('?')[0] ||
      (item.path !== '/' && pathname.startsWith(`${item.path.split('?')[0]}/`)),
  )
}
