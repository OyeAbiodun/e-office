import { describe, expect, it } from 'vitest'

import { resolveApiProxyOrigin } from '@/config/api-url'

describe('Vite API URL handling', () => {
  it.each([undefined, '', '  ', '/api/v1', ' /api/v1/ '])(
    'does not create a development proxy for %s',
    (value) => {
      expect(resolveApiProxyOrigin(value)).toBeNull()
    },
  )

  it.each([
    ['http://localhost:8000/api/v1', 'http://localhost:8000'],
    ['https://api.officeflow.test/api/v1', 'https://api.officeflow.test'],
  ])('creates a proxy origin for %s', (value, expected) => {
    expect(resolveApiProxyOrigin(value)).toBe(expected)
  })

  it.each([
    'api/v1',
    '//api.officeflow.test/api/v1',
    '/api/v1?tenant=one',
    '/api/v1#fragment',
    'redis://localhost:6379/0',
    'not a URL',
  ])('rejects invalid API URL %s', (value) => {
    expect(() => resolveApiProxyOrigin(value)).toThrow(/VITE_API_URL/)
  })
})
