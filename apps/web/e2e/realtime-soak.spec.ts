import { expect, test } from '@playwright/test'

const apiBase = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8001/api/v1'

function requiredEnvironment(name: string) {
  const value = process.env[name]
  if (!value) throw new Error(`${name} must be set for realtime acceptance`)
  return value
}

const email = requiredEnvironment('PLAYWRIGHT_ORGANIZER_EMAIL')
const password = requiredEnvironment('PLAYWRIGHT_ORGANIZER_PASSWORD')

test('ten authenticated chat sockets remain connected for a bounded soak and reconnect', async ({
  page,
  request,
}) => {
  test.setTimeout(90_000)
  const login = await request.post(`${apiBase}/auth/login`, {
    data: { email, password },
  })
  expect(login.ok(), await login.text()).toBeTruthy()
  const session = (
    (await login.json()) as {
      data: { access_token: string; csrf_token: string }
    }
  ).data
  const token = session.access_token
  const headers = {
    Authorization: `Bearer ${token}`,
    'X-CSRF-Token': session.csrf_token,
  }
  const conversations = await request.get(`${apiBase}/conversations`, {
    headers,
  })
  expect(conversations.ok(), await conversations.text()).toBeTruthy()
  let conversationId = (
    (await conversations.json()) as { data: Array<{ id: string }> }
  ).data[0]?.id
  if (!conversationId) {
    const workspaces = await request.get(`${apiBase}/workspaces`, { headers })
    expect(workspaces.ok(), await workspaces.text()).toBeTruthy()
    const workspaceId = (
      (await workspaces.json()) as { data: Array<{ id: string }> }
    ).data[0]?.id
    expect(workspaceId).toBeTruthy()
    const created = await request.post(`${apiBase}/conversations`, {
      headers,
      data: {
        workspace_id: workspaceId,
        type: 'workspace',
        name: `Realtime soak ${Date.now()}`,
      },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    conversationId = ((await created.json()) as { data: { id: string } }).data
      .id
  }
  expect(conversationId).toBeTruthy()

  const result = await page.evaluate(
    async ({ apiBase, conversationId, token }) => {
      const url = `${apiBase.replace(/^http/, 'ws')}/chat/ws/${conversationId}?token=${encodeURIComponent(token)}`
      const connect = () =>
        new Promise<WebSocket>((resolve, reject) => {
          const socket = new WebSocket(url)
          const timer = window.setTimeout(
            () => reject(new Error('WebSocket connection timed out')),
            10_000,
          )
          socket.onopen = () => {
            window.clearTimeout(timer)
            resolve(socket)
          }
          socket.onerror = () => {
            window.clearTimeout(timer)
            reject(new Error('WebSocket connection failed'))
          }
        })
      const sockets = await Promise.all(
        Array.from({ length: 10 }, () => connect()),
      )
      await new Promise((resolve) => window.setTimeout(resolve, 60_000))
      const openAfterSoak = sockets.filter(
        (socket) => socket.readyState === WebSocket.OPEN,
      ).length
      sockets.forEach((socket) => socket.close())
      const reconnected = await connect()
      const reconnectOpen = reconnected.readyState === WebSocket.OPEN
      reconnected.close()
      return { openAfterSoak, reconnectOpen }
    },
    { apiBase, conversationId: conversationId!, token },
  )

  expect(result).toEqual({ openAfterSoak: 10, reconnectOpen: true })
})
