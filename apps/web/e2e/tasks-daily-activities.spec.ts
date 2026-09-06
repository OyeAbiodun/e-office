import { expect, type Page, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value) throw new Error(`${name} must be set for task browser acceptance`)
  return value
}

const organizerEmail = requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL')
const organizerPassword = requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD')
const attachmentFixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  'fixtures/task-acceptance.txt',
)

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel(/work email|email/i).fill(organizerEmail)
  const password = page.getByLabel('Password')
  await password.fill(organizerPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await password.fill('').catch(() => undefined)
  await expect(page).toHaveURL('/', { timeout: 15_000 })
}

test('a user can create, complete, and log activity against a task', async ({
  page,
}) => {
  await login(page)
  const title = `Task acceptance ${Date.now()}`

  await page.goto('/tasks')
  await expect(page.getByRole('heading', { name: 'My Work' })).toBeVisible()
  const activityLabel = page.getByText('Activities', { exact: true })
  const activityCount = Number(
    await activityLabel.locator('xpath=preceding-sibling::p[1]').innerText(),
  )
  await page.getByRole('button', { name: 'New task' }).click()
  await page.getByLabel('Title').fill(title)
  await page.getByRole('button', { name: 'Save' }).click()

  // Today is intentionally a focused queue. Broader scopes must not preserve
  // that implicit due-date filter, otherwise undated tasks disappear.
  await page.getByRole('button', { name: 'Created by me' }).click()
  await expect(page.getByText(title, { exact: true })).toBeVisible()
  await page.getByText(title, { exact: true }).click()

  const taskDialog = page.getByRole('dialog')
  await taskDialog
    .getByLabel('New checklist item')
    .fill('Confirm the customer handoff')
  await taskDialog.getByRole('button', { name: 'Add' }).click()
  const checkbox = taskDialog.getByLabel(
    'Complete Confirm the customer handoff',
  )
  await expect(checkbox).toBeVisible()
  await checkbox.click()
  await expect(checkbox).toBeChecked({ timeout: 5_000 })
  await taskDialog
    .getByLabel('Upload task attachment')
    .setInputFiles(attachmentFixture)
  await expect(taskDialog.getByText(/task-acceptance\.txt/)).toBeVisible({
    timeout: 10_000,
  })
  await taskDialog.getByRole('button').first().click()

  await page.getByRole('button', { name: 'Log today' }).click()
  const activityDialog = page.getByRole('dialog')
  await activityDialog
    .getByLabel('Summary')
    .fill('Recorded the acceptance activity.')
  await activityDialog.getByLabel('Minutes spent').fill('15')
  await activityDialog.getByRole('button', { name: 'Save' }).click()

  await expect(page.getByText('Completed successfully')).toBeVisible()
  await page.reload()
  await expect(
    page
      .getByText('Activities', { exact: true })
      .locator('xpath=preceding-sibling::p[1]'),
  ).toHaveText(String(activityCount + 1), { timeout: 15_000 })
})
