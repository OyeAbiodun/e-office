import {
  expect,
  type APIRequestContext,
  type Page,
  test,
} from '@playwright/test'

const apiBase = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8001/api/v1'
const webBase = process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5174'

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value) {
    throw new Error(`${name} must be set for meeting lifecycle acceptance`)
  }
  return value
}

const organizerEmail = requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL')
const organizerPassword = requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD')

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

async function browserLogin(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Work email').fill(email)
  const passwordField = page.getByLabel('Password')
  await passwordField.fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await passwordField.fill('').catch(() => undefined)
  await expect(page).toHaveURL('/', { timeout: 15_000 })
}

async function waitForMeetingNotification(
  request: APIRequestContext,
  headers: Record<string, string>,
  meetingId: string,
  notificationType: string,
) {
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `${apiBase}/notifications?include_archived=true&page_size=100`,
          { headers },
        )
        expect(response.ok(), await response.text()).toBeTruthy()
        const payload = (await response.json()) as {
          data: {
            unread: number
            notifications: Array<{
              id: string
              meeting_id: string
              notification_type: string
            }>
          }
        }
        return {
          notification: payload.data.notifications.find(
            (item) =>
              item.meeting_id === meetingId &&
              item.notification_type === notificationType,
          ),
          unread: payload.data.unread,
        }
      },
      { timeout: 75_000, intervals: [1_000, 2_000, 3_000] },
    )
    .toMatchObject({
      notification: {
        meeting_id: meetingId,
        notification_type: notificationType,
      },
    })

  const response = await request.get(
    `${apiBase}/notifications?include_archived=true&page_size=100`,
    { headers },
  )
  const payload = (await response.json()) as {
    data: {
      unread: number
      notifications: Array<{
        id: string
        meeting_id: string
        notification_type: string
      }>
    }
  }
  return {
    notification: payload.data.notifications.find(
      (item) =>
        item.meeting_id === meetingId &&
        item.notification_type === notificationType,
    )!,
    unread: payload.data.unread,
  }
}

test('organizer and participant complete the meeting lifecycle', async ({
  browser,
  page,
  request,
}) => {
  test.setTimeout(240_000)
  const organizer = await apiLogin(request, organizerEmail, organizerPassword)
  const suffix = Date.now()
  const participantEmail = `meeting.e2e.${suffix}@example.com`
  const temporaryPassword = `MeetingE2ETemp${suffix}!`
  const participantPassword = `MeetingE2EFinal${suffix}!`
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
  const employeeRole = roles.data.find((role) => role.name === 'Employee')
  expect(employeeRole).toBeTruthy()
  const createdUser = await request.post(`${apiBase}/users`, {
    headers: organizer.headers,
    data: {
      first_name: 'Lifecycle',
      last_name: 'Participant',
      email: participantEmail,
      workspace_id: workspaces.data[0].id,
      role_ids: [employeeRole?.id],
      temporary_password: temporaryPassword,
      send_welcome_email: false,
    },
  })
  expect(createdUser.ok(), await createdUser.text()).toBeTruthy()

  await browserLogin(page, organizerEmail, organizerPassword)
  await page.goto('/meetings/new')
  const title = `Release acceptance ${suffix}`
  await page.getByLabel('Title').fill(title)
  await page
    .getByLabel('Description')
    .fill('Validate invitation, RSVP, calendar, and updates.')
  await page.getByRole('button', { name: /Continue/ }).click()
  const start = new Date()
  start.setUTCSeconds(0, 0)
  start.setUTCMinutes(start.getUTCMinutes() + 16)
  const end = new Date(start.getTime() + 45 * 60_000)
  await page.getByLabel('Starts').fill(start.toISOString().slice(0, 16))
  await page.getByLabel('Ends').fill(end.toISOString().slice(0, 16))
  await page.getByLabel('Timezone').fill('UTC')
  await page.getByRole('button', { name: /Continue/ }).click()
  await page.getByLabel('Search participants').fill(participantEmail)
  await page.getByRole('button', { name: new RegExp(participantEmail) }).click()
  await page.getByRole('button', { name: /Continue/ }).click()
  await page
    .getByLabel('Meeting link (optional)')
    .fill('https://meet.example.test/release')
  await page.getByRole('button', { name: /Continue/ }).click()
  await page.getByLabel('Topic 1').fill('Release decision')
  await page.getByRole('button', { name: /Continue/ }).click()
  await page.getByRole('button', { name: 'Schedule meeting' }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
  const meetingId = page.url().split('/').at(-1)
  expect(meetingId).toBeTruthy()

  const temporarySession = await apiLogin(
    request,
    participantEmail,
    temporaryPassword,
  )
  const passwordChanged = await request.post(
    `${apiBase}/auth/change-password`,
    {
      headers: temporarySession.headers,
      data: {
        current_password: temporaryPassword,
        new_password: participantPassword,
        confirm_new_password: participantPassword,
      },
    },
  )
  expect(passwordChanged.ok(), await passwordChanged.text()).toBeTruthy()
  const participant = await apiLogin(
    request,
    participantEmail,
    participantPassword,
  )
  const invitationInbox = await request.get(`${apiBase}/notifications`, {
    headers: participant.headers,
  })
  const invitationPayload = (await invitationInbox.json()) as {
    data: { notifications: Array<{ notification_type: string }> }
  }
  expect(
    invitationPayload.data.notifications.some(
      (item) => item.notification_type === 'meeting_invitation',
    ),
  ).toBeTruthy()

  const participantContext = await browser.newContext({ baseURL: webBase })
  const participantPage = await participantContext.newPage()
  await browserLogin(participantPage, participantEmail, participantPassword)
  await participantPage.goto(`/meetings/${meetingId}`)

  const reminder = await waitForMeetingNotification(
    request,
    participant.headers,
    meetingId!,
    'meeting_reminder',
  )
  await participantPage.goto('/notifications')
  await expect(
    participantPage.getByRole('heading', { name: `Upcoming: ${title}` }),
  ).toBeVisible()
  const markedRead = await request.post(
    `${apiBase}/notifications/${reminder.notification.id}/read`,
    { headers: participant.headers },
  )
  expect(markedRead.ok(), await markedRead.text()).toBeTruthy()
  const afterRead = await request.get(`${apiBase}/notifications`, {
    headers: participant.headers,
  })
  const afterReadPayload = (await afterRead.json()) as {
    data: { unread: number }
  }
  expect(afterReadPayload.data.unread).toBe(reminder.unread - 1)
  await participantPage.goto(`/meetings/${meetingId}`)

  for (const status of ['tentative', 'declined', 'accepted']) {
    await participantPage.getByRole('button', { name: 'RSVP' }).click()
    await participantPage.getByRole('button', { name: status }).click()
    await expect(
      participantPage
        .getByRole('paragraph')
        .filter({ hasText: new RegExp(`^${status}$`) }),
    ).toBeVisible()
    const statusDetail = await request.get(`${apiBase}/meetings/${meetingId}`, {
      headers: organizer.headers,
    })
    const statusPayload = (await statusDetail.json()) as {
      data: {
        attendees: Array<{ email: string; attendance_status: string }>
      }
    }
    expect(
      statusPayload.data.attendees.find(
        (item) => item.email === participantEmail,
      )?.attendance_status,
    ).toBe(status)
  }

  const detail = await request.get(`${apiBase}/meetings/${meetingId}`, {
    headers: organizer.headers,
  })
  const detailPayload = (await detail.json()) as {
    data: { attendees: Array<{ email: string; attendance_status: string }> }
  }
  expect(
    detailPayload.data.attendees.find((item) => item.email === participantEmail)
      ?.attendance_status,
  ).toBe('accepted')

  const duplicateRsvp = await request.put(
    `${apiBase}/meetings/${meetingId}/rsvp`,
    {
      headers: participant.headers,
      data: { status: 'accepted' },
    },
  )
  expect(duplicateRsvp.ok(), await duplicateRsvp.text()).toBeTruthy()

  const rescheduledStart = new Date(start.getTime() + 86_400_000)
  const rescheduledEnd = new Date(end.getTime() + 86_400_000)
  const rescheduled = await request.post(
    `${apiBase}/meetings/${meetingId}/reschedule`,
    {
      headers: organizer.headers,
      data: {
        start_datetime: rescheduledStart.toISOString(),
        end_datetime: rescheduledEnd.toISOString(),
        timezone: 'America/Chicago',
      },
    },
  )
  expect(rescheduled.ok(), await rescheduled.text()).toBeTruthy()
  const rescheduledPayload = (await rescheduled.json()) as {
    data: { timezone: string }
  }
  expect(rescheduledPayload.data.timezone).toBe('America/Chicago')
  await participantPage.reload()
  await expect(
    participantPage.getByRole('heading', { name: title }),
  ).toBeVisible()

  await page.reload()
  await page.getByRole('button', { name: 'Cancel' }).click()
  await expect(page.getByText('cancelled', { exact: true })).toBeVisible()
  await participantPage.reload()
  await expect(
    participantPage.getByText('cancelled', { exact: true }),
  ).toBeVisible()

  const calendars = await request.get(`${apiBase}/calendars`, {
    headers: participant.headers,
  })
  const calendarPayload = (await calendars.json()) as {
    data: Array<{ id: string }>
  }
  const eventPages = await Promise.all(
    calendarPayload.data.map((calendar) =>
      request.get(`${apiBase}/calendars/${calendar.id}/events`, {
        headers: participant.headers,
      }),
    ),
  )
  const events = (
    await Promise.all(
      eventPages.map(
        async (response) =>
          (
            (await response.json()) as {
              data: Array<{
                meeting_id: string
                start_datetime: string
                status: string
              }>
            }
          ).data,
      ),
    )
  ).flat()
  const meetingEvents = events.filter((event) => event.meeting_id === meetingId)
  expect(meetingEvents).toHaveLength(1)
  expect(new Date(meetingEvents[0].start_datetime).getTime()).toBe(
    rescheduledStart.getTime(),
  )
  expect(meetingEvents[0].status).toBe('cancelled')

  const lifecycleInbox = await request.get(
    `${apiBase}/notifications?include_archived=true&page_size=100`,
    { headers: participant.headers },
  )
  const lifecyclePayload = (await lifecycleInbox.json()) as {
    data: {
      notifications: Array<{ meeting_id: string; notification_type: string }>
    }
  }
  const lifecycleTypes = new Set(
    lifecyclePayload.data.notifications
      .filter((item) => item.meeting_id === meetingId)
      .map((item) => item.notification_type),
  )
  expect(lifecycleTypes).toEqual(
    new Set([
      'meeting_invitation',
      'meeting_reminder',
      'meeting_updated',
      'meeting_cancelled',
    ]),
  )

  const audit = await request.get(`${apiBase}/audit?limit=200`, {
    headers: organizer.headers,
  })
  expect(audit.ok(), await audit.text()).toBeTruthy()
  const auditPayload = (await audit.json()) as {
    data: {
      items: Array<{
        action: string
        resource_id: string | null
      }>
    }
  }
  const meetingAuditActions = new Set(
    auditPayload.data.items
      .filter((item) => item.resource_id === meetingId)
      .map((item) => item.action),
  )
  expect(meetingAuditActions).toContain('MeetingCreated')
  expect(meetingAuditActions).toContain('MeetingRescheduled')
  expect(meetingAuditActions).toContain('MeetingCancelled')
  await participantContext.close()
})
