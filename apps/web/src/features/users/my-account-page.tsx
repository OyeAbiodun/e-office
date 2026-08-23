import { Link } from '@tanstack/react-router'
import { KeyRound, MonitorSmartphone, UserRound } from 'lucide-react'

export function MyAccountPage() {
  return (
    <div className="mx-auto max-w-4xl p-5 sm:p-8">
      <h1 className="text-3xl font-semibold">My account</h1>
      <p className="mt-2 text-muted-foreground">
        Identity, security, and account preferences.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        <Card
          icon={UserRound}
          title="Profile"
          description="Name, avatar, and locale"
          to="/profile"
        />
        <Card
          icon={MonitorSmartphone}
          title="Sessions"
          description="Active devices"
          to="/settings/sessions"
        />
        <Card
          icon={KeyRound}
          title="Security"
          description="Password and verification"
          to="/profile"
        />
      </div>
    </div>
  )
}
function Card({
  icon: Icon,
  title,
  description,
  to,
}: {
  icon: typeof UserRound
  title: string
  description: string
  to: '/profile' | '/settings/sessions'
}) {
  return (
    <Link
      className="rounded-2xl border bg-card p-5 transition hover:border-primary/40"
      to={to}
    >
      <Icon className="size-5 text-primary" />
      <h2 className="mt-4 font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </Link>
  )
}
