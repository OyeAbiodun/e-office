import { beforeEach, describe, expect, test, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/features/auth/api', () => ({
  apiBaseUrl: 'http://127.0.0.1:8001/api/v1',
  apiRequest: mocks.apiRequest,
  currentAccessToken: () => null,
}))

import { chatApi } from '@/features/chat/api'

describe('chat mutation feedback', () => {
  beforeEach(() => {
    mocks.apiRequest.mockClear()
  })

  test('keeps high-frequency chat mutations out of the global toast stream', async () => {
    await chatApi.send('conversation-1', { body: 'Hello' })
    await chatApi.saveDraft('conversation-1', 'Draft')
    await chatApi.read('conversation-1', 'message-1')
    await chatApi.react('message-1', '👍')

    expect(mocks.apiRequest).toHaveBeenCalledTimes(4)
    for (const request of mocks.apiRequest.mock.calls) {
      expect(request[3]).toBe(false)
    }
  })
})
