import { useEffect, useState } from 'react'

import { authenticatedAsset } from '@/features/auth/api'

interface AuthenticatedAvatarProps {
  alt: string
  fallback: string
  src: string | null
  className?: string
}

export function AuthenticatedAvatar({
  alt,
  fallback,
  src,
  className,
}: AuthenticatedAvatarProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let createdUrl: string | null = null
    setObjectUrl(null)
    if (!src) return
    void authenticatedAsset(src)
      .then((blob) => {
        if (!active) return
        createdUrl = URL.createObjectURL(blob)
        setObjectUrl(createdUrl)
      })
      .catch(() => setObjectUrl(null))
    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [src])

  if (!objectUrl) return <span aria-hidden="true">{fallback || 'U'}</span>
  return <img alt={alt} className={className} src={objectUrl} />
}
