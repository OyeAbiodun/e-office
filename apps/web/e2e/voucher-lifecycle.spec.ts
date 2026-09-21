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

test.use({ actionTimeout: 12_000, navigationTimeout: 20_000 })

function required(name: string) {
  const value = process.env[name]
  if (!value) throw new Error(`${name} must be set for voucher acceptance`)
  return value
}

function unwrap<T>(payload: { data: T }): T {
  return payload.data
}

async function ok(response: APIResponse) {
  expect(response.ok(), `${response.status()} ${await response.text()}`).toBe(
    true,
  )
  return response
}

async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string,
) {
  const response = await ok(
    await request.post(`${apiBase}/auth/login`, { data: { email, password } }),
  )
  const data = unwrap<{ access_token: string; user: User }>(
    await response.json(),
  )
  return {
    headers: { Authorization: `Bearer ${data.access_token}` } as Headers,
    user: data.user,
  }
}

async function login(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByLabel(/work email|email/i).fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL('/', { timeout: 20_000 })
}

async function rolePage(browser: Browser, email: string, password: string) {
  const context = await browser.newContext({ baseURL: webBase })
  const page = await context.newPage()
  await login(page, email, password)
  return { context, page }
}

async function confirm(page: Page, label: RegExp) {
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: label }).click()
}

test('role-separated voucher lifecycle enforces finance, audit, attachment, and tenant controls', async ({
  browser,
  request,
}) => {
  test.setTimeout(420_000)
  await apiLogin(
    request,
    required('PLAYWRIGHT_ORGANIZER_EMAIL'),
    required('PLAYWRIGHT_ORGANIZER_PASSWORD'),
  )

  const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`
  const adminPassword = `VoucherAdmin${suffix}!Aa`
  const temporaryPassword = `VoucherTemp${suffix}!Aa`
  const finalPassword = `VoucherFinal${suffix}!Aa`
  const registration = await ok(
    await request.post(`${apiBase}/auth/register`, {
      data: {
        organization_name: `Voucher Acceptance ${suffix}`,
        organization_slug: `voucher-acceptance-${suffix}`,
        workspace_name: 'Voucher Acceptance',
        email: `admin.${suffix}@voucher-acceptance.example`,
        username: `voucher.admin.${suffix}`,
        first_name: 'Voucher',
        last_name: 'Administrator',
        password: adminPassword,
      },
    }),
  )
  const adminToken = unwrap<{ access_token: string }>(await registration.json())
  const adminHeaders: Headers = {
    Authorization: `Bearer ${adminToken.access_token}`,
  }
  const [workspaceResponse, rolesResponse] = await Promise.all([
    request.get(`${apiBase}/workspaces`, { headers: adminHeaders }),
    request.get(`${apiBase}/roles`, { headers: adminHeaders }),
  ])
  await ok(workspaceResponse)
  await ok(rolesResponse)
  const workspace = unwrap<Entity[]>(await workspaceResponse.json())[0]
  const roles = unwrap<Array<Entity & { name: string }>>(
    await rolesResponse.json(),
  )
  const roleId = (name: string) => {
    const role = roles.find((candidate) => candidate.name === name)
    expect(role, `Missing role ${name}`).toBeTruthy()
    return role!.id
  }
  const createUser = async (
    label: string,
    role: string,
    managerId?: string,
  ) => {
    const response = await ok(
      await request.post(`${apiBase}/users`, {
        headers: adminHeaders,
        data: {
          first_name: 'Voucher',
          last_name: label,
          email: `${label.toLowerCase()}.${suffix}@voucher-acceptance.example`,
          job_title: label,
          department: 'Finance Operations',
          manager_id: managerId ?? null,
          role_ids: [roleId(role)],
          workspace_id: workspace.id,
          temporary_password: temporaryPassword,
          send_welcome_email: false,
        },
      }),
    )
    const user = unwrap<User>(await response.json())
    const temporary = await apiLogin(request, user.email, temporaryPassword)
    await ok(
      await request.post(`${apiBase}/auth/change-password`, {
        headers: temporary.headers,
        data: {
          current_password: temporaryPassword,
          new_password: finalPassword,
          confirm_new_password: finalPassword,
        },
      }),
    )
    return user
  }
  const manager = await createUser('Manager', 'Team Manager')
  const staff = await createUser('Staff', 'Employee', manager.id)
  const accountant = await createUser('Accountant', 'Accountant')
  const auditor = await createUser('Auditor', 'Auditor')
  const staffSession = await apiLogin(request, staff.email, finalPassword)
  const managerSession = await apiLogin(request, manager.email, finalPassword)
  const accountantSession = await apiLogin(
    request,
    accountant.email,
    finalPassword,
  )
  await apiLogin(request, auditor.email, finalPassword)

  const accountResponse = await ok(
    await request.post(`${apiBase}/finance/accounts`, {
      headers: adminHeaders,
      data: {
        account_name: `Acceptance cash ${suffix}`,
        account_code: `ACC-${suffix.slice(-8)}`,
        account_type: 'cash',
        opening_balance: '1000.00',
      },
    }),
  )
  const account = unwrap<Entity>(await accountResponse.json())

  const staffBrowser = await rolePage(browser, staff.email, finalPassword)
  await staffBrowser.page.goto('/vouchers/new')
  await staffBrowser.page
    .getByLabel('Purpose')
    .fill(`Lifecycle voucher ${suffix}`)
  await staffBrowser.page
    .getByLabel('Description / justification')
    .fill('Role-separated acceptance evidence')
  await staffBrowser.page
    .getByLabel('Description 1')
    .fill('Controlled supplies')
  await staffBrowser.page.getByLabel('Quantity 1').fill('2')
  await staffBrowser.page.getByLabel('Unit price 1').fill('50')
  await staffBrowser.page.getByLabel('Tax amount 1').fill('0')
  await staffBrowser.page.getByRole('button', { name: /save/i }).click()
  await expect(staffBrowser.page).toHaveURL(/\/vouchers\/[0-9a-f-]+$/)
  const voucherId = staffBrowser.page.url().split('/').at(-1)!
  await staffBrowser.page
    .getByLabel('Upload receipt or document (up to 25 MB)')
    .setInputFiles({
      name: 'voucher-evidence.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('voucher acceptance evidence'),
    })
  await expect(
    staffBrowser.page.getByText('voucher-evidence.txt'),
  ).toBeVisible()
  await staffBrowser.page.getByRole('button', { name: 'Submit' }).click()
  await confirm(staffBrowser.page, /^Submit$/)
  await expect(
    staffBrowser.page.getByText('Submitted', { exact: true }).first(),
  ).toBeVisible()

  const unauthorizedApproval = await request.post(
    `${apiBase}/vouchers/${voucherId}/approve`,
    {
      headers: staffSession.headers,
      data: { approved_amount: '100.00' },
    },
  )
  expect(unauthorizedApproval.status()).toBe(403)

  const managerBrowser = await rolePage(browser, manager.email, finalPassword)
  await managerBrowser.page.goto(`/vouchers/${voucherId}`)
  await expect(
    managerBrowser.page.getByRole('button', { name: 'Approve' }),
  ).toBeVisible()
  await managerBrowser.page.getByRole('button', { name: 'Approve' }).click()
  await managerBrowser.page.getByLabel('Approved amount').fill('100')
  await managerBrowser.page
    .getByLabel('Review comment (optional)')
    .fill('Within delegated budget')
  await managerBrowser.page
    .getByRole('button', { name: 'Review and approve' })
    .click()
  await confirm(managerBrowser.page, /^Approve$/)
  await expect(
    managerBrowser.page.getByText('Approved', { exact: true }).first(),
  ).toBeVisible()

  const managerDisbursement = await request.post(
    `${apiBase}/vouchers/${voucherId}/disburse`,
    {
      headers: managerSession.headers,
      data: {
        account_id: account.id,
        amount: '100.00',
        payment_method: 'bank_transfer',
        payment_reference: `DENIED-${suffix}`,
        payment_date: new Date().toISOString().slice(0, 10),
        idempotency_key: `denied-${suffix}`,
      },
    },
  )
  expect(managerDisbursement.status()).toBe(403)

  await expect
    .poll(async () => {
      const response = await request.get(`${apiBase}/vouchers/${voucherId}`, {
        headers: accountantSession.headers,
      })
      if (!response.ok()) return []
      return unwrap<{ allowed_actions: string[] }>(await response.json())
        .allowed_actions
    })
    .toContain('disburse')

  const accountantBrowser = await rolePage(
    browser,
    accountant.email,
    finalPassword,
  )
  await accountantBrowser.page.goto(`/vouchers/${voucherId}`)
  await accountantBrowser.page.getByRole('button', { name: 'Disburse' }).click()
  await accountantBrowser.page
    .getByLabel('Pay from account')
    .selectOption(account.id)
  await accountantBrowser.page.getByLabel('Current payment amount').fill('100')
  await accountantBrowser.page
    .getByLabel('Payment reference')
    .fill(`PAY-${suffix}`)
  await accountantBrowser.page
    .getByRole('button', { name: 'Review and disburse' })
    .click()
  await confirm(accountantBrowser.page, /^Disburse$/)
  await expect(
    accountantBrowser.page.getByText('Completed', { exact: true }).first(),
  ).toBeVisible()

  const detailResponse = await ok(
    await request.get(`${apiBase}/vouchers/${voucherId}`, {
      headers: accountantSession.headers,
    }),
  )
  const detail = unwrap<{
    voucher: {
      status: string
      disbursed_amount: string
      outstanding_amount: string
    }
    attachments: Array<{ id: string; url: string }>
    disbursements: Entity[]
    transactions: Array<Entity & { amount: string; direction: string }>
    history: Array<{ event_type: string }>
  }>(await detailResponse.json())
  expect(detail.voucher).toMatchObject({
    status: 'completed',
    disbursed_amount: '100.00',
    outstanding_amount: '0.00',
  })
  expect(detail.disbursements).toHaveLength(1)
  expect(detail.transactions).toHaveLength(1)
  expect(detail.transactions[0]).toMatchObject({
    amount: '100.00',
    direction: 'debit',
  })
  expect(detail.history.map((entry) => entry.event_type)).toEqual(
    expect.arrayContaining(['created', 'submitted', 'approved', 'disbursed']),
  )

  const replay = await request.post(
    `${apiBase}/vouchers/${voucherId}/disburse`,
    {
      headers: accountantSession.headers,
      data: {
        account_id: account.id,
        amount: '100.00',
        payment_method: 'bank_transfer',
        payment_reference: `PAY-${suffix}`,
        payment_date: new Date().toISOString().slice(0, 10),
        idempotency_key: `browser-replay-${voucherId}`,
      },
    },
  )
  expect([409, 422]).toContain(replay.status())

  const notifications = await ok(
    await request.get(`${apiBase}/notifications`, {
      headers: staffSession.headers,
    }),
  )
  expect(JSON.stringify(await notifications.json())).toContain(voucherId)

  const auditorBrowser = await rolePage(browser, auditor.email, finalPassword)
  await auditorBrowser.page.goto(`/vouchers/${voucherId}`)
  await expect(
    auditorBrowser.page.getByRole('heading', { name: 'Lifecycle' }),
  ).toBeVisible()
  await expect(
    auditorBrowser.page.getByText('Disbursed', { exact: true }).last(),
  ).toBeVisible()
  await expect(
    auditorBrowser.page.getByRole('heading', {
      name: 'Ledger & reconciliation',
    }),
  ).toBeVisible()

  const attachmentUrl = detail.attachments[0].url
  expect(
    (
      await request.get(
        `${apiBase.replace(/\/api\/v1$/, '')}${attachmentUrl}`,
        { headers: staffSession.headers },
      )
    ).status(),
  ).toBe(200)
  expect(
    (
      await request.get(
        `${apiBase.replace(/\/api\/v1$/, '')}${attachmentUrl}`,
        { headers: accountantSession.headers },
      )
    ).status(),
  ).toBe(200)

  const foreignPassword = `Foreign${suffix}!Aa`
  const foreign = await ok(
    await request.post(`${apiBase}/auth/register`, {
      data: {
        organization_name: `Foreign Voucher ${suffix}`,
        organization_slug: `foreign-voucher-${suffix}`,
        workspace_name: 'Foreign',
        email: `admin.${suffix}@foreign-voucher.example`,
        username: `foreign.voucher.${suffix}`,
        first_name: 'Foreign',
        last_name: 'Administrator',
        password: foreignPassword,
      },
    }),
  )
  const foreignToken = unwrap<{ access_token: string }>(await foreign.json())
  const foreignHeaders = {
    Authorization: `Bearer ${foreignToken.access_token}`,
  }
  expect(
    (
      await request.get(`${apiBase}/vouchers/${voucherId}`, {
        headers: foreignHeaders,
      })
    ).status(),
  ).toBe(404)
  expect(
    (
      await request.get(
        `${apiBase.replace(/\/api\/v1$/, '')}${attachmentUrl}`,
        { headers: foreignHeaders },
      )
    ).status(),
  ).toBe(404)

  await Promise.all([
    staffBrowser.context.close(),
    managerBrowser.context.close(),
    accountantBrowser.context.close(),
    auditorBrowser.context.close(),
  ])
})
