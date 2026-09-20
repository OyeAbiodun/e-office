import AxeBuilder from '@axe-core/playwright'
import { expect, type Page, test } from '@playwright/test'

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value) throw new Error(`${name} must be set for browser acceptance`)
  return value
}

const organizerEmail = requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL')
const organizerPassword = requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD')

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Work email').fill(organizerEmail)
  const passwordField = page.getByLabel('Password')
  await passwordField.fill(organizerPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await passwordField.fill('').catch(() => undefined)
  await expect(page).toHaveURL('/', { timeout: 15_000 })
  await expect(
    page.getByRole('heading', { name: /Good (morning|afternoon|evening)/ }),
  ).toBeVisible()
}

async function navigateTo(page: Page, label: string) {
  if ((page.viewportSize()?.width ?? 1280) < 1024)
    await page.getByRole('button', { name: 'Open navigation' }).click()
  const link = page.getByRole('link', { name: label, exact: true })
  if (!(await link.isVisible().catch(() => false))) {
    const groups: Record<string, string> = {
      'My Space': 'My work',
      Projects: 'My work',
      'Tasks & Activities': 'My work',
      Calendar: 'My work',
      Mail: 'Communication',
      Chat: 'Communication',
      Meetings: 'Communication',
      Notifications: 'Communication',
      People: 'People',
      Leave: 'People',
      Finance: 'Finance & payroll',
      Vouchers: 'Finance & payroll',
      'My Payroll': 'Finance & payroll',
      'Reports & Intelligence': 'Intelligence',
    }
    const group = groups[label]
    if (group)
      await page.getByRole('button', { name: group, exact: true }).click()
  }
  await link.click()
}

test('authenticated shell, command center, and navigation work', async ({
  page,
}) => {
  await login(page)
  await page.keyboard.press('Control+k')
  await expect(
    page.getByRole('dialog', { name: 'Search OfficeFlow' }),
  ).toBeVisible()
  await page.getByLabel('Search commands').fill('calendar')
  await page
    .getByRole('dialog', { name: 'Search OfficeFlow' })
    .getByRole('link', { name: 'Calendar Work navigation' })
    .click()
  await expect(page).toHaveURL('/calendar')
  await expect(page.getByRole('heading', { name: 'Calendar' })).toBeVisible()

  await page.goBack()
  await expect(page).toHaveURL('/')
  await page.goto('/profile/security/mfa')
  await page.reload()
  await expect(page).toHaveURL('/profile/security/mfa')
  await expect(
    page.locator('nav[aria-label$="readcrumb"]:visible'),
  ).toContainText('Multi-factor Authentication')

  const secondPage = await page.context().newPage()
  await secondPage.goto('/profile')
  await expect(secondPage).toHaveURL('/profile')
  await expect(
    secondPage.getByRole('button', { name: /user account/i }),
  ).toBeVisible()
  await secondPage.close()
})

test('grouped navigation and live decision charts support drill-down', async ({
  page,
}) => {
  await login(page)
  if ((page.viewportSize()?.width ?? 1280) < 1024)
    await page.getByRole('button', { name: 'Open navigation' }).click()
  const sidebar = page.getByRole('navigation', { name: 'Primary navigation' })
  await expect(sidebar.getByRole('button', { name: 'My work' })).toBeVisible()
  await expect(
    sidebar.getByRole('button', { name: 'Communication' }),
  ).toBeVisible()
  await expect(
    sidebar.getByRole('button', { name: 'Finance & payroll' }),
  ).toBeVisible()
  const myWorkGroup = sidebar.getByRole('button', { name: 'My work' })
  const communicationGroup = sidebar.getByRole('button', {
    name: 'Communication',
  })
  await myWorkGroup.click()
  await expect(myWorkGroup).toHaveAttribute('aria-expanded', 'true')
  await communicationGroup.click()
  await expect(communicationGroup).toHaveAttribute('aria-expanded', 'true')
  await expect(myWorkGroup).toHaveAttribute('aria-expanded', 'false')

  await sidebar.getByRole('button', { name: 'Finance & payroll' }).click()
  await sidebar.getByRole('link', { name: 'My Payroll' }).click()
  await expect(page).toHaveURL('/payroll')
  if ((page.viewportSize()?.width ?? 1280) < 1024)
    await expect(sidebar).not.toBeInViewport()
  await expect(page.getByRole('heading', { name: 'Payroll' })).toBeVisible()
  await expect(
    sidebar.getByRole('button', { name: 'Finance & payroll' }),
  ).toHaveAttribute('aria-expanded', 'true')
  await expect(sidebar.getByRole('link', { name: 'Overview' })).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: /Payroll periods/ }),
  ).toBeVisible()
  await page.getByRole('button', { name: /Payroll periods/ }).click()
  await expect(page.getByRole('tab', { name: 'Payroll runs' })).toHaveAttribute(
    'aria-selected',
    'true',
  )

  await page.goto('/')
  await expect(page.locator('[data-decision-chart]')).toHaveCount(2)
  const chartLink = page.locator('[data-decision-chart] a').first()
  await chartLink.click()
  await expect(page).not.toHaveURL('/')

  await page.goto('/reports')
  await expect(
    page.getByRole('heading', { name: 'Reports & Intelligence' }),
  ).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Work delivery chart' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Report history' }).click()
  await expect(
    page.getByRole('heading', { name: 'Report history' }),
  ).toBeVisible()
  await page.getByLabel('Rows').selectOption('10')
  await expect(page.getByText(/Page \d+ of \d+/)).toBeVisible()
})

test('sidebar groups remain switchable after child navigation and deep links', async ({
  page,
}) => {
  const isMobile = (page.viewportSize()?.width ?? 1280) < 1024
  const openMobileNavigation = async () => {
    if (isMobile)
      await page.getByRole('button', { name: 'Open navigation' }).click()
  }

  await login(page)
  await openMobileNavigation()
  const sidebar = page.getByRole('navigation', { name: 'Primary navigation' })
  const finance = sidebar.getByRole('button', { name: 'Finance & payroll' })
  const communication = sidebar.getByRole('button', { name: 'Communication' })
  const people = sidebar.getByRole('button', { name: 'People', exact: true })

  await finance.click()
  await expect(finance).toHaveAttribute('aria-expanded', 'true')
  await sidebar.getByRole('link', { name: 'My Payroll' }).click()
  await expect(page).toHaveURL('/payroll')
  if (isMobile) await expect(sidebar).not.toBeInViewport()

  await openMobileNavigation()
  await expect(finance).toHaveAttribute('aria-expanded', 'true')
  await communication.focus()
  await page.keyboard.press('Enter')
  await expect(communication).toHaveAttribute('aria-expanded', 'true')
  await expect(finance).toHaveAttribute('aria-expanded', 'false')
  await sidebar.getByRole('link', { name: 'Chat' }).click()
  await expect(page).toHaveURL('/chat')

  await openMobileNavigation()
  await people.click()
  await expect(people).toHaveAttribute('aria-expanded', 'true')
  await expect(communication).toHaveAttribute('aria-expanded', 'false')
  await sidebar.getByRole('link', { name: 'People', exact: true }).click()
  await expect(page).toHaveURL('/members')

  await openMobileNavigation()
  await finance.click()
  await expect(finance).toHaveAttribute('aria-expanded', 'true')
  await expect(people).toHaveAttribute('aria-expanded', 'false')
  await sidebar.getByRole('link', { name: 'Finance', exact: true }).click()
  await expect(page).toHaveURL('/finance')
  await page.getByRole('tab', { name: 'Accounts' }).click()
  await expect(page).toHaveURL('/finance?tab=accounts')

  await page.goto('/payroll')
  await page.reload()
  await expect(page).toHaveURL('/payroll')
  await openMobileNavigation()
  await expect(finance).toHaveAttribute('aria-expanded', 'true')
  await communication.click()
  await expect(communication).toHaveAttribute('aria-expanded', 'true')
  await expect(finance).toHaveAttribute('aria-expanded', 'false')
})

test('finance sections are distinct while vouchers and payroll remain available', async ({
  page,
}) => {
  const isMobile = (page.viewportSize()?.width ?? 1280) < 1024
  const openMobileNavigation = async () => {
    if (isMobile)
      await page.getByRole('button', { name: 'Open navigation' }).click()
  }

  await login(page)
  await openMobileNavigation()
  const sidebar = page.getByRole('navigation', { name: 'Primary navigation' })
  await sidebar.getByRole('button', { name: 'Finance & payroll' }).click()
  await expect(sidebar.getByRole('link', { name: 'Finance' })).toHaveCount(1)
  await expect(sidebar.getByRole('link', { name: 'Accounts' })).toHaveCount(0)
  await expect(sidebar.getByRole('link', { name: 'Transactions' })).toHaveCount(
    0,
  )
  await expect(sidebar.getByRole('link', { name: 'Statements' })).toHaveCount(0)
  await sidebar.getByRole('link', { name: 'Finance', exact: true }).click()

  await expect(page.getByRole('heading', { name: 'Accounts' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Accounts' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.getByRole('tab', { name: 'Transactions' }).click()
  await expect(page).toHaveURL('/finance?tab=transactions')
  await expect(
    page.getByRole('heading', { name: 'Transactions' }),
  ).toBeVisible()
  await expect(page.getByLabel('Search transactions')).toBeVisible()

  await page.getByRole('tab', { name: 'Statements' }).click()
  await expect(page).toHaveURL('/finance?tab=statements')
  await expect(page.getByRole('heading', { name: 'Statements' })).toBeVisible()
  await expect(page.getByLabel('Statement account')).toBeVisible()

  await openMobileNavigation()
  await sidebar.getByRole('link', { name: 'Vouchers' }).click()
  await expect(page).toHaveURL('/vouchers')
  await expect(page.getByRole('heading', { name: 'Vouchers' })).toBeVisible()

  await openMobileNavigation()
  await sidebar.getByRole('link', { name: 'My Payroll' }).click()
  await expect(page).toHaveURL('/payroll')
  await expect(page.getByRole('heading', { name: 'Payroll' })).toBeVisible()
})

test('Help & Support provides learning, support, and admin content workflows', async ({
  page,
}) => {
  await login(page)
  await navigateTo(page, 'Help & Support')
  await expect(page).toHaveURL('/help')
  await expect(
    page.getByRole('heading', { name: 'Help & Support' }),
  ).toBeVisible()
  await expect(page.getByLabel('Search OfficeFlow help')).toBeVisible()

  const searches = [
    ['request leave', 'Leave Management'],
    ['download payslip', 'Payroll & Payslips'],
    ['approve voucher', 'Vouchers'],
    ['weekly report', 'Reports & Management Intelligence'],
    ['create project', 'Projects'],
    ['access denied', 'Quick Start Guide'],
    ['change password', 'First Login'],
  ] as const
  for (const [phrase, expectedGuide] of searches) {
    await page.getByLabel('Search OfficeFlow help').fill(phrase)
    await expect(
      page.getByRole('button', { name: expectedGuide }),
    ).toBeVisible()
  }

  await page.getByLabel('Search OfficeFlow help').fill('')
  await page.getByRole('button', { name: 'Learning Paths' }).click()
  await expect(
    page.getByRole('button', { name: 'Employee Learning Path' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Employee Learning Path' }).click()
  await expect(
    page.getByRole('heading', { name: 'How to use this path' }),
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Recommended sequence' }),
  ).toBeVisible()

  await page.getByRole('tab', { name: 'Get support' }).click()
  await expect(
    page.getByRole('heading', { name: 'How can we help?' }),
  ).toBeVisible()
  await expect(page.getByText('Request history')).toBeVisible()

  await page.getByRole('tab', { name: 'Manage content' }).click()
  await expect(page.getByText('Content studio', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Search help content')).toBeVisible()
  await page.getByLabel('Search help content').fill('Finance Center')
  await page.getByRole('button', { name: /Finance Center/ }).click()
  await expect(page.getByText(/Edit Finance Center/)).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Save revision' }),
  ).toBeEnabled()

  const acceptanceTitle = 'OfficeFlow Help Publishing Acceptance'
  await page.getByLabel('Search help content').fill(acceptanceTitle)
  const acceptanceGuide = page.getByRole('button', { name: acceptanceTitle })
  if ((await acceptanceGuide.count()) === 0) {
    await page.getByLabel('Create guide').click()
    await page.getByLabel('Title').fill(acceptanceTitle)
    await page
      .getByLabel('Slug', { exact: true })
      .fill('officeflow-help-publishing-acceptance')
    await page.getByLabel('Category').fill('Administrator Handbook')
    await page
      .getByLabel('Summary')
      .fill('Controlled guide used to verify Help publishing and search.')
    await page.getByLabel('Workflow').selectOption('published')
    await page
      .getByLabel('Guide Markdown content')
      .fill(
        '# Publishing acceptance\n\n## Procedure\n\n1. Verify the guide is searchable.',
      )
    await page.getByLabel('Search keywords').fill('help publishing acceptance')
    await page
      .getByRole('button', { name: 'Create guide' })
      .filter({ hasText: 'Create guide' })
      .click()
    await expect(page.getByText(`Edit ${acceptanceTitle}`)).toBeVisible()
  } else {
    await acceptanceGuide.click()
  }
  await page
    .getByLabel('Summary')
    .fill('Controlled published guide verified through the Content Studio.')
  await page.getByRole('button', { name: 'Save revision' }).click()
  await expect(page.getByText(`Edit ${acceptanceTitle}`)).toBeVisible()

  await page.getByRole('tab', { name: 'Learn' }).click()
  await page
    .getByLabel('Search OfficeFlow help')
    .fill('help publishing acceptance')
  await expect(
    page.getByRole('button', { name: acceptanceTitle }),
  ).toBeVisible()

  await navigateTo(page, 'Finance')
  await page.getByRole('button', { name: 'Help for this page' }).click()
  await expect(
    page.getByRole('heading', { name: 'Help for this page' }),
  ).toBeVisible()
  await expect(page.getByText('Finance Center', { exact: true })).toBeVisible()
})

test('compact Administration and Help empty states remain usable', async ({
  page,
}) => {
  await login(page)

  const sidebar = page.getByRole('navigation', { name: 'Primary navigation' })
  await expect(
    sidebar.getByRole('link', { name: 'Administration', exact: true }),
  ).toHaveCount(1)
  await expect(sidebar.getByRole('link', { name: 'Users' })).toHaveCount(0)
  await navigateTo(page, 'Administration')
  await expect(page).toHaveURL('/administration')
  await expect(
    page.getByRole('heading', { name: 'Administration' }),
  ).toBeVisible()
  await expect(
    page.getByRole('navigation', { name: 'People & access' }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: /Users/ })).toBeVisible()

  await navigateTo(page, 'Help & Support')
  await page
    .getByLabel('Search OfficeFlow help')
    .fill(`no-result-${Date.now()}`)
  await expect(page.getByText('No guides found')).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Clear filters' }),
  ).toBeVisible()
})

test('themes and tablet layout remain readable without horizontal overflow', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await login(page)

  await page.getByRole('button', { name: 'Light theme' }).click()
  await expect(page.locator('html')).not.toHaveClass(/dark/)
  await page.getByRole('button', { name: 'Dark theme' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await navigateTo(page, 'Administration')
  await expect(
    page.getByRole('heading', { name: 'Administration' }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})

test('calendar can create, edit, and delete a real event', async ({ page }) => {
  await login(page)
  await navigateTo(page, 'Calendar')
  await expect(page).toHaveURL('/calendar')
  await page.getByRole('button', { name: 'New event' }).click()
  const title = `Polish verification ${Date.now()}`
  await page.getByLabel('Title').fill(title)
  const uniqueMinute = Date.now() % 1000
  const start = new Date(Date.UTC(2035, 0, 1, 0, uniqueMinute))
  const end = new Date(start.getTime() + 60 * 60 * 1000)
  await page.getByLabel('Starts').fill(start.toISOString().slice(0, 16))
  await page
    .getByRole('textbox', { name: 'Ends', exact: true })
    .fill(end.toISOString().slice(0, 16))
  await page.getByRole('button', { name: 'Create event', exact: true }).click()
  await page.getByRole('link', { name: 'Agenda', exact: true }).click()
  await expect(page.getByText(title)).toBeVisible()
  await page.getByText(title).click()
  await page.getByLabel('Title').fill(`${title} updated`)
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText(`${title} updated`)).toBeVisible()
  await page.getByText(`${title} updated`).click()
  await page.getByRole('button', { name: 'Delete' }).click()
  await expect(
    page.getByRole('heading', { name: 'Delete this item?' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Delete' }).last().click()
  await expect(page.getByText(`${title} updated`)).toHaveCount(0)
})

test('internal mail persists a sent rich-text message', async ({ page }) => {
  await login(page)
  await navigateTo(page, 'Mail')
  await expect(page).toHaveURL('/mail')
  await page.getByRole('button', { name: 'Compose', exact: true }).click()
  const subject = `Mail verification ${Date.now()}`
  await page
    .getByRole('textbox', { name: 'To recipients' })
    .fill(organizerEmail)
  await page.getByRole('textbox', { name: 'Subject' }).fill(subject)
  await page
    .getByRole('textbox', { name: 'Message body' })
    .fill('Verified from the production browser workflow.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText('Message sent')).toBeVisible()
  if ((page.viewportSize()?.width ?? 1280) < 1024)
    await page.getByRole('button', { name: 'Show mail folders' }).click()
  await page.getByRole('button', { name: /sent/i }).click()
  await expect(
    page.getByRole('heading', { name: subject, exact: true }),
  ).toBeVisible()
})

test('dashboard and chat have no serious automated accessibility violations', async ({
  page,
}) => {
  await login(page)
  let results = await new AxeBuilder({ page })
    .disableRules(['color-contrast'])
    .analyze()
  expect(
    results.violations.filter((violation) =>
      ['critical', 'serious'].includes(violation.impact ?? ''),
    ),
  ).toEqual([])
  await navigateTo(page, 'Chat')
  await expect(page).toHaveURL('/chat')
  results = await new AxeBuilder({ page })
    .disableRules(['color-contrast'])
    .analyze()
  expect(
    results.violations.filter((violation) =>
      ['critical', 'serious'].includes(violation.impact ?? ''),
    ),
  ).toEqual([])
})
