import { type PropsWithChildren, useEffect, useMemo, useState } from 'react'

import { ThemeContext, type Theme } from '@/components/theme-context'
import { LEGACY_THEME_STORAGE_KEY, THEME_STORAGE_KEY } from '@/lib/product'

export function ThemeProvider({ children }: PropsWithChildren) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved =
      localStorage.getItem(THEME_STORAGE_KEY) ??
      localStorage.getItem(LEGACY_THEME_STORAGE_KEY)
    return saved === 'light' || saved === 'dark' || saved === 'system'
      ? saved
      : 'system'
  })

  useEffect(() => {
    const root = document.documentElement
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    root.classList.toggle(
      'dark',
      theme === 'dark' || (theme === 'system' && systemDark),
    )
    localStorage.setItem(THEME_STORAGE_KEY, theme)
    localStorage.removeItem(LEGACY_THEME_STORAGE_KEY)
  }, [theme])

  const value = useMemo(() => ({ theme, setTheme }), [theme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
