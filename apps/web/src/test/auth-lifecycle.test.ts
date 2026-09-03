const user = {
  id: 'user-1',
  organization_id: 'organization-1',
  email: 'admin@meetinghq.test',
  username: 'admin',
  first_name: 'Admin',
  last_name: 'User',
  display_name: 'Admin User',
  avatar_url: null,
  email_verified: true,
  force_password_change: false,
  roles: ['Super Admin'],
  permissions: ['admin.manage'],
}

const tokenResponse = {
  access_token: 'access-token',
  token_type: 'bearer',
  expires_in: 900,
  refresh_token: 'rotated-refresh-token',
  csrf_token: 'rotated-csrf-token',
  user,
}

test('startup restoration is single-flight and resolves the current user once', async () => {
  vi.resetModules()
  document.cookie = 'meetinghq_csrf=initial-csrf-token; path=/'
  let refreshCalls = 0
  let currentUserCalls = 0
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
    const url = String(input)
    if (url.endsWith('/auth/refresh')) {
      refreshCalls += 1
      expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe(
        'initial-csrf-token',
      )
      return Response.json({ success: true, data: tokenResponse })
    }
    if (url.endsWith('/auth/me')) {
      currentUserCalls += 1
      expect(new Headers(options?.headers).get('Authorization')).toBe(
        'Bearer access-token',
      )
      return Response.json({ success: true, data: user })
    }
    return new Response(null, { status: 404 })
  })

  const { authApi } = await import('@/features/auth/api')
  const [first, second] = await Promise.all([
    authApi.restoreSession(),
    authApi.restoreSession(),
  ])

  expect(first.id).toBe(user.id)
  expect(second.id).toBe(user.id)
  expect(refreshCalls).toBe(1)
  expect(currentUserCalls).toBe(0)
})

test('surfaces a safe field-level validation message instead of a generic mutation error', async () => {
  vi.resetModules()
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    Response.json(
      {
        success: false,
        error: {
          message: 'The request could not be completed.',
          details: {
            detail: [
              {
                loc: ['body', 'new_password'],
                msg: 'Field required',
              },
            ],
          },
        },
      },
      { status: 422 },
    ),
  )

  const { authApi, ApiError } = await import('@/features/auth/api')
  await expect(
    authApi.resetPassword({ token: 'safe-test-token' }),
  ).rejects.toEqual(new ApiError('new_password: Field required', 422))
})
