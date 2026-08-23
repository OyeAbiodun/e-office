import { Link, useNavigate } from '@tanstack/react-router'
import {
  Bell,
  Clock3,
  LogOut,
  Palette,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import { useEffect, useRef, useState, useSyncExternalStore } from 'react'

import { useAuth } from '@/features/auth/auth-store'
import { recentPages, subscribeRecentPages } from '@/lib/recent-pages'

const accountLinks = [
  { label: 'My Profile', to: '/profile', icon: UserRound },
  { label: 'Security & MFA', to: '/profile/security', icon: ShieldCheck },
  {
    label: 'Notification Preferences',
    to: '/profile/notifications',
    icon: Bell,
  },
  {
    label: 'Account Preferences',
    to: '/profile/preferences',
    icon: Palette,
  },
] as const

export function ProfileMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const container = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const recent = useSyncExternalStore(
    subscribeRecentPages,
    () => (user ? JSON.stringify(recentPages(user.id).slice(0, 3)) : '[]'),
    () => '[]',
  )

  useEffect(() => {
    if (!open) return
    const closeOutside = (event: PointerEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  if (!user) return null
  const recentItems = JSON.parse(recent) as ReturnType<typeof recentPages>
  const initials = `${user.first_name.slice(0, 1)}${user.last_name.slice(0, 1)}`
  return (
    <div className="relative" ref={container}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Open user account menu"
        className="grid size-9 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground shadow-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        {initials || 'U'}
      </button>
      {open && (
        <div
          aria-label="User account"
          className="absolute right-0 top-11 z-50 w-72 rounded-2xl border bg-card p-2 shadow-2xl"
          role="menu"
        >
          <div className="border-b p-3">
            <p className="font-semibold">{user.display_name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {user.email}
            </p>
            <p className="mt-1 text-xs font-medium text-primary">
              {user.roles[0] ?? 'MeetingHQ member'}
            </p>
          </div>
          <div className="py-2">
            {accountLinks.map(({ label, to, icon: Icon }) => (
              <Link
                className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                key={to}
                onClick={() => setOpen(false)}
                role="menuitem"
                to={to}
              >
                <Icon className="size-4 text-muted-foreground" />
                {label}
              </Link>
            ))}
          </div>
          {recentItems.length > 0 && (
            <div className="border-t py-2">
              <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Recent pages
              </p>
              {recentItems.map((item) => (
                <a
                  className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-muted"
                  href={item.path}
                  key={item.path}
                  onClick={(event) => {
                    event.preventDefault()
                    setOpen(false)
                    void navigate({ to: item.path as never })
                  }}
                  role="menuitem"
                >
                  <Clock3 className="size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0">
                    <span className="block truncate">{item.label}</span>
                    <span className="block truncate text-[10px] text-muted-foreground">
                      {item.parent}
                    </span>
                  </span>
                </a>
              ))}
            </div>
          )}
          <div className="border-t pt-2">
            <button
              className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-red-600 hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() =>
                void logout().then(() => navigate({ to: '/login' }))
              }
              role="menuitem"
              type="button"
            >
              <LogOut className="size-4" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
