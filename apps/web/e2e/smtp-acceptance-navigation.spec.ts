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
}

test('authenticated delivery-related centers support direct URLs and refresh', async ({
  page,
}) => {
  test.setTimeout(90_000)
  await login(page)

  const pages = [
    ['/integrations', 'Integration Center'],
    ['/mail', 'Mail'],
    ['/meetings', 'Your collaboration hub'],
    ['/calendar', 'Calendar'],
    ['/notifications', 'Notification Center'],
    ['/system-health', 'System Health'],
    ['/audit', 'Audit Center'],
  ] as const

  for (const [path, heading] of pages) {
    await page.goto(path)
    await expect(page).toHaveURL(path)
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
    await page.reload()
    await expect(page).toHaveURL(path)
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  }
})
