const validationBaseUrl = 'http://vite.invalid'

/** Return a development proxy origin, or null for a valid same-origin path. */
export function resolveApiProxyOrigin(
  value: string | undefined,
): string | null {
  const configuredApiUrl = value?.trim()
  if (!configuredApiUrl) return null

  if (configuredApiUrl.startsWith('/') && !configuredApiUrl.startsWith('//')) {
    const relativeUrl = new URL(configuredApiUrl, validationBaseUrl)
    if (
      relativeUrl.origin !== validationBaseUrl ||
      relativeUrl.search ||
      relativeUrl.hash
    ) {
      throw new Error(
        'VITE_API_URL must be a same-origin path without a query or fragment, or an absolute HTTP(S) URL',
      )
    }
    return null
  }

  let absoluteUrl: URL
  try {
    absoluteUrl = new URL(configuredApiUrl)
  } catch {
    throw new Error(
      'VITE_API_URL must be a same-origin path beginning with / or an absolute HTTP(S) URL',
    )
  }
  if (absoluteUrl.protocol !== 'http:' && absoluteUrl.protocol !== 'https:') {
    throw new Error('VITE_API_URL absolute URLs must use HTTP or HTTPS')
  }
  return absoluteUrl.origin
}
