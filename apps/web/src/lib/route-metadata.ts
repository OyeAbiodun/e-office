export interface BreadcrumbItem {
  label: string
  path: string
  icon: string
}

const labels: Record<string, string> = {
  vouchers: 'Vouchers',
  finance: 'Finance Center',
  leave: 'Leave',
  team: 'Team Leave',
  accounts: 'Accounts',
  calendar: 'Calendar',
  meetings: 'Meetings',
  chat: 'Chat',
  mail: 'Mail',
  organization: 'Organization',
  workspaces: 'Workspaces',
  teams: 'Teams',
  members: 'Members',
  invitations: 'Invitations',
  profile: 'Profile Center',
  security: 'Security & MFA',
  preferences: 'Account Preferences',
  sessions: 'Active Sessions',
  connections: 'Connected Accounts',
  mfa: 'Multi-factor Authentication',
  account: 'My Account',
  settings: 'Settings',
  platform: 'Platform Management',
  administration: 'Administration',
  help: 'Help Center',
  notifications: 'Notification Center',
  users: 'User Management',
  roles: 'Roles & Permissions',
  integrations: 'Integration Center',
  audit: 'Audit Center',
  'system-health': 'System Health',
}

const icons: Record<string, string> = {
  administration: 'settings',
  platform: 'flag',
  integrations: 'plug',
  users: 'users',
  roles: 'shield',
  audit: 'file-clock',
  'system-health': 'activity',
  meetings: 'video',
  calendar: 'calendar-days',
  chat: 'messages',
  mail: 'mail',
  notifications: 'bell',
  profile: 'user',
  leave: 'calendar-range',
}

const administrationRoutes = new Set([
  'platform',
  'integrations',
  'users',
  'roles',
  'audit',
  'system-health',
  'organization',
])

const platformSections: Record<string, string> = {
  features: 'Feature Flags',
  modules: 'Module Registry',
  runtime: 'Runtime Configuration',
  security: 'Security',
  branding: 'Branding',
  connections: 'External Connections',
  scheduler: 'Scheduler',
  workers: 'Workers',
  licensing: 'Licensing',
  menus: 'Menu Manager',
  system: 'System Modules',
}

const readable = (part: string) =>
  labels[part] ??
  part
    .replaceAll('-', ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())

const isDynamic = (part: string) =>
  /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(part) || /^\d+$/.test(part)

export function resolveBreadcrumbs(
  pathname: string,
  search: string,
): BreadcrumbItem[] {
  const parts = pathname.split('/').filter(Boolean)
  if (parts.length === 0)
    return [{ label: 'Dashboard', path: '/', icon: 'layout-dashboard' }]

  const crumbs: BreadcrumbItem[] = []
  const root = parts[0]!
  if (administrationRoutes.has(root) && root !== 'administration')
    crumbs.push({
      label: 'Administration',
      path: '/administration',
      icon: 'settings',
    })

  parts.forEach((part, index) => {
    const path = `/${parts.slice(0, index + 1).join('/')}`
    let label = readable(part)
    if (root === 'profile' && part === 'notifications')
      label = 'Notification Preferences'
    if (root === 'profile' && part === 'organization')
      label = 'Organization & Access'
    if (isDynamic(part)) {
      const parent = parts[index - 1]
      label =
        parent === 'meetings'
          ? 'Meeting Details'
          : parent === 'teams'
            ? 'Team Details'
            : parent === 'workspaces'
              ? 'Workspace Details'
              : parent === 'mail'
                ? 'Message'
                : parent === 'chat'
                  ? 'Conversation'
                  : 'Details'
    }
    if (part === 'edit') label = 'Edit'
    if (part === 'new') label = root === 'meetings' ? 'Schedule Meeting' : 'New'
    if (part === 'compose') label = 'Compose'
    if (part === 'thread') label = 'Thread'
    crumbs.push({
      label,
      path,
      icon: icons[part] ?? icons[root] ?? 'circle',
    })
  })

  if (root === 'platform') {
    const section = new URLSearchParams(search).get('section')
    const sectionLabel = section ? platformSections[section] : undefined
    if (section && section !== 'overview' && sectionLabel)
      crumbs.push({
        label: sectionLabel,
        path: `/platform?section=${section}`,
        icon: 'flag',
      })
  }
  return crumbs
}
