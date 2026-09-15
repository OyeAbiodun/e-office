import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'

import { DecisionBarChart } from '@/components/decision-chart'
import { buildSidebarNavigation } from '@/components/sidebar-navigation'
import type { MenuDefinition } from '@/features/platform/api'

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, ...props }: { children: ReactNode; to: string }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}))

const item = (
  key: string,
  label: string,
  path: string,
  position: number,
): MenuDefinition => ({
  id: key,
  key,
  label,
  path,
  icon: 'layout-dashboard',
  permission: `${key}.view`,
  required_role: null,
  feature_key: null,
  badge: null,
  parent_key: null,
  section: 'work',
  position,
  enabled: true,
  hidden: false,
})

test('groups only server-authorized destinations without duplicates', () => {
  const navigation = buildSidebarNavigation([
    item('dashboard', 'Home', '/', 1),
    item('tasks', 'Tasks & Activities', '/tasks', 2),
    item('mail', 'Mail', '/mail', 3),
    item('members', 'People', '/members', 4),
    item('help', 'Help & Support', '/help', 5),
  ])
  expect(navigation.direct.map((entry) => entry.key)).toEqual([
    'dashboard',
    'help',
  ])
  expect(navigation.groups.map((group) => group.label)).toEqual([
    'My work',
    'Communication',
    'People',
  ])
  const groupedKeys = navigation.groups.flatMap((group) =>
    group.items.map((entry) => entry.key),
  )
  expect(new Set(groupedKeys).size).toBe(groupedKeys.length)
  expect(groupedKeys).not.toContain('payroll')
})

test('finance navigation exposes functional children according to permission', () => {
  const finance = item('finance', 'Finance', '/finance', 1)
  const payroll = item('payroll', 'My Payroll', '/payroll', 2)
  const withoutTransactions = buildSidebarNavigation([finance, payroll])
  const basicItems = withoutTransactions.groups.find(
    (group) => group.key === 'finance-payroll',
  )?.items
  expect(basicItems).toBeDefined()
  expect(basicItems?.map((entry) => entry.label)).toEqual([
    'Overview',
    'Accounts',
    'Statements',
    'My Payroll',
  ])
  const withTransactions = buildSidebarNavigation(
    [finance, payroll],
    new Set(['finance.transactions.view']),
  )
  expect(
    withTransactions.groups
      .find((group) => group.key === 'finance-payroll')
      ?.items.map((entry) => entry.label),
  ).toEqual([
    'Overview',
    'Accounts',
    'Transactions',
    'Statements',
    'My Payroll',
  ])
})

test('decision chart provides numerical summaries and drill-down links', () => {
  render(
    <DecisionBarChart
      data={[
        { label: 'Open work', value: 9, to: '/tasks?status=in_progress' },
        {
          label: 'Overdue',
          value: 2,
          to: '/tasks?due=overdue',
          tone: 'danger',
        },
      ]}
      description="Select a bar to inspect work."
      title="Work this week"
    />,
  )
  expect(
    screen.getByRole('region', { name: 'Work this week chart' }),
  ).toBeVisible()
  expect(screen.getByRole('link', { name: /Open work: 9/ })).toHaveAttribute(
    'href',
    '/tasks?status=in_progress',
  )
  expect(screen.getByText('11')).toBeVisible()
})
