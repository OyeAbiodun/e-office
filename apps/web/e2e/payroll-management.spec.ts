import {
  expect,
  type APIRequestContext,
  type APIResponse,
  type Browser,
  type Page,
  test,
} from '@playwright/test'

const apiBase = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8001/api/v1'
const webBase = process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5174'
type Headers = { Authorization: string }
type Entity = { id: string }
type User = Entity & { email: string }

test.use({ actionTimeout: 10_000, navigationTimeout: 15_000 })

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value)
    throw new Error(`${name} must be set for payroll browser acceptance`)
  return value
}

function unwrap<T>(payload: { data: T }): T {
  return payload.data
}

async function assertOk(response: APIResponse) {
  expect(response.ok(), `API request failed with ${response.status()}`).toBe(
    true,
  )
  return response
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
  await assertOk(response)
  const payload = unwrap<{ access_token: string; user: { id: string } }>(
    await response.json(),
  )
  return {
    headers: { Authorization: `Bearer ${payload.access_token}` } as Headers,
    userId: payload.user.id,
  }
}

async function login(page: Page, email: string, passwordValue: string) {
  console.info('payroll-acceptance: opening login')
  await page.goto('/login')
  console.info('payroll-acceptance: login page ready')
  await page.getByLabel(/work email|email/i).fill(email)
  const password = page.getByLabel('Password')
  await password.fill(passwordValue)
  await page.getByRole('button', { name: 'Sign in' }).click()
  console.info('payroll-acceptance: sign-in submitted')
  await password.fill('').catch(() => undefined)
  await expect(page).toHaveURL('/', { timeout: 15_000 })
  console.info('payroll-acceptance: authenticated page ready')
}

async function rolePage(
  browser: Browser,
  email: string,
  password: string,
  viewport?: { width: number; height: number },
) {
  console.info('payroll-acceptance: opening role context')
  const context = await browser.newContext({ baseURL: webBase, viewport })
  const page = await context.newPage()
  page.on('response', (response) => {
    if (response.status() >= 400) {
      const url = new URL(response.url())
      console.info(
        `payroll-acceptance: HTTP ${response.status()} ${url.pathname}`,
      )
    }
  })
  await login(page, email, password)
  return { context, page }
}

async function changePassword(
  request: APIRequestContext,
  user: User,
  temporaryPassword: string,
  finalPassword: string,
) {
  const session = await apiLogin(request, user.email, temporaryPassword)
  await assertOk(
    await request.post(`${apiBase}/auth/change-password`, {
      headers: session.headers,
      data: {
        current_password: temporaryPassword,
        new_password: finalPassword,
        confirm_new_password: finalPassword,
      },
    }),
  )
}

async function confirm(page: Page, label: RegExp) {
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: label }).click()
}

test('role-separated payroll lifecycle, posting, payslip security, and mobile access', async ({
  browser,
  request,
}) => {
  test.setTimeout(360_000)
  await apiLogin(
    request,
    requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL'),
    requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD'),
  )

  const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`
  const adminPassword = `PayrollAdmin${suffix}!Aa`
  const temporaryPassword = `PayrollTemp${suffix}!Aa`
  const finalPassword = `PayrollFinal${suffix}!Aa`
  const register = await assertOk(
    await request.post(`${apiBase}/auth/register`, {
      data: {
        organization_name: `Payroll Acceptance ${suffix}`,
        organization_slug: `payroll-acceptance-${suffix}`,
        workspace_name: 'Payroll Acceptance',
        email: `admin.${suffix}@payroll-acceptance.example`,
        username: `payroll.admin.${suffix}`,
        first_name: 'Payroll',
        last_name: 'Administrator',
        password: adminPassword,
      },
    }),
  )
  const registered = unwrap<{ access_token: string }>(await register.json())
  const adminHeaders: Headers = {
    Authorization: `Bearer ${registered.access_token}`,
  }
  const [workspaceResponse, rolesResponse, permissionsResponse] =
    await Promise.all([
      request.get(`${apiBase}/workspaces`, { headers: adminHeaders }),
      request.get(`${apiBase}/roles`, { headers: adminHeaders }),
      request.get(`${apiBase}/permissions`, { headers: adminHeaders }),
    ])
  await assertOk(workspaceResponse)
  await assertOk(rolesResponse)
  await assertOk(permissionsResponse)
  const workspace = unwrap<Entity[]>(await workspaceResponse.json())[0]
  const roles = unwrap<Array<Entity & { name: string }>>(
    await rolesResponse.json(),
  )
  const permissions = unwrap<Array<Entity & { name: string }>>(
    await permissionsResponse.json(),
  )
  const roleId = (name: string) => {
    const role = roles.find((candidate) => candidate.name === name)
    expect(role, `Missing system role ${name}`).toBeTruthy()
    return role!.id
  }
  const makePayrollRole = async (label: string, permissionNames: string[]) => {
    const permissionIds = permissions
      .filter((permission) => permissionNames.includes(permission.name))
      .map((permission) => permission.id)
    expect(permissionIds).toHaveLength(permissionNames.length)
    const response = await assertOk(
      await request.post(`${apiBase}/roles`, {
        headers: adminHeaders,
        data: {
          name: `${label} ${suffix}`,
          description: 'Controlled Payroll browser acceptance role',
          permission_ids: permissionIds,
        },
      }),
    )
    return unwrap<Entity>(await response.json()).id
  }
  const reviewerRole = await makePayrollRole('Payroll Reviewer', [
    'dashboard.view',
    'payroll.periods.view',
    'payroll.review',
    'payroll.view_employee',
    'payroll.reports.view',
  ])
  const approverRole = await makePayrollRole('Payroll Final Approver', [
    'dashboard.view',
    'payroll.periods.view',
    'payroll.approve',
    'payroll.view_employee',
    'payroll.reports.view',
  ])
  const createUser = async (
    label: string,
    role: string,
    employeeNumber?: string,
  ) => {
    const response = await assertOk(
      await request.post(`${apiBase}/users`, {
        headers: adminHeaders,
        data: {
          first_name: 'Payroll',
          last_name: label,
          email: `${label.toLowerCase()}.${suffix}@payroll-acceptance.example`,
          job_title: label,
          department: 'Finance',
          employee_number: employeeNumber,
          employment_start_date: '2026-01-01',
          role_ids: [role],
          workspace_id: workspace.id,
          temporary_password: temporaryPassword,
          send_welcome_email: false,
        },
      }),
    )
    const user = unwrap<User>(await response.json())
    await changePassword(request, user, temporaryPassword, finalPassword)
    return user
  }

  const officer = await createUser('Officer', roleId('Payroll Officer'))
  const reviewer = await createUser('Reviewer', reviewerRole)
  const approver = await createUser('Approver', approverRole)
  const accountant = await createUser('Accountant', roleId('Accountant'))
  const employee = await createUser(
    'Employee',
    roleId('Employee'),
    `EMP-${suffix}`,
  )
  const stranger = await createUser('Stranger', roleId('Employee'))
  const manager = await createUser('Manager', roleId('Team Manager'))
  const sessions = {
    officer: await apiLogin(request, officer.email, finalPassword),
    reviewer: await apiLogin(request, reviewer.email, finalPassword),
    accountant: await apiLogin(request, accountant.email, finalPassword),
    employee: await apiLogin(request, employee.email, finalPassword),
    stranger: await apiLogin(request, stranger.email, finalPassword),
    manager: await apiLogin(request, manager.email, finalPassword),
  }
  console.info('payroll-acceptance: identities ready')

  const componentResponse = await assertOk(
    await request.post(`${apiBase}/payroll/components`, {
      headers: adminHeaders,
      data: {
        code: `HOUSING-${suffix}`,
        name: 'Housing Allowance',
        description: 'Recurring taxable housing allowance',
        component_kind: 'earning',
        calculation_type: 'fixed',
        taxable: true,
        pensionable: true,
        recurring: true,
        is_active: true,
        effective_start: '2026-01-01',
      },
    }),
  )
  const component = unwrap<Entity>(await componentResponse.json())
  const statutory = [
    {
      configuration_type: 'paye',
      name: 'PAYE 2026',
      rules: {
        annual_relief_fixed: '0',
        annual_relief_rate: '0',
        bands: [{ limit: null, rate: '10' }],
      },
    },
    {
      configuration_type: 'pension',
      name: 'Pension 2026',
      rules: {
        basis: 'pensionable',
        employee_rate: '8',
        employer_rate: '10',
      },
    },
    {
      configuration_type: 'nhf',
      name: 'NHF 2026',
      rules: { basis: 'basic', employee_rate: '2.5' },
    },
    {
      configuration_type: 'payroll_policy',
      name: 'Payroll policy 2026',
      rules: { proration_method: 'calendar_days' },
    },
  ]
  for (const configuration of statutory) {
    await assertOk(
      await request.post(`${apiBase}/payroll/statutory`, {
        headers: adminHeaders,
        data: {
          ...configuration,
          effective_start: '2026-01-01',
          change_reason: 'Controlled browser acceptance setup',
        },
      }),
    )
  }
  const structureBody = {
    employee_id: employee.id,
    basic_salary: '100000',
    effective_start: '2026-01-01',
    change_reason: 'Initial controlled employment package',
    items: [{ component_id: component.id, amount: '20000' }],
  }
  const previewResponse = await assertOk(
    await request.post(`${apiBase}/payroll/salary-structures/preview`, {
      headers: adminHeaders,
      data: structureBody,
    }),
  )
  expect(
    unwrap<Record<string, string>>(await previewResponse.json()),
  ).toMatchObject({
    gross_pay: '120000.00',
    paye: '12000.00',
    pension_employee: '9600.00',
    nhf: '2500.00',
    total_deductions: '24100.00',
    net_pay: '95900.00',
    employer_cost: '132000.00',
  })
  await assertOk(
    await request.post(`${apiBase}/payroll/salary-structures`, {
      headers: adminHeaders,
      data: structureBody,
    }),
  )
  const overlap = await request.post(`${apiBase}/payroll/salary-structures`, {
    headers: adminHeaders,
    data: {
      ...structureBody,
      basic_salary: '110000',
      effective_start: '2026-06-01',
      change_reason: 'Unsafe overlapping structure',
    },
  })
  expect(overlap.status()).toBe(409)
  const accountResponse = await assertOk(
    await request.post(`${apiBase}/finance/accounts`, {
      headers: adminHeaders,
      data: {
        account_name: 'Controlled Payroll Account',
        account_code: `PAY-${suffix}`,
        account_type: 'bank',
        bank_name: 'Controlled Bank',
        account_number: '0000000000',
        opening_balance: '1000000',
      },
    }),
  )
  const account = unwrap<Entity>(await accountResponse.json())
  await assertOk(
    await request.post(`${apiBase}/payroll/periods`, {
      headers: sessions.officer.headers,
      data: {
        name: `September ${suffix}`,
        start_date: '2026-09-01',
        end_date: '2026-09-30',
        payment_date: '2026-09-30',
      },
    }),
  )
  console.info('payroll-acceptance: payroll foundation ready')

  const officerBrowser = await rolePage(browser, officer.email, finalPassword)
  await officerBrowser.page.goto('/payroll')
  await officerBrowser.page.getByRole('tab', { name: 'Payroll runs' }).click()
  const periodRow = officerBrowser.page
    .getByRole('row')
    .filter({ hasText: `September ${suffix}` })
  await periodRow.getByRole('button', { name: 'Prepare payroll' }).click()
  await expect(
    officerBrowser.page.getByRole('button', {
      name: 'View calculation for Payroll Employee',
    }),
  ).toBeVisible()
  for (const value of [
    'NGN 120,000.00',
    'NGN 12,000.00',
    'NGN 9,600.00',
    'NGN 2,500.00',
    'NGN 24,100.00',
    'NGN 95,900.00',
    'NGN 132,000.00',
  ]) {
    await expect(
      officerBrowser.page.getByText(value, { exact: true }).first(),
    ).toBeVisible()
  }
  await officerBrowser.page
    .getByRole('button', { name: 'View calculation for Payroll Employee' })
    .click()
  await expect(
    officerBrowser.page.getByLabel('Employee payroll calculation'),
  ).toContainText('NGN 95,900.00')
  await officerBrowser.page
    .getByLabel('Employee payroll calculation')
    .getByRole('button', { name: 'Close' })
    .click()
  await officerBrowser.page
    .getByRole('button', { name: 'Submit for approval' })
    .click()
  await confirm(officerBrowser.page, /^submit$/i)
  await expect(
    officerBrowser.page.getByText('Under review').first(),
  ).toBeVisible()
  console.info('payroll-acceptance: preparer submitted')

  const runsResponse = await assertOk(
    await request.get(`${apiBase}/payroll/runs`, {
      headers: sessions.officer.headers,
    }),
  )
  const run = unwrap<Array<Entity & { status: string }>>(
    await runsResponse.json(),
  )[0]
  const detailResponse = await assertOk(
    await request.get(`${apiBase}/payroll/runs/${run.id}`, {
      headers: sessions.officer.headers,
    }),
  )
  const detail = unwrap<{
    results: { items: Array<Entity & { employee_id: string }> }
  }>(await detailResponse.json())
  let result = detail.results.items.find(
    (item) => item.employee_id === employee.id,
  )!

  const reviewerBrowser = await rolePage(browser, reviewer.email, finalPassword)
  await reviewerBrowser.page.goto('/payroll')
  await reviewerBrowser.page.getByRole('tab', { name: 'Payroll runs' }).click()
  await reviewerBrowser.page
    .getByRole('row')
    .filter({ hasText: `September ${suffix}` })
    .getByRole('button', { name: 'Open run' })
    .click()
  await expect(
    reviewerBrowser.page.getByRole('button', { name: 'Record payment' }),
  ).toHaveCount(0)
  await expect(
    reviewerBrowser.page.getByRole('button', { name: 'Approve' }),
  ).toHaveCount(0)
  await reviewerBrowser.page.getByRole('button', { name: 'Return' }).click()
  await reviewerBrowser.page
    .getByLabel('Return reason')
    .fill('Confirm the controlled calculation evidence')
  await reviewerBrowser.page
    .getByRole('button', { name: 'Return for correction' })
    .click()
  await confirm(reviewerBrowser.page, /^return$/i)
  await expect(reviewerBrowser.page.getByText('Returned').first()).toBeVisible()
  await reviewerBrowser.context.close()
  console.info('payroll-acceptance: reviewer returned')

  await officerBrowser.page.reload()
  await officerBrowser.page.getByRole('tab', { name: 'Payroll runs' }).click()
  const returnedRow = officerBrowser.page
    .getByRole('row')
    .filter({ hasText: `September ${suffix}` })
  await expect(returnedRow.getByText('Returned')).toBeVisible()
  await returnedRow.getByRole('button', { name: 'Open run' }).click()
  await officerBrowser.page.getByRole('button', { name: 'Recalculate' }).click()
  await expect(
    officerBrowser.page.getByRole('button', { name: 'Submit for approval' }),
  ).toBeVisible()
  await officerBrowser.page
    .getByRole('button', { name: 'Submit for approval' })
    .click()
  await confirm(officerBrowser.page, /^submit$/i)
  await expect(
    officerBrowser.page.getByText('Under review').first(),
  ).toBeVisible()
  await officerBrowser.context.close()
  console.info('payroll-acceptance: preparer resubmitted')

  const approverBrowser = await rolePage(browser, approver.email, finalPassword)
  await approverBrowser.page.goto('/payroll')
  await approverBrowser.page.getByRole('tab', { name: 'Payroll runs' }).click()
  await approverBrowser.page
    .getByRole('row')
    .filter({ hasText: `September ${suffix}` })
    .getByRole('button', { name: 'Open run' })
    .click()
  await expect(
    approverBrowser.page.getByRole('button', { name: 'Return' }),
  ).toHaveCount(0)
  await approverBrowser.page.getByRole('button', { name: 'Approve' }).click()
  await confirm(approverBrowser.page, /^approve$/i)
  await expect(approverBrowser.page.getByText('Approved').first()).toBeVisible()
  await expect(
    approverBrowser.page.getByRole('button', { name: 'Recalculate' }),
  ).toHaveCount(0)
  await approverBrowser.context.close()
  console.info('payroll-acceptance: approver approved')

  expect(
    (
      await request.post(`${apiBase}/payroll/runs/${run.id}/approve`, {
        headers: sessions.officer.headers,
      })
    ).status(),
  ).toBe(403)
  expect(
    (
      await request.post(`${apiBase}/payroll/runs/${run.id}/pay`, {
        headers: sessions.reviewer.headers,
        data: {
          account_id: account.id,
          payment_date: '2026-09-30',
          payment_reference: `DENIED-${suffix}`,
          idempotency_key: `denied-${suffix}`,
        },
      })
    ).status(),
  ).toBe(403)
  expect(
    (
      await request.post(`${apiBase}/payroll/salary-structures`, {
        headers: sessions.accountant.headers,
        data: structureBody,
      })
    ).status(),
  ).toBe(403)

  const accountantBrowser = await rolePage(
    browser,
    accountant.email,
    finalPassword,
  )
  await accountantBrowser.page.goto('/payroll')
  await accountantBrowser.page
    .getByRole('tab', { name: 'Payroll runs' })
    .click()
  await accountantBrowser.page
    .getByRole('row')
    .filter({ hasText: `September ${suffix}` })
    .getByRole('button', { name: 'Open run' })
    .click()
  await accountantBrowser.page
    .getByRole('button', { name: 'Record payment' })
    .click()
  await accountantBrowser.page
    .getByLabel('Funding account')
    .selectOption(account.id)
  await accountantBrowser.page.getByLabel('Payment date').fill('2026-09-30')
  await accountantBrowser.page
    .getByLabel('Payment reference')
    .fill(`PAY-${suffix}`)
  await accountantBrowser.page
    .getByRole('button', { name: 'Confirm payment' })
    .click()
  await confirm(accountantBrowser.page, /^pay$/i)
  await expect(accountantBrowser.page.getByText('Paid').first()).toBeVisible()
  await accountantBrowser.context.close()
  console.info('payroll-acceptance: accountant paid')

  const paidDetailResponse = await assertOk(
    await request.get(`${apiBase}/payroll/runs/${run.id}`, {
      headers: sessions.accountant.headers,
    }),
  )
  const paidDetail = unwrap<{
    results: { items: Array<Entity & { employee_id: string }> }
  }>(await paidDetailResponse.json())
  result = paidDetail.results.items.find(
    (item) => item.employee_id === employee.id,
  )!

  const transactions = async () => {
    const response = await assertOk(
      await request.get(`${apiBase}/finance/transactions`, {
        headers: sessions.accountant.headers,
      }),
    )
    return unwrap<Array<Entity & { transaction_type: string }>>(
      await response.json(),
    ).filter((item) => item.transaction_type === 'payroll')
  }
  expect(await transactions()).toHaveLength(1)
  const replayBody = {
    account_id: account.id,
    payment_date: '2026-09-30',
    payment_reference: `PAY-${suffix}`,
    idempotency_key: `replay-${suffix}`,
  }
  const replayOne = await assertOk(
    await request.post(`${apiBase}/payroll/runs/${run.id}/pay`, {
      headers: sessions.accountant.headers,
      data: replayBody,
    }),
  )
  const replayTwo = await assertOk(
    await request.post(`${apiBase}/payroll/runs/${run.id}/pay`, {
      headers: sessions.accountant.headers,
      data: replayBody,
    }),
  )
  expect(unwrap<Entity>(await replayOne.json()).id).toBe(
    unwrap<Entity>(await replayTwo.json()).id,
  )
  expect(await transactions()).toHaveLength(1)

  const employeeBrowser = await rolePage(browser, employee.email, finalPassword)
  await employeeBrowser.page.goto('/payroll')
  await expect(
    employeeBrowser.page.getByRole('tab', { name: 'Payroll runs' }),
  ).toHaveCount(0)
  await expect(
    employeeBrowser.page.getByRole('tab', { name: 'Salary structures' }),
  ).toHaveCount(0)
  await employeeBrowser.page.getByRole('tab', { name: 'My payslips' }).click()
  await expect(
    employeeBrowser.page.getByText(`September ${suffix}`),
  ).toBeVisible()
  let responseType = ''
  employeeBrowser.page.on('response', (response) => {
    if (response.url().includes(`/payroll/results/${result.id}/payslip`))
      responseType = response.headers()['content-type'] ?? ''
  })
  const downloadEvent = employeeBrowser.page.waitForEvent('download')
  await employeeBrowser.page.getByRole('button', { name: 'Download' }).click()
  const download = await downloadEvent
  expect(download.suggestedFilename()).toBe('payslip.pdf')
  const path = await download.path()
  expect(path).toBeTruthy()
  const { readFile } = await import('node:fs/promises')
  expect((await readFile(path!)).subarray(0, 5).toString()).toBe('%PDF-')
  expect(responseType).toContain('application/pdf')
  await employeeBrowser.context.close()
  console.info('payroll-acceptance: employee payslip verified')

  expect(
    (
      await request.get(`${apiBase}/payroll/results/${result.id}`, {
        headers: sessions.stranger.headers,
      })
    ).status(),
  ).toBe(404)
  expect(
    (
      await request.get(`${apiBase}/payroll/results/${result.id}/payslip`, {
        headers: sessions.stranger.headers,
      })
    ).status(),
  ).toBe(404)
  expect(
    (
      await request.get(`${apiBase}/payroll/salary-structures`, {
        headers: sessions.manager.headers,
      })
    ).status(),
  ).toBe(403)
  const managerBrowser = await rolePage(browser, manager.email, finalPassword)
  await managerBrowser.page.goto('/payroll')
  await expect(managerBrowser.page.getByRole('alert')).toContainText(
    'You do not have permission to access payroll.',
  )
  await managerBrowser.context.close()
  console.info('payroll-acceptance: role denials verified')

  const foreignPassword = `ForeignPayroll${suffix}!Aa`
  const foreignRegister = await assertOk(
    await request.post(`${apiBase}/auth/register`, {
      data: {
        organization_name: `Foreign Payroll ${suffix}`,
        organization_slug: `foreign-payroll-${suffix}`,
        workspace_name: 'Foreign Workspace',
        email: `admin.${suffix}@foreign-payroll.example`,
        username: `foreign.payroll.${suffix}`,
        first_name: 'Foreign',
        last_name: 'Administrator',
        password: foreignPassword,
      },
    }),
  )
  const foreign = unwrap<{ access_token: string }>(await foreignRegister.json())
  const foreignHeaders = { Authorization: `Bearer ${foreign.access_token}` }
  for (const endpoint of [
    `/payroll/runs/${run.id}`,
    `/payroll/results/${result.id}`,
    `/payroll/results/${result.id}/payslip`,
  ]) {
    const response = await request.get(`${apiBase}${endpoint}`, {
      headers: foreignHeaders,
    })
    expect(response.status()).toBe(404)
    expect(await response.text()).not.toContain(employee.email)
  }

  const paidBeforeResponse = await assertOk(
    await request.get(`${apiBase}/payroll/results/${result.id}`, {
      headers: sessions.officer.headers,
    }),
  )
  const paidBefore = unwrap<{ gross_pay: string; net_pay: string }>(
    await paidBeforeResponse.json(),
  )
  await assertOk(
    await request.put(`${apiBase}/payroll/components/${component.id}`, {
      headers: sessions.officer.headers,
      data: {
        code: `HOUSING-${suffix}`,
        name: 'Housing Allowance',
        description: 'Governed after payroll payment',
        component_kind: 'earning',
        calculation_type: 'fixed',
        taxable: true,
        pensionable: true,
        recurring: true,
        is_active: true,
        effective_start: '2026-01-01',
      },
    }),
  )
  const paidAfterResponse = await assertOk(
    await request.get(`${apiBase}/payroll/results/${result.id}`, {
      headers: sessions.officer.headers,
    }),
  )
  expect(
    unwrap<{ gross_pay: string; net_pay: string }>(
      await paidAfterResponse.json(),
    ),
  ).toMatchObject(paidBefore)

  const mobile = await rolePage(browser, employee.email, finalPassword, {
    width: 390,
    height: 844,
  })
  await mobile.page.goto('/payroll')
  await expect(
    mobile.page.getByRole('heading', { name: 'Payroll', exact: true }),
  ).toBeVisible()
  await mobile.page.getByRole('tab', { name: 'My payslips' }).click()
  await expect(mobile.page.getByText(`September ${suffix}`)).toBeVisible()
  await expect(
    mobile.page.getByRole('button', { name: 'Download' }),
  ).toBeVisible()
  expect(
    await mobile.page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    ),
  ).toBe(false)
  await mobile.context.close()
  console.info('payroll-acceptance: mobile and tenant isolation verified')
})
