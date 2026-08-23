import { Outlet } from '@tanstack/react-router'
import { Suspense } from 'react'

export function RouteOutlet() {
  return (
    <Suspense
      fallback={
        <div
          aria-label="Loading page"
          aria-live="polite"
          className="space-y-3 p-8"
          role="status"
        >
          {[1, 2, 3].map((item) => (
            <div
              className="h-20 animate-pulse rounded-xl bg-muted"
              key={item}
            />
          ))}
        </div>
      }
    >
      <Outlet />
    </Suspense>
  )
}
