import {
  expect,
  type APIRequestContext,
  type Page,
  test,
} from '@playwright/test'

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value)
    throw new Error(`${name} must be set for leave browser acceptance`)
  return value
}

const organizerEmail = requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL')
const organizerPassword = requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD')
const apiBase = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8001/api/v1'

interface SmtpConfiguration {
  provider_display_name: string
  host: string
  port: number
  security_mode: 'starttls' | 'ssl_tls' | 'none'
  allow_insecure: boolean
  connection_timeout: number
  authentication_enabled: boolean
  authentication_method: 'password'
  username: string | null
  from_email: string
  from_name: string
  reply_to: string | null
  return_path: string | null
  enabled: boolean
  max_retry_attempts: number
  retry_delay_seconds: number
  timeout_seconds: number
  default_priority: 'low' | 'normal' | 'high'
}

function smtpPayload(configuration: SmtpConfiguration, enabled: boolean) {
  return {
    provider_display_name: configuration.provider_display_name,
    host: configuration.host,
    port: configuration.port,
    security_mode: configuration.security_mode,
    allow_insecure: configuration.allow_insecure,
    connection_timeout: configuration.connection_timeout,
    authentication_enabled: configuration.authentication_enabled,
    authentication_method: configuration.authentication_method,
    username: configuration.username,
    from_email: configuration.from_email,
    from_name: configuration.from_name,
    reply_to: configuration.reply_to,
    return_path: configuration.return_path,
    enabled,
    max_retry_attempts: configuration.max_retry_attempts,
    retry_delay_seconds: configuration.retry_delay_seconds,
    timeout_seconds: configuration.timeout_seconds,
    default_priority: configuration.default_priority,
  }
}

async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string,
) {
  let response = await request.post(`${apiBase}/auth/login`, {
    data: { email, password },
  })
  for (let attempt = 0; response.status() === 401 && attempt < 4; attempt++) {
    await new Promise((resolve) => setTimeout(resolve, 200 * (attempt + 1)))
    response = await request.post(`${apiBase}/auth/login`, {
      data: { email, password },
    })
  }
  expect(response.ok(), await response.text()).toBeTruthy()
  const payload = (await response.json()) as {
    data: { access_token: string; user: { id: string } }
  }
  return {
    headers: { Authorization: `Bearer ${payload.data.access_token}` },
    userId: payload.data.user.id,
  }
}

async function login(page: Page, email: string, passwordValue: string) {
  await page.goto('/login')
  await page.getByLabel(/work email|email/i).fill(email)
  const password = page.getByLabel('Password')
  await password.fill(passwordValue)
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

test('employee request, manager approval, calendar, balance adjustment, and mobile flow', async ({
  browser,
  request,
}, testInfo) => {
  test.setTimeout(240_000)
  const organizer = await apiLogin(request, organizerEmail, organizerPassword)
  const smtpResponse = await request.get(
    `${apiBase}/integrations/smtp/configuration`,
    { headers: organizer.headers },
  )
  const smtpConfiguration = smtpResponse.ok()
    ? ((await smtpResponse.json()) as { data: SmtpConfiguration }).data
    : null
  if (smtpConfiguration?.enabled) {
    const disabled = await request.put(
      `${apiBase}/integrations/smtp/configuration`,
      {
        headers: organizer.headers,
        data: smtpPayload(smtpConfiguration, false),
      },
    )
    expect(disabled.ok(), await disabled.text()).toBeTruthy()
  }

  try {
    const suffix = Date.now()
    const temporaryPassword = `LeaveTemp${suffix}!`
    const finalPassword = `LeaveFinal${suffix}!`
    const today = new Date()
    const start = new Date(today)
    start.setDate(start.getDate() + 14)
    const end = new Date(start)
    end.setDate(end.getDate() + 2)
    const startDate = start.toISOString().slice(0, 10)
    const endDate = end.toISOString().slice(0, 10)
    const futureDate = (offset: number) => {
      const value = new Date(today)
      value.setDate(value.getDate() + offset)
      return value.toISOString().slice(0, 10)
    }
    const nextWorkingDate = (offset: number) => {
      const value = new Date(today)
      value.setDate(value.getDate() + offset)
      while (value.getDay() === 0 || value.getDay() === 6) {
        value.setDate(value.getDate() + 1)
      }
      return value
    }
    const rejectedStart = nextWorkingDate(25)
    const rejectedEnd = new Date(rejectedStart)
    rejectedEnd.setDate(rejectedEnd.getDate() + 1)
    while (rejectedEnd.getDay() === 0 || rejectedEnd.getDay() === 6) {
      rejectedEnd.setDate(rejectedEnd.getDate() + 1)
    }

    const [workspacesResponse, rolesResponse] = await Promise.all([
      request.get(`${apiBase}/workspaces`, { headers: organizer.headers }),
      request.get(`${apiBase}/roles`, { headers: organizer.headers }),
    ])
    let periodResponse = await request.get(
      `${apiBase}/leave/periods/current?on_date=${today.toISOString().slice(0, 10)}`,
      { headers: organizer.headers },
    )
    if (periodResponse.status() === 404) {
      periodResponse = await request.post(`${apiBase}/leave/periods`, {
        headers: organizer.headers,
        data: {
          name: `Acceptance ${today.getUTCFullYear()}`,
          start_date: `${today.getUTCFullYear()}-01-01`,
          end_date: `${today.getUTCFullYear()}-12-31`,
          status: 'open',
        },
      })
    }
    expect(
      workspacesResponse.ok(),
      await workspacesResponse.text(),
    ).toBeTruthy()
    expect(rolesResponse.ok(), await rolesResponse.text()).toBeTruthy()
    expect(periodResponse.ok(), await periodResponse.text()).toBeTruthy()
    const workspaces = (await workspacesResponse.json()) as {
      data: Array<{ id: string }>
    }
    const roles = (await rolesResponse.json()) as {
      data: Array<{ id: string; name: string }>
    }
    const period = (await periodResponse.json()) as { data: { id: string } }
    const employeeRole = roles.data.find((role) => role.name === 'Employee')
    expect(employeeRole).toBeTruthy()

    const employeeResponse = await request.post(`${apiBase}/users`, {
      headers: organizer.headers,
      data: {
        first_name: 'Leave',
        last_name: 'Acceptance',
        email: `leave.${suffix}@example.com`,
        role_ids: [employeeRole?.id],
        workspace_id: workspaces.data[0]?.id,
        manager_id: organizer.userId,
        temporary_password: temporaryPassword,
        send_welcome_email: false,
      },
    })
    expect(employeeResponse.ok(), await employeeResponse.text()).toBeTruthy()
    const employee = (await employeeResponse.json()) as {
      data: { id: string; email: string }
    }
    await changeTemporaryPassword(
      request,
      employee.data.email,
      temporaryPassword,
      finalPassword,
    )

    const typeResponse = await request.post(`${apiBase}/leave/types`, {
      headers: organizer.headers,
      data: {
        name: `Acceptance Leave ${suffix}`,
        code: `ACC${suffix}`,
        description: 'Controlled browser acceptance policy',
        is_active: true,
        is_paid: true,
        default_entitlement: 8,
        accrual_enabled: false,
        accrual_frequency: null,
        carryover_enabled: false,
        carryover_limit: null,
        carryover_expiry_months: null,
        minimum_notice_days: 0,
        maximum_consecutive_days: 30,
        attachment_required: false,
        half_day_supported: true,
        eligible_employment_types: [],
        probation_eligible: true,
        color: '#2563eb',
      },
    })
    expect(typeResponse.ok(), await typeResponse.text()).toBeTruthy()
    const leaveType = (await typeResponse.json()) as {
      data: { id: string; name: string }
    }
    const entitlement = await request.post(`${apiBase}/leave/entitlements`, {
      headers: organizer.headers,
      data: {
        employee_id: employee.data.id,
        leave_type_id: leaveType.data.id,
        leave_period_id: period.data.id,
        allocated_days: 8,
        reason: 'Browser acceptance allocation',
      },
    })
    expect(entitlement.ok(), await entitlement.text()).toBeTruthy()

    const employeeContext = await browser.newContext({
      baseURL: process.env.PLAYWRIGHT_BASE_URL,
    })
    const employeePage = await employeeContext.newPage()
    await login(employeePage, employee.data.email, finalPassword)
    await employeePage.goto('/leave')
    await expect(
      employeePage.getByRole('heading', { name: 'My Leave' }),
    ).toBeVisible()
    await expect(
      employeePage.getByText(leaveType.data.name, { exact: true }).first(),
    ).toBeVisible()
    await employeePage.screenshot({
      fullPage: true,
      path: testInfo.outputPath('01-my-leave-desktop.png'),
    })
    await employeePage
      .getByRole('button', { name: 'Request leave' })
      .first()
      .click()
    const requestDialog = employeePage.getByRole('dialog')
    await requestDialog.getByLabel('Leave type').selectOption(leaveType.data.id)
    await requestDialog.getByLabel('Start date').fill(startDate)
    await requestDialog.getByLabel('End date').fill(endDate)
    await expect(requestDialog.getByText(/Chargeable/)).toBeVisible()
    await requestDialog
      .getByLabel('Reason or note')
      .fill('Controlled lifecycle acceptance')
    await requestDialog.getByRole('button', { name: 'Submit request' }).click()
    await expect(requestDialog).toBeHidden({ timeout: 15_000 })
    await expect(
      employeePage.getByText(leaveType.data.name, { exact: true }).last(),
    ).toBeVisible()
    await employeePage
      .getByText(leaveType.data.name, { exact: true })
      .last()
      .click()
    await expect(employeePage).toHaveURL(/\/leave\/requests\//)
    const requestId = employeePage.url().split('/').at(-1)!
    await expect(
      employeePage.getByText('Submitted', { exact: true }),
    ).toBeVisible()

    const managerContext = await browser.newContext({
      baseURL: process.env.PLAYWRIGHT_BASE_URL,
    })
    const managerPage = await managerContext.newPage()
    await login(managerPage, organizerEmail, organizerPassword)
    await managerPage.goto('/leave/team')
    await expect(
      managerPage.getByRole('heading', { name: 'Team Leave' }),
    ).toBeVisible()
    await managerPage
      .getByPlaceholder('Search employee')
      .fill('Leave Acceptance')
    const approvalRequestLink = managerPage.locator(
      `a[href="/leave/requests/${requestId}"]`,
    )
    await expect(approvalRequestLink).toBeVisible({ timeout: 15_000 })
    await managerPage.screenshot({
      fullPage: true,
      path: testInfo.outputPath('02-team-leave-desktop.png'),
    })
    await approvalRequestLink.click()
    await expect(managerPage).toHaveURL(
      new RegExp(`/leave/requests/${requestId}`),
    )
    await managerPage.getByRole('button', { name: 'Approve' }).click()
    await managerPage
      .getByRole('dialog')
      .getByRole('button', { name: 'Approve' })
      .click()
    await expect(managerPage.getByText(/^approved$/i).first()).toBeVisible({
      timeout: 15_000,
    })

    await employeePage.reload()
    await expect(employeePage.getByText(/^approved$/i).first()).toBeVisible()
    const employeeSession = await apiLogin(
      request,
      employee.data.email,
      finalPassword,
    )
    const detailResponse = await request.get(
      `${apiBase}/leave/requests/${requestId}`,
      { headers: employeeSession.headers },
    )
    const detail = (await detailResponse.json()) as {
      data: { calendar_event_id: string | null }
    }
    expect(detail.data.calendar_event_id).toBeTruthy()
    const calendarsResponse = await request.get(`${apiBase}/calendars`, {
      headers: employeeSession.headers,
    })
    const calendars = (await calendarsResponse.json()) as {
      data: Array<{ id: string }>
    }
    const eventResults = await Promise.all(
      calendars.data.map((calendar) =>
        request.get(`${apiBase}/calendars/${calendar.id}/events`, {
          headers: employeeSession.headers,
        }),
      ),
    )
    const eventPayloads = await Promise.all(
      eventResults.map(
        (response) =>
          response.json() as Promise<{ data: Array<{ id: string }> }>,
      ),
    )
    expect(
      eventPayloads
        .flatMap((payload) => payload.data)
        .filter((event) => event.id === detail.data.calendar_event_id),
    ).toHaveLength(1)

    await employeePage.goto('/leave')
    await employeePage
      .getByRole('button', { name: 'Request leave' })
      .first()
      .click()
    const excessiveDialog = employeePage.getByRole('dialog')
    await excessiveDialog
      .getByLabel('Leave type')
      .selectOption(leaveType.data.id)
    await excessiveDialog.getByLabel('Start date').fill(futureDate(35))
    await excessiveDialog.getByLabel('End date').fill(futureDate(49))
    await expect(excessiveDialog.getByRole('alert')).toContainText(
      /available, but this request requires/i,
    )
    await expect(
      excessiveDialog.getByRole('button', { name: 'Submit request' }),
    ).toBeDisabled()
    await excessiveDialog.getByRole('button', { name: 'Close dialog' }).click()

    await employeePage
      .getByRole('button', { name: 'Request leave' })
      .first()
      .click()
    const rejectedDialog = employeePage.getByRole('dialog')
    await rejectedDialog
      .getByLabel('Leave type')
      .selectOption(leaveType.data.id)
    await rejectedDialog
      .getByLabel('Start date')
      .fill(rejectedStart.toISOString().slice(0, 10))
    await rejectedDialog
      .getByLabel('End date')
      .fill(rejectedEnd.toISOString().slice(0, 10))
    await rejectedDialog
      .getByLabel('Reason or note')
      .fill('Controlled rejection acceptance')
    await rejectedDialog.getByRole('button', { name: 'Submit request' }).click()
    await expect(rejectedDialog).toBeHidden({ timeout: 15_000 })

    await managerPage.goto('/leave/team')
    const pendingRequestLink = managerPage.getByRole('link', {
      name: new RegExp(leaveType.data.name),
    })
    await expect(pendingRequestLink).toBeVisible({ timeout: 15_000 })
    await pendingRequestLink.click()
    await expect(managerPage).toHaveURL(/\/leave\/requests\//)
    const rejectedRequestId = managerPage.url().split('/').at(-1)!
    await managerPage.getByRole('button', { name: 'Reject' }).click()
    const rejection = managerPage.getByRole('dialog', {
      name: 'Reject leave request',
    })
    await rejection
      .getByLabel('Reason for rejection')
      .fill('Coverage is unavailable for those dates.')
    await rejection.getByRole('button', { name: 'Reject request' }).click()
    await expect(managerPage.getByText(/^rejected$/i).first()).toBeVisible()
    await employeePage.goto(`/leave/requests/${rejectedRequestId}`)
    await expect(employeePage.getByText(/^rejected$/i).first()).toBeVisible()
    await expect(
      employeePage
        .getByText('Coverage is unavailable for those dates.')
        .first(),
    ).toBeVisible()

    await managerPage.goto('/leave/admin')
    await expect(
      managerPage.getByRole('heading', { name: 'Leave Types' }),
    ).toBeVisible()
    await managerPage.screenshot({
      fullPage: true,
      path: testInfo.outputPath('03-leave-administration.png'),
    })
    await managerPage.getByRole('button', { name: /Leave Balances/ }).click()
    await managerPage.getByLabel('Employee').selectOption(employee.data.id)
    await managerPage.getByLabel('Leave type').selectOption(leaveType.data.id)
    await managerPage
      .getByRole('button', { name: 'Adjust Leave Acceptance balance' })
      .click()
    const adjustment = managerPage.getByRole('dialog')
    await adjustment.getByLabel('Amount').fill('1')
    await adjustment
      .getByLabel('Reason')
      .fill('Controlled browser acceptance adjustment')
    await adjustment.getByRole('button', { name: 'Record adjustment' }).click()
    await managerPage
      .getByRole('dialog', { name: /Adjust Leave Acceptance/ })
      .getByRole('button', { name: 'Record adjustment' })
      .click()
    await expect(adjustment).toBeHidden({ timeout: 15_000 })
    await managerPage.screenshot({
      fullPage: true,
      path: testInfo.outputPath('04-balance-management.png'),
    })
    await managerPage.getByRole('button', { name: /Leave Periods/ }).click()
    await expect(
      managerPage.getByRole('heading', { name: 'Leave Periods' }),
    ).toBeVisible()
    await managerPage
      .getByRole('button', { name: /Holidays & Working Days/ })
      .click()
    await expect(
      managerPage.getByRole('heading', { name: 'Working week' }),
    ).toBeVisible()
    await managerPage.getByRole('button', { name: 'Reports' }).click()
    await expect(
      managerPage.getByRole('heading', { name: 'Leave Reports' }),
    ).toBeVisible()

    await employeePage.goto('/leave')
    const balanceCard = employeePage
      .getByLabel('Leave balances')
      .locator('article')
      .filter({ hasText: leaveType.data.name })
    await expect(balanceCard.getByText('6', { exact: true })).toBeVisible()

    const mobileContext = await browser.newContext({
      baseURL: process.env.PLAYWRIGHT_BASE_URL,
      viewport: { width: 390, height: 844 },
    })
    const mobilePage = await mobileContext.newPage()
    await login(mobilePage, employee.data.email, finalPassword)
    await mobilePage.goto('/leave')
    await expect(
      mobilePage.getByRole('heading', { name: 'My Leave' }),
    ).toBeVisible()
    await mobilePage
      .getByRole('button', { name: 'Request leave' })
      .first()
      .click()
    await expect(
      mobilePage.getByRole('dialog').getByLabel('Start date'),
    ).toBeVisible()
    await mobilePage.screenshot({
      fullPage: true,
      path: testInfo.outputPath('05-request-leave-mobile.png'),
    })
    const overflow = await mobilePage.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
    )
    expect(overflow).toBeFalsy()
    await mobileContext.close()
    await managerContext.close()
    await employeeContext.close()
  } finally {
    if (smtpConfiguration?.enabled) {
      const restored = await request.put(
        `${apiBase}/integrations/smtp/configuration`,
        {
          headers: organizer.headers,
          data: smtpPayload(smtpConfiguration, true),
        },
      )
      expect(restored.ok(), await restored.text()).toBeTruthy()
    }
  }
})
