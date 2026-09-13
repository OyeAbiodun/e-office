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

test('project lifecycle is integrated, role-separated, and responsive', async ({
  browser,
  request,
}) => {
  test.setTimeout(240_000)
  const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`
  const adminPassword = `ProjectAdmin${suffix}!Aa`
  const temporaryPassword = `ProjectTemp${suffix}!Aa`
  const finalPassword = `ProjectFinal${suffix}!Aa`
  const register = await request.post(`${apiBase}/auth/register`, {
    data: {
      organization_name: `Project Acceptance ${suffix}`,
      organization_slug: `project-acceptance-${suffix}`,
      workspace_name: 'Project Acceptance',
      email: `admin.${suffix}@project-acceptance.example`,
      username: `project.admin.${suffix}`,
      first_name: 'Project',
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
  expect(workspaceResponse.ok()).toBeTruthy()
  expect(rolesResponse.ok()).toBeTruthy()
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
        last_name: 'Project acceptance',
        email: `${label.toLowerCase()}.${suffix}@project-acceptance.example`,
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
  const member = await createUser('Member', 'Employee', manager.id)
  const outsider = await createUser('Outsider', 'Employee')
  const managerSession = await loginApi(request, manager.email, finalPassword)
  const memberSession = await loginApi(request, member.email, finalPassword)
  const outsiderSession = await loginApi(request, outsider.email, finalPassword)

  const adminBrowser = await browserSession(
    browser,
    registered.user.email,
    adminPassword,
  )
  await adminBrowser.page.goto('/projects')
  await expect(
    adminBrowser.page.getByRole('heading', { name: 'Projects', exact: true }),
  ).toBeVisible()
  await adminBrowser.page.getByRole('button', { name: /new project/i }).click()
  await adminBrowser.page
    .getByLabel('Project name')
    .fill(`Operations rollout ${suffix}`)
  await adminBrowser.page.getByLabel('Project manager').selectOption(manager.id)
  await adminBrowser.page.getByLabel('Start date').fill('2026-09-15')
  await adminBrowser.page.getByLabel('Target end').fill('2026-11-30')
  await adminBrowser.page
    .getByRole('button', { name: 'Create project' })
    .click()
  await expect(
    adminBrowser.page.getByText(`Operations rollout ${suffix}`),
  ).toBeVisible()
  const projectResponse = await request.get(`${apiBase}/projects`, {
    headers: adminHeaders,
    params: { search: `Operations rollout ${suffix}`, page_size: 10 },
  })
  expect(projectResponse.ok()).toBeTruthy()
  const project = unwrap<{ items: Array<Entity & { project_code: string }> }>(
    await projectResponse.json(),
  ).items[0]

  const addMember = await request.post(
    `${apiBase}/projects/${project.id}/members`,
    {
      headers: managerSession.headers,
      data: { user_id: member.id, role: 'member' },
    },
  )
  expect(addMember.ok(), await addMember.text()).toBeTruthy()
  const milestone = await request.post(
    `${apiBase}/projects/${project.id}/milestones`,
    {
      headers: managerSession.headers,
      data: {
        name: 'Launch readiness',
        owner_id: member.id,
        target_date: '2026-11-15',
      },
    },
  )
  expect(milestone.ok(), await milestone.text()).toBeTruthy()
  const milestoneId = unwrap<Entity>(await milestone.json()).id
  const taskResponse = await request.post(
    `${apiBase}/projects/${project.id}/tasks`,
    {
      headers: managerSession.headers,
      data: {
        title: 'Validate launch controls',
        assignee_id: member.id,
        milestone_id: milestoneId,
        due_date: '2026-11-01',
        priority: 'high',
      },
    },
  )
  expect(taskResponse.ok(), await taskResponse.text()).toBeTruthy()
  const task = unwrap<Entity>(await taskResponse.json())
  expect(
    (
      await request.post(`${apiBase}/tasks/activities`, {
        headers: memberSession.headers,
        data: {
          activity_date: '2026-09-16',
          summary: 'Validated launch access controls.',
          task_id: task.id,
          project_id: project.id,
          duration_minutes: 60,
        },
      })
    ).ok(),
  ).toBeTruthy()
  expect(
    (
      await request.post(`${apiBase}/projects/${project.id}/updates`, {
        headers: managerSession.headers,
        data: {
          reporting_date: '2026-09-16',
          summary: 'The rollout remains on track.',
          accomplishments: 'Access control validation started.',
        },
      })
    ).ok(),
  ).toBeTruthy()

  const managerBrowser = await browserSession(
    browser,
    manager.email,
    finalPassword,
  )
  await managerBrowser.page.goto(`/projects/${project.id}`)
  await expect(
    managerBrowser.page.getByRole('heading', {
      name: `Operations rollout ${suffix}`,
    }),
  ).toBeVisible()
  await expect(
    managerBrowser.page.getByText(project.project_code).first(),
  ).toBeVisible()
  await managerBrowser.page.getByRole('button', { name: 'Tasks' }).click()
  await expect(
    managerBrowser.page.getByText('Validate launch controls'),
  ).toBeVisible()
  await managerBrowser.page.getByRole('button', { name: 'Milestones' }).click()
  await expect(managerBrowser.page.getByText('Launch readiness')).toBeVisible()
  await managerBrowser.page.getByRole('button', { name: 'Updates' }).click()
  await expect(
    managerBrowser.page.getByText('The rollout remains on track.'),
  ).toBeVisible()
  await managerBrowser.page.getByRole('button', { name: 'Risks' }).click()
  await managerBrowser.page
    .getByRole('button', { name: 'Add', exact: true })
    .click()
  let dialog = managerBrowser.page.getByRole('dialog')
  await dialog.getByLabel('Risk title').fill('Vendor cutover capacity')
  await dialog.getByLabel('Severity').selectOption('high')
  await dialog.getByLabel('Probability').selectOption('medium')
  await dialog.getByLabel('Impact').selectOption('high')
  await dialog
    .getByLabel('Mitigation')
    .fill('Reserve a secondary cutover window.')
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(
    managerBrowser.page.getByText('Vendor cutover capacity'),
  ).toBeVisible()

  await managerBrowser.page.getByRole('button', { name: 'Issues' }).click()
  await managerBrowser.page
    .getByRole('button', { name: 'Add', exact: true })
    .click()
  dialog = managerBrowser.page.getByRole('dialog')
  await dialog.getByLabel('Issue title').fill('Legacy access review')
  await dialog.getByLabel('Severity').selectOption('medium')
  await dialog.getByLabel('Due date').fill('2026-10-10')
  await dialog
    .getByLabel('Description')
    .fill('Confirm that legacy identities are removed before launch.')
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(
    managerBrowser.page.getByText('Legacy access review'),
  ).toBeVisible()

  await managerBrowser.page.getByRole('button', { name: 'Files' }).click()
  await managerBrowser.page.locator('input[type="file"]').setInputFiles({
    name: 'launch-controls.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Project acceptance evidence'),
  })
  await expect(
    managerBrowser.page.getByText('launch-controls.txt'),
  ).toBeVisible()
  const download = managerBrowser.page.waitForEvent('download')
  await managerBrowser.page.getByRole('button', { name: 'Download' }).click()
  expect((await download).suggestedFilename()).toBe('launch-controls.txt')

  await managerBrowser.page.getByRole('button', { name: 'Reports' }).click()
  await managerBrowser.page
    .getByRole('button', { name: 'Add', exact: true })
    .click()
  dialog = managerBrowser.page.getByRole('dialog')
  await dialog.getByLabel('Start date').fill('2026-09-01')
  await dialog.getByLabel('End date').fill('2026-12-01')
  await dialog.getByRole('button', { name: 'Generate report' }).click()
  await expect(
    managerBrowser.page.getByRole('heading', {
      name: 'Executive summary',
    }),
  ).toBeVisible()
  await expect(
    managerBrowser.page.getByText('Vendor cutover capacity'),
  ).toBeVisible()
  await expect(
    managerBrowser.page.getByText('Legacy access review'),
  ).toBeVisible()

  const memberBrowser = await browserSession(
    browser,
    member.email,
    finalPassword,
  )
  await memberBrowser.page.goto(`/projects/${project.id}`)
  await expect(
    memberBrowser.page.getByRole('heading', {
      name: `Operations rollout ${suffix}`,
    }),
  ).toBeVisible()
  await memberBrowser.page.goto('/tasks')
  await memberBrowser.page
    .getByRole('button', { name: 'Assigned to me' })
    .click()
  await expect(
    memberBrowser.page.getByText('Validate launch controls'),
  ).toBeVisible()
  await memberBrowser.page
    .getByLabel('Update Validate launch controls status')
    .selectOption('completed')
  await expect
    .poll(async () => {
      const response = await request.get(`${apiBase}/projects/${project.id}`, {
        headers: managerSession.headers,
      })
      return unwrap<{ project: { progress: number } }>(await response.json())
        .project.progress
    })
    .toBe(100)
  await managerBrowser.page.goto(`/projects/${project.id}`)
  await expect(managerBrowser.page.getByText('100%')).toBeVisible()
  expect(
    (
      await request.get(`${apiBase}/projects/${project.id}`, {
        headers: outsiderSession.headers,
      })
    ).status(),
  ).toBe(404)
  await memberBrowser.context.close()

  const mobile = await browserSession(browser, manager.email, finalPassword, {
    width: 390,
    height: 844,
  })
  await mobile.page.goto(`/projects/${project.id}`)
  await expect(
    mobile.page.getByRole('heading', { name: `Operations rollout ${suffix}` }),
  ).toBeVisible()
  await mobile.page.getByRole('button', { name: 'Team' }).click()
  await expect(mobile.page.getByText('Member Project acceptance')).toBeVisible()
  const overflow = await mobile.page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth + 1,
  )
  expect(overflow).toBeFalsy()

  await Promise.all([
    adminBrowser.context.close(),
    managerBrowser.context.close(),
    mobile.context.close(),
  ])
})
