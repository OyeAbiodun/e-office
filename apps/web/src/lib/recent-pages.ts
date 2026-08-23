export interface RecentPage {
  path: string
  label: string
  parent: string
  icon: string
  visitedAt: string
}

const eventName = 'meetinghq:recent-pages'

function storageKey(userId: string) {
  return `meetinghq:recent-pages:${userId}`
}

export function recentPages(userId: string): RecentPage[] {
  try {
    const value = window.localStorage.getItem(storageKey(userId))
    return value ? (JSON.parse(value) as RecentPage[]) : []
  } catch {
    return []
  }
}

export function recordRecentPage(userId: string, page: RecentPage) {
  const pages = recentPages(userId).filter((item) => item.path !== page.path)
  window.localStorage.setItem(
    storageKey(userId),
    JSON.stringify([page, ...pages].slice(0, 20)),
  )
  window.dispatchEvent(new CustomEvent(eventName))
}

export function subscribeRecentPages(listener: () => void) {
  window.addEventListener(eventName, listener)
  window.addEventListener('storage', listener)
  return () => {
    window.removeEventListener(eventName, listener)
    window.removeEventListener('storage', listener)
  }
}
