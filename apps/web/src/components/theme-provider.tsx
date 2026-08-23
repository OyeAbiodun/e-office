import { type PropsWithChildren, useEffect, useMemo, useState } from 'react'

import { ThemeContext, type Theme } from '@/components/theme-context'

const storageKey = 'meetinghq-theme'

export function ThemeProvider({ children }: PropsWithChildren) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem(storageKey)
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
    localStorage.setItem(storageKey, theme)
  }, [theme])

  const value = useMemo(() => ({ theme, setTheme }), [theme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
