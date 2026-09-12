import { expect, test } from '@playwright/test'

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value)
    throw new Error(`${name} must be set for payroll browser acceptance`)
  return value
}

const email = requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL')
const password = requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD')

test('authorized payroll user can navigate the secure payroll workspace', async ({
  page,
}) => {
  const consoleErrors: string[] = []
  const failedPayrollRequests: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', (response) => {
    if (response.url().includes('/api/v1/payroll') && response.status() >= 400)
      failedPayrollRequests.push(
        `${response.status()} ${new URL(response.url()).pathname}`,
      )
  })

  await page.goto('/login')
  await page.getByLabel('Work email').fill(email)
  const passwordInput = page.getByLabel('Password')
  await passwordInput.fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await passwordInput.fill('')
  await expect(page).toHaveURL('/', { timeout: 15_000 })

  await page.goto('/payroll')
  await expect(
    page.getByRole('heading', { name: 'Payroll', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText('Salary data is permission restricted'),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Payroll runs' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'My payslips' })).toBeVisible()
  await page.getByRole('button', { name: 'Salary structures' }).click()
  await expect(
    page.getByRole('heading', { name: 'Effective-dated salary structures' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Components' }).click()
  await expect(
    page.getByRole('heading', { name: 'Salary components' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Statutory rules' }).click()
  await expect(
    page.getByRole('heading', { name: 'Statutory and payroll policy' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Loans' }).click()
  await expect(
    page.getByRole('heading', { name: 'Employee loans' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Reports' }).click()
  await expect(
    page.getByRole('heading', {
      name: 'Payroll reports and statutory exports',
    }),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('heading', { name: 'Payroll', exact: true }),
  ).toBeVisible()

  expect({ consoleErrors, failedPayrollRequests }).toEqual({
    consoleErrors: [],
    failedPayrollRequests: [],
  })
})
