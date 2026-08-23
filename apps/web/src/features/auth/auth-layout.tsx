import { Link, Outlet } from '@tanstack/react-router'
import { Sparkles } from 'lucide-react'

export function AuthLayout() {
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-[#081a3a] p-12 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(59,130,246,.35),transparent_38%)]" />
        <Link
          className="relative flex items-center gap-3 font-semibold"
          to="/login"
        >
          <span className="grid size-10 place-items-center rounded-xl bg-blue-500">
            <Sparkles className="size-5" />
          </span>
          MeetingHQ
        </Link>
        <div className="relative my-auto max-w-lg">
          <p className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-blue-300">
            Schedule. Meet. Collaborate.
          </p>
          <h1 className="text-5xl font-semibold leading-tight tracking-tight">
            Your digital workplace, thoughtfully connected.
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-blue-100/75">
            Secure identity, focused collaboration, and intelligent meetings in
            one enterprise workspace.
          </p>
        </div>
      </aside>
      <main className="grid min-h-screen place-items-center p-5 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground">
              <Sparkles className="size-4" />
            </span>
            <span className="font-semibold">MeetingHQ</span>
          </div>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
