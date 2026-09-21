import {
  expect,
  type APIRequestContext,
  type Browser,
  type Page,
  test,
} from '@playwright/test'

const apiBase = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8001/api/v1'
const webBase = process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5174'
type Headers = { Authorization: string }
type Entity = { id: string }
type User = Entity & { email: string }

function unwrap<T>(payload: { data: T }): T {
  return payload.data
}

async function loginApi(
  request: APIRequestContext,
  email: string,
  password: string,
) {
  const response = await request.post(`${apiBase}/auth/login`, {
    data: { email, password },
  })
  expect(response.ok(), `Login failed with ${response.status()}`).toBeTruthy()
  const result = unwrap<{ access_token: string; user: User }>(
    await response.json(),
  )
  return {
    headers: { Authorization: `Bearer ${result.access_token}` } as Headers,
    user: result.user,
  }
}

async function loginPage(page: Page, email: string, passwordValue: string) {
  await page.goto('/login')
  await page.getByLabel(/work email|email/i).fill(email)
  const password = page.getByLabel('Password')
  await password.fill(passwordValue)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await password.fill('').catch(() => undefined)
  await expect(page).toHaveURL('/', { timeout: 15_000 })
}

async function browserSession(
  browser: Browser,
  email: string,
  password: string,
  viewport = { width: 1440, height: 1000 },
) {
  const context = await browser.newContext({ baseURL: webBase, viewport })
  const page = await context.newPage()
  await loginPage(page, email, password)
  return { context, page }
}

test('reporting workflow is reviewable, permission-scoped, automated, and responsive', async ({
  browser,
  request,
}) => {
  test.setTimeout(300_000)
  const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`
  const adminPassword = `ReportAdmin${suffix}!Aa`
  const temporaryPassword = `ReportTemp${suffix}!Aa`
  const finalPassword = `ReportFinal${suffix}!Aa`
  const today = new Date().toISOString().slice(0, 10)
  const yesterdayDate = new Date()
  yesterdayDate.setUTCDate(yesterdayDate.getUTCDate() - 1)
  const yesterday = yesterdayDate.toISOString().slice(0, 10)

  const register = await request.post(`${apiBase}/auth/register`, {
    data: {
      organization_name: `Reporting Acceptance ${suffix}`,
      organization_slug: `reporting-acceptance-${suffix}`,
      workspace_name: 'Reporting Acceptance',
      email: `admin.${suffix}@reporting-acceptance.example`,
      username: `report.admin.${suffix}`,
      first_name: 'Report',
      last_name: 'Administrator',
      password: adminPassword,
    },
  })
  expect(register.ok(), await register.text()).toBeTruthy()
  const registered = unwrap<{ access_token: string; user: User }>(
    await register.json(),
  )
  const adminHeaders: Headers = {
    Authorization: `Bearer ${registered.access_token}`,
  }
  const [workspaceResponse, rolesResponse] = await Promise.all([
    request.get(`${apiBase}/workspaces`, { headers: adminHeaders }),
    request.get(`${apiBase}/roles`, { headers: adminHeaders }),
  ])
  const workspace = unwrap<Entity[]>(await workspaceResponse.json())[0]
  const roles = unwrap<Array<Entity & { name: string }>>(
    await rolesResponse.json(),
  )
  const roleId = (name: string) => roles.find((role) => role.name === name)!.id

  const createUser = async (
    label: string,
    role: string,
    managerId?: string,
  ) => {
    const response = await request.post(`${apiBase}/users`, {
      headers: adminHeaders,
      data: {
        first_name: label,
        last_name: 'Reporting acceptance',
        email: `${label.toLowerCase()}.${suffix}@reporting-acceptance.example`,
        job_title: label,
        role_ids: [roleId(role)],
        workspace_id: workspace.id,
        manager_id: managerId,
        temporary_password: temporaryPassword,
        send_welcome_email: false,
      },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    const user = unwrap<User>(await response.json())
    const temporary = await loginApi(request, user.email, temporaryPassword)
    const changed = await request.post(`${apiBase}/auth/change-password`, {
      headers: temporary.headers,
      data: {
        current_password: temporaryPassword,
        new_password: finalPassword,
        confirm_new_password: finalPassword,
      },
    })
    expect(changed.ok(), await changed.text()).toBeTruthy()
    return user
  }

  const manager = await createUser('Manager', 'Team Manager')
  const employee = await createUser('Employee', 'Employee', manager.id)
  const outsider = await createUser('Outsider', 'Employee')
  const managerApi = await loginApi(request, manager.email, finalPassword)
  const employeeApi = await loginApi(request, employee.email, finalPassword)

  const projectResponse = await request.post(`${apiBase}/projects`, {
    headers: adminHeaders,
    data: {
      name: `Reporting project ${suffix}`,
      project_manager_id: manager.id,
      member_ids: [employee.id],
      start_date: yesterday,
      target_end_date: today,
    },
  })
  expect(projectResponse.ok(), await projectResponse.text()).toBeTruthy()
  const project = unwrap<Entity>(await projectResponse.json())
  const taskResponse = await request.post(`${apiBase}/tasks`, {
    headers: managerApi.headers,
    data: {
      title: `Reporting evidence ${suffix}`,
      assignee_id: employee.id,
      project_id: project.id,
      due_date: today,
    },
  })
  expect(taskResponse.ok(), await taskResponse.text()).toBeTruthy()
  const task = unwrap<Entity>(await taskResponse.json())
  const openGeneratedEmployeeReport = async (
    page: Page,
    start: string,
    end: string,
  ) => {
    await page.goto('/reports')
    await page.getByRole('button', { name: 'Generate report' }).click()
    const form = page.getByRole('form', { name: 'Generate report' })
    await form
      .getByLabel('Period')
      .selectOption(start === end ? 'daily' : 'custom')
    await form.getByLabel('Start date').fill(start)
    await form.getByLabel('End date').fill(end)
    await form.getByRole('button', { name: 'Generate draft' }).click()
    await expect(page).toHaveURL(/\/reports\/[0-9a-f-]{36}$/)
    return page.url().split('/').pop()!
  }
  const saveAndSubmit = async (page: Page, accomplishment: string) => {
    await page.getByLabel('Accomplishments').fill(accomplishment)
    await page.getByRole('button', { name: 'Save draft' }).click()
    await expect(
      page.getByRole('definition').filter({ hasText: /^Draft$/ }),
    ).toBeVisible()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: 'Submit for review' }).click()
    await expect(
      page.getByRole('definition').filter({ hasText: /^Submitted$/ }),
    ).toBeVisible()
  }

  const employeeBrowser = await browserSession(
    browser,
    employee.email,
    finalPassword,
  )
  await employeeBrowser.page.goto('/tasks')
  await employeeBrowser.page
    .getByRole('button', { name: 'Log activity' })
    .click()
  const activityForm = employeeBrowser.page.getByRole('dialog')
  await activityForm.getByLabel('Activity date').fill(yesterday)
  await activityForm
    .getByLabel('Summary')
    .fill('Prepared verified reporting evidence.')
  await activityForm.getByLabel('Related task').selectOption(task.id)
  await activityForm.getByLabel('Minutes spent').fill('45')
  await activityForm.getByLabel('Outcome').fill('Evidence package prepared.')
  await activityForm.getByRole('button', { name: 'Save' }).click()
  await expect(
    employeeBrowser.page.getByText('Prepared verified reporting evidence.'),
  ).toBeVisible()
  await employeeBrowser.page
    .getByRole('button', { name: 'Edit activity' })
    .click()
  const editActivityForm = employeeBrowser.page.getByRole('dialog')
  await editActivityForm
    .getByLabel('Summary')
    .fill('Prepared and validated reporting evidence.')
  await editActivityForm
    .getByLabel('Outcome')
    .fill('Evidence package validated and ready for review.')
  await editActivityForm.getByRole('button', { name: 'Save' }).click()
  await expect(
    employeeBrowser.page.getByText(
      'Prepared and validated reporting evidence.',
    ),
  ).toBeVisible()

  const firstReport = await openGeneratedEmployeeReport(
    employeeBrowser.page,
    today,
    today,
  )
  await saveAndSubmit(
    employeeBrowser.page,
    'Completed the verified reporting evidence.',
  )

  const managerBrowser = await browserSession(
    browser,
    manager.email,
    finalPassword,
  )
  await managerBrowser.page.goto(`/reports/${firstReport}`)
  await expect(
    managerBrowser.page
      .getByRole('definition')
      .filter({ hasText: /^Submitted$/ }),
  ).toBeVisible()
  await managerBrowser.page
    .getByRole('button', { name: 'Accept and finalize' })
    .click()
  await expect(
    managerBrowser.page.getByRole('definition').filter({ hasText: /^Final$/ }),
  ).toBeVisible()

  const secondReport = await openGeneratedEmployeeReport(
    employeeBrowser.page,
    yesterday,
    yesterday,
  )
  const priorReport = await request.get(`${apiBase}/reports/${secondReport}`, {
    headers: employeeApi.headers,
  })
  expect(priorReport.ok(), await priorReport.text()).toBeTruthy()
  const priorSnapshot = unwrap<{
    report: {
      authoritative_snapshot: {
        activities: Array<{ summary: string; outcome: string | null }>
      }
    }
  }>(await priorReport.json()).report.authoritative_snapshot
  expect(priorSnapshot.activities).toContainEqual(
    expect.objectContaining({
      summary: 'Prepared and validated reporting evidence.',
      outcome: 'Evidence package validated and ready for review.',
    }),
  )
  await saveAndSubmit(
    employeeBrowser.page,
    'Reviewed the prior-period work record.',
  )
  await managerBrowser.page.goto(`/reports/${secondReport}`)
  await managerBrowser.page
    .getByLabel('Return note')
    .fill('Add the validation outcome.')
  await managerBrowser.page.getByRole('button', { name: 'Return' }).click()
  await expect(
    managerBrowser.page
      .getByRole('definition')
      .filter({ hasText: /^Returned$/ }),
  ).toBeVisible()
  await employeeBrowser.page.goto(`/reports/${secondReport}`)
  await expect(
    employeeBrowser.page.getByText('Returned for correction'),
  ).toBeVisible()
  await employeeBrowser.page
    .getByLabel('Accomplishments')
    .fill('Reviewed the work record and added the validation outcome.')
  await employeeBrowser.page.getByRole('button', { name: 'Save draft' }).click()
  employeeBrowser.page.once('dialog', (dialog) => dialog.accept())
  await employeeBrowser.page
    .getByRole('button', { name: 'Submit for review' })
    .click()
  await managerBrowser.page.goto(`/reports/${secondReport}`)
  await managerBrowser.page
    .getByRole('button', { name: 'Accept and finalize' })
    .click()
  await expect(
    managerBrowser.page.getByRole('definition').filter({ hasText: /^Final$/ }),
  ).toBeVisible()

  await managerBrowser.page.goto('/reports')
  await managerBrowser.page
    .getByRole('button', { name: 'Generate report' })
    .click()
  const projectForm = managerBrowser.page.getByRole('form', {
    name: 'Generate report',
  })
  await projectForm.getByLabel('Report scope').selectOption('project')
  await projectForm.getByLabel('Subject').selectOption(project.id)
  await projectForm.getByLabel('Period').selectOption('custom')
  await projectForm.getByLabel('Start date').fill(yesterday)
  await projectForm.getByLabel('End date').fill(today)
  await projectForm.getByRole('button', { name: 'Generate draft' }).click()
  await expect(
    managerBrowser.page.getByRole('heading', {
      name: `Reporting project ${suffix}`,
    }),
  ).toBeVisible()
  const projectReportId = managerBrowser.page.url().split('/').pop()!
  await managerBrowser.page.goto(`/projects/${project.id}`)
  await managerBrowser.page
    .getByRole('button', { name: 'Reports', exact: true })
    .click()
  await expect(
    managerBrowser.page.locator(`a[href="/reports/${projectReportId}"]`),
  ).toBeVisible()

  const outsiderBrowser = await browserSession(
    browser,
    outsider.email,
    finalPassword,
  )
  await outsiderBrowser.page.goto(`/reports/${firstReport}`)
  await expect(
    outsiderBrowser.page.getByText(/unavailable or you do not have access/i),
  ).toBeVisible()

  const adminBrowser = await browserSession(
    browser,
    registered.user.email,
    adminPassword,
  )
  await adminBrowser.page.goto('/reports')
  await adminBrowser.page
    .getByRole('button', { name: 'Reporting policy' })
    .click()
  await adminBrowser.page
    .getByLabel('Automatically submit generated reports')
    .check()
  await adminBrowser.page.getByLabel('Submission deadline (hours)').fill('1')
  adminBrowser.page.once('dialog', (dialog) => dialog.accept())
  const policySaved = adminBrowser.page.waitForResponse(
    (response) =>
      response.url().endsWith('/reports/policy') &&
      response.request().method() === 'PUT',
  )
  await adminBrowser.page
    .getByRole('button', { name: 'Save reporting policy' })
    .click()
  expect((await policySaved).ok()).toBeTruthy()
  // Give the scheduler a user/period combination that was not already generated
  // manually above; this keeps the idempotency assertion meaningful on reruns.
  await createUser('Automated', 'Employee', manager.id)
  const scheduled = await request.post(`${apiBase}/reports/scheduler/run`, {
    headers: adminHeaders,
  })
  expect(scheduled.ok(), await scheduled.text()).toBeTruthy()
  const generated = unwrap<{ generated: number }>(
    await scheduled.json(),
  ).generated
  expect(generated).toBeGreaterThanOrEqual(0)
  const automated = await request.get(`${apiBase}/reports`, {
    headers: adminHeaders,
    params: { status: 'pending_review', page_size: 100 },
  })
  expect(automated.ok()).toBeTruthy()
  if (generated > 0)
    expect(
      unwrap<{ items: Array<{ submission_mode: string | null }> }>(
        await automated.json(),
      ).items.some((report) => report.submission_mode === 'automatic'),
    ).toBeTruthy()

  const mobile = await browserSession(browser, employee.email, finalPassword, {
    width: 390,
    height: 844,
  })
  await mobile.page.goto('/reports')
  await expect(
    mobile.page.getByRole('heading', { name: 'Reports & Intelligence' }),
  ).toBeVisible()
  await mobile.page.goto(`/reports/${firstReport}`)
  await expect(
    mobile.page.getByRole('heading', { name: 'Employee Reporting acceptance' }),
  ).toBeVisible()
  expect(
    await mobile.page.evaluate(
      () => document.documentElement.scrollWidth <= 392,
    ),
  ).toBeTruthy()

  await Promise.all([
    employeeBrowser.context.close(),
    managerBrowser.context.close(),
    outsiderBrowser.context.close(),
    adminBrowser.context.close(),
    mobile.context.close(),
  ])
})
