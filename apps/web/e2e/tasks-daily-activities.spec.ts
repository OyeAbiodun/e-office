import {
  expect,
  type APIRequestContext,
  type Page,
  test,
} from '@playwright/test'
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
const apiBase = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8001/api/v1'

async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string,
) {
  const response = await request.post(`${apiBase}/auth/login`, {
    data: { email, password },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  const payload = (await response.json()) as {
    data: { access_token: string; user: { id: string } }
  }
  return {
    headers: { Authorization: `Bearer ${payload.data.access_token}` },
    userId: payload.data.user.id,
  }
}

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel(/work email|email/i).fill(organizerEmail)
  const password = page.getByLabel('Password')
  await password.fill(organizerPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await password.fill('').catch(() => undefined)
  await expect(page).toHaveURL('/', { timeout: 15_000 })
}

async function changeTemporaryPassword(
  request: APIRequestContext,
  email: string,
  temporaryPassword: string,
  finalPassword: string,
) {
  const session = await apiLogin(request, email, temporaryPassword)
  const response = await request.post(`${apiBase}/auth/change-password`, {
    headers: session.headers,
    data: {
      current_password: temporaryPassword,
      new_password: finalPassword,
      confirm_new_password: finalPassword,
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
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

test('a manager can assign only an active direct report', async ({
  browser,
  request,
}) => {
  test.setTimeout(180_000)
  const organizer = await apiLogin(request, organizerEmail, organizerPassword)
  const suffix = Date.now()
  const temporaryPassword = `TaskMgrTemp${suffix}!`
  const finalPassword = `TaskMgrFinal${suffix}!`
  const [workspacesResponse, rolesResponse] = await Promise.all([
    request.get(`${apiBase}/workspaces`, { headers: organizer.headers }),
    request.get(`${apiBase}/roles`, { headers: organizer.headers }),
  ])
  const workspaces = (await workspacesResponse.json()) as {
    data: Array<{ id: string }>
  }
  const roles = (await rolesResponse.json()) as {
    data: Array<{ id: string; name: string }>
  }
  const managerRole = roles.data.find((role) => role.name === 'Team Manager')
  const employeeRole = roles.data.find((role) => role.name === 'Employee')
  expect(managerRole && employeeRole).toBeTruthy()

  const createUser = async (body: Record<string, unknown>) => {
    const response = await request.post(`${apiBase}/users`, {
      headers: organizer.headers,
      data: {
        workspace_id: workspaces.data[0].id,
        temporary_password: temporaryPassword,
        send_welcome_email: false,
        ...body,
      },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    return (await response.json()) as {
      data: { id: string; email: string; display_name: string }
    }
  }
  const manager = await createUser({
    first_name: 'Manager',
    last_name: 'Acceptance',
    email: `manager.${suffix}@example.com`,
    role_ids: [managerRole?.id],
  })
  const report = await createUser({
    first_name: 'Report',
    last_name: 'Acceptance',
    email: `report.${suffix}@example.com`,
    role_ids: [employeeRole?.id],
    manager_id: manager.data.id,
  })
  const unrelated = await createUser({
    first_name: 'Unrelated',
    last_name: 'Acceptance',
    email: `unrelated.${suffix}@example.com`,
    role_ids: [employeeRole?.id],
  })
  await changeTemporaryPassword(
    request,
    manager.data.email,
    temporaryPassword,
    finalPassword,
  )
  await changeTemporaryPassword(
    request,
    report.data.email,
    temporaryPassword,
    finalPassword,
  )

  const managerContext = await browser.newContext({
    baseURL: process.env.PLAYWRIGHT_BASE_URL,
  })
  const managerPage = await managerContext.newPage()
  await managerPage.goto('/login')
  await managerPage.getByLabel('Work email').fill(manager.data.email)
  await managerPage.getByLabel('Password').fill(finalPassword)
  await managerPage.getByRole('button', { name: 'Sign in' }).click()
  await expect(managerPage).toHaveURL('/')
  const title = `Direct report task ${suffix}`
  await managerPage.goto('/tasks')
  await managerPage.getByRole('button', { name: 'New task' }).click()
  await managerPage.getByLabel('Title').fill(title)
  await managerPage
    .getByText('Assignment and reminder', { exact: true })
    .click()
  await managerPage
    .getByLabel('Search authorized employees')
    .fill(report.data.display_name)
  const allowed = managerPage.getByRole('option', {
    name: new RegExp(report.data.display_name),
  })
  await expect(allowed).toBeVisible()
  await expect(
    managerPage.getByText(unrelated.data.display_name, { exact: true }),
  ).toHaveCount(0)
  await allowed.click()
  await managerPage.getByRole('button', { name: 'Save' }).click()
  await managerPage.getByRole('button', { name: 'Created by me' }).click()
  await expect(managerPage.getByText(title, { exact: true })).toBeVisible()

  const managerSession = await apiLogin(
    request,
    manager.data.email,
    finalPassword,
  )
  const rejected = await request.post(`${apiBase}/tasks`, {
    headers: managerSession.headers,
    data: { title: 'Unauthorized assignment', assignee_id: unrelated.data.id },
  })
  expect(rejected.status()).toBe(403)
  const reportSession = await apiLogin(
    request,
    report.data.email,
    finalPassword,
  )
  const notifications = await request.get(`${apiBase}/notifications`, {
    headers: reportSession.headers,
  })
  expect(notifications.ok(), await notifications.text()).toBeTruthy()
  const inbox = (await notifications.json()) as {
    data: { notifications: Array<{ notification_type: string; body: string }> }
  }
  expect(
    inbox.data.notifications.some(
      (item) =>
        item.notification_type === 'task.assigned' && item.body.includes(title),
    ),
  ).toBeTruthy()

  const employeeContext = await browser.newContext({
    baseURL: process.env.PLAYWRIGHT_BASE_URL,
  })
  const employeePage = await employeeContext.newPage()
  await employeePage.goto('/login')
  await employeePage.getByLabel(/work email|email/i).fill(report.data.email)
  await employeePage.getByLabel('Password').fill(finalPassword)
  await employeePage.getByRole('button', { name: 'Sign in' }).click()
  await expect(employeePage).toHaveURL('/')
  await employeePage.goto('/tasks')
  await employeePage.getByRole('button', { name: 'Assigned to me' }).click()
  await expect(employeePage.getByText(title, { exact: true })).toBeVisible()
  await employeeContext.close()
  await managerContext.close()
})
