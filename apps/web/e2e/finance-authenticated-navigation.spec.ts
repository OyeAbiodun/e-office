import { expect, test } from '@playwright/test'

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value)
    throw new Error(`${name} must be set for finance browser acceptance`)
  return value
}

const email = requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL')
const password = requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD')

test('an authenticated finance user can revisit voucher and finance pages', async ({
  page,
}) => {
  const consoleErrors: string[] = []
  const failedApiRequests: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', (response) => {
    if (response.url().includes('/api/v1/') && response.status() >= 400) {
      failedApiRequests.push(
        `${response.status()} ${new URL(response.url()).pathname}${new URL(response.url()).search}`,
      )
    }
  })

  await page.goto('/login')
  await page.getByLabel('Work email').fill(email)
  const passwordInput = page.getByLabel('Password')
  await passwordInput.fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await passwordInput.fill('')
  await expect(page).toHaveURL('/', { timeout: 15_000 })

  await page.goto('/vouchers')
  await expect(page.getByRole('heading', { name: 'Vouchers' })).toBeVisible()
  await expect(page.getByLabel('Search vouchers')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Vouchers' })).toBeVisible()

  await page.goto('/finance')
  await expect(
    page.getByRole('heading', { name: 'Finance Center' }),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('heading', { name: 'Finance Center' }),
  ).toBeVisible()

  expect({ consoleErrors, failedApiRequests }).toEqual({
    consoleErrors: [],
    failedApiRequests: [],
  })
})
