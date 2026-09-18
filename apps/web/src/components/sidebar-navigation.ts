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
export function buildSidebarNavigation(
  items: MenuDefinition[],
  permissions: ReadonlySet<string> = new Set(),
) {
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
    let groupItems = definition.itemKeys
      .map((key) => byKey.get(key))
      .filter((item): item is MenuDefinition => Boolean(item))
    if (definition.key === 'finance-payroll') {
      const finance = byKey.get('finance')
      if (finance) {
        const financeChildren: MenuDefinition[] = [
          {
            ...finance,
            id: `${finance.id}-accounts`,
            key: 'finance-accounts',
            label: 'Accounts',
            path: '/finance?tab=accounts',
          },
          {
            ...finance,
            id: `${finance.id}-statements`,
            key: 'finance-statements',
            label: 'Statements',
            path: '/finance?tab=accounts&intent=statement',
          },
        ]
        if (permissions.has('finance.transactions.view'))
          financeChildren.splice(1, 0, {
            ...finance,
            id: `${finance.id}-transactions`,
            key: 'finance-transactions',
            label: 'Transactions',
            path: '/finance?tab=transactions',
          })
        groupItems = [
          ...financeChildren,
          ...groupItems.filter((item) => item.key !== 'finance'),
        ]
      }
    }
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

export function groupIsActive(group: SidebarGroup, pathname: string) {
  return group.items.some(
    (item) =>
      pathname === item.path.split('?')[0] ||
      (item.path !== '/' && pathname.startsWith(`${item.path.split('?')[0]}/`)),
  )
}
