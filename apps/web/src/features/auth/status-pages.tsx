import { Link } from '@tanstack/react-router'
import { ShieldAlert } from 'lucide-react'

function StatusPage({
  code,
  title,
  description,
}: {
  code: string
  title: string
  description: string
}) {
  return (
    <div className="grid min-h-screen place-items-center p-6 text-center">
      <div>
        <ShieldAlert className="mx-auto size-11 text-primary" />
        <p className="mt-5 text-sm font-semibold text-primary">{code}</p>
        <h1 className="mt-2 text-3xl font-semibold">{title}</h1>
        <p className="mt-3 text-muted-foreground">{description}</p>
        <Link className="mt-7 inline-block font-medium text-primary" to="/">
          Return to dashboard
        </Link>
      </div>
    </div>
  )
}
export const UnauthorizedPage = () => (
  <StatusPage
    code="401"
    title="Sign in required"
    description="Your session is missing or has expired."
  />
)
export const ForbiddenPage = () => (
  <StatusPage
    code="403"
    title="Access denied"
    description="You do not have permission to view this page."
  />
)
