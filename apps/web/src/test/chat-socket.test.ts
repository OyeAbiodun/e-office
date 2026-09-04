import { apiBaseUrl } from '@/features/auth/api'
import { chatSocketUrl } from '@/features/chat/api'

test('builds a chat WebSocket URL from the configured MeetingHQ API origin', () => {
  const url = chatSocketUrl('conversation-1', 'access token')

  expect(url).toBe(
    `${apiBaseUrl.replace(/^http/, 'ws')}/chat/ws/conversation-1?token=access%20token`,
  )
  expect(url).not.toContain(':8000/')
})
