import { Link } from '@tanstack/react-router'
import { ArrowRight, type LucideIcon, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'

export function Page({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={`page-container ${className}`.trim()}>{children}</div>
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
  meta?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="page-eyebrow">{eyebrow}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="page-title">{title}</h1>
          {meta}
        </div>
        <p className="page-description">{description}</p>
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      )}
    </header>
  )
}

export function Surface({
  children,
  className = '',
  as: Element = 'section',
}: {
  children: ReactNode
  className?: string
  as?: 'section' | 'article' | 'div'
}) {
  return <Element className={`surface ${className}`.trim()}>{children}</Element>
}

export function MetricLink({
  label,
  value,
  detail,
  to,
  icon: Icon,
  tone = 'default',
}: {
  label: string
  value: string | number
  detail?: string
  to: string
  icon: LucideIcon
  tone?: 'default' | 'danger' | 'warning' | 'success'
}) {
  return (
    <Link
      aria-label={`${label}: ${value}. View details`}
      className="metric-link group"
      to={to as never}
    >
      <span className={`metric-icon metric-icon-${tone}`}>
        <Icon aria-hidden="true" className="size-[18px]" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[12px] font-medium text-muted-foreground">
          {label}
        </span>
        <span className="mt-1 block text-2xl font-semibold tracking-[-0.025em]">
          {value}
        </span>
        {detail && (
          <span className="mt-1 block truncate text-xs text-muted-foreground">
            {detail}
          </span>
        )}
      </span>
      <ArrowRight
        aria-hidden="true"
        className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
      />
    </Link>
  )
}

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div aria-label={label} className="space-y-3" role="status">
      <div className="skeleton h-12 w-2/5" />
      <div className="grid gap-3 md:grid-cols-3">
        <div className="skeleton h-28" />
        <div className="skeleton h-28" />
        <div className="skeleton h-28" />
      </div>
      <div className="skeleton h-64" />
    </div>
  )
}

export function ErrorState({
  title,
  description,
  onRetry,
}: {
  title: string
  description: string
  onRetry?: () => void
}) {
  return (
    <div className="state-panel" role="alert">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      {onRetry && (
        <button
          className="button-secondary mt-4"
          onClick={onRetry}
          type="button"
        >
          <RefreshCw className="size-4" /> Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="state-panel">
      <span className="mx-auto grid size-10 place-items-center rounded-xl bg-primary-subtle text-primary">
        <Icon aria-hidden="true" className="size-5" />
      </span>
      <h2 className="mt-3 font-semibold">{title}</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        {description}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
