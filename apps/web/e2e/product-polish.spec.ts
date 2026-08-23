import AxeBuilder from '@axe-core/playwright'
import { expect, type Page, test } from '@playwright/test'

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Work email').fill('textabi12@gmail.com')
  await page.getByLabel('Password').fill('ChangeMe123!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL('/', { timeout: 15_000 })
  await expect(
    page.getByRole('heading', { name: /Good (morning|afternoon|evening)/ }),
  ).toBeVisible()
}

async function navigateTo(page: Page, label: string) {
  if ((page.viewportSize()?.width ?? 1280) >= 1024)
    await page.getByRole('link', { name: label, exact: true }).click()
  else {
    await page.getByRole('button', { name: 'Open navigation' }).click()
    await page.getByRole('link', { name: label, exact: true }).click()
  }
}

test('authenticated shell, command center, and navigation work', async ({
  page,
}) => {
  await login(page)
  await page.keyboard.press('Control+k')
  await expect(
    page.getByRole('dialog', { name: 'Search MeetingHQ' }),
  ).toBeVisible()
  await page.getByLabel('Search commands').fill('calendar')
  await page
    .getByRole('dialog', { name: 'Search MeetingHQ' })
    .getByRole('link', { name: 'Calendar Work navigation' })
    .click()
  await expect(page).toHaveURL('/calendar')
  await expect(page.getByRole('heading', { name: 'Calendar' })).toBeVisible()
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
    .fill('textabi12@gmail.com')
  await page.getByRole('textbox', { name: 'Subject' }).fill(subject)
  await page
    .getByRole('textbox', { name: 'Message body' })
    .fill('Verified from the production browser workflow.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText('Message sent')).toBeVisible()
  if ((page.viewportSize()?.width ?? 1280) < 1024)
    await page.getByRole('button', { name: 'Show mail folders' }).click()
  await page.getByRole('button', { name: /sent/i }).click()
  await expect(page.getByText(subject)).toBeVisible()
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
