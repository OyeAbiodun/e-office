import { expect, test } from '@playwright/test'

const apiBase = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8001/api/v1'

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value) throw new Error(`${name} must be set for browser acceptance`)
  return value
}

const organizerEmail = requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL')
const organizerPassword = requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD')

test('chat connects its WebSocket to the configured MeetingHQ API', async ({
  page,
  request,
}) => {
  const login = await request.post(`${apiBase}/auth/login`, {
    data: { email: organizerEmail, password: organizerPassword },
  })
  expect(login.ok()).toBeTruthy()
  const session = (await login.json()) as {
    data: { access_token: string }
  }
  const conversations = await request.get(`${apiBase}/conversations`, {
    headers: { Authorization: `Bearer ${session.data.access_token}` },
  })
  expect(conversations.ok()).toBeTruthy()
  const conversationData = (await conversations.json()) as {
    data: Array<{ id: string }>
  }
  expect(conversationData.data.length).toBeGreaterThan(0)

  await page.goto('/')
  const socketBase = apiBase.replace(/^http/, 'ws')
  const outcome = await page.evaluate(
    ({ conversationId, socketBase, token }) =>
      new Promise<'open' | 'closed' | 'error'>((resolve) => {
        const socket = new WebSocket(
          `${socketBase}/chat/ws/${conversationId}?token=${encodeURIComponent(token)}`,
        )
        const timeout = window.setTimeout(() => {
          socket.close()
          resolve('closed')
        }, 10_000)
        socket.onopen = () => {
          window.clearTimeout(timeout)
          socket.close()
          resolve('open')
        }
        socket.onerror = () => {
          window.clearTimeout(timeout)
          resolve('error')
        }
        socket.onclose = () => {
          window.clearTimeout(timeout)
          resolve('closed')
        }
      }),
    {
      conversationId: conversationData.data[0].id,
      socketBase,
      token: session.data.access_token,
    },
  )

  expect(outcome).toBe('open')
})
