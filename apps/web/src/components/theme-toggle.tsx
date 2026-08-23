import { Monitor, Moon, Sun } from 'lucide-react'

import { useTheme } from '@/components/theme-context'

const themes = [
  { value: 'light', label: 'Light theme', icon: Sun },
  { value: 'dark', label: 'Dark theme', icon: Moon },
  { value: 'system', label: 'System theme', icon: Monitor },
] as const

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <div
      className="flex rounded-lg border border-border bg-muted p-0.5"
      aria-label="Theme"
    >
      {themes.map(({ value, label, icon: Icon }) => (
        <button
          aria-label={label}
          aria-pressed={theme === value}
          className="rounded-md p-1.5 text-muted-foreground transition hover:text-foreground aria-pressed:bg-background aria-pressed:text-foreground aria-pressed:shadow-sm"
          key={value}
          onClick={() => setTheme(value)}
          type="button"
        >
          <Icon aria-hidden="true" className="size-4" />
        </button>
      ))}
    </div>
  )
}
