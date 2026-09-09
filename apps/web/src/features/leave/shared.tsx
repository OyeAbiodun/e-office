import { AlertCircle, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

import type { LeaveStatus } from './api'

const statusStyles: Record<LeaveStatus | string, string> = {
  draft:
    'border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200',
  submitted:
    'border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200',
  approved:
    'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200',
  rejected:
    'border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200',
  withdrawn:
    'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200',
  cancelled:
    'border-zinc-300 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200',
  open: 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200',
  closed:
    'border-zinc-300 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200',
  active:
    'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200',
  inactive:
    'border-zinc-300 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200',
}

export function StatusBadge({ value }: { value: string }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${statusStyles[value] ?? statusStyles.draft}`}
    >
      {value.replaceAll('_', ' ')}
    </span>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string
  title: string
  description: string
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-sm font-semibold text-primary">{eyebrow}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">{description}</p>
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  )
}

export function LoadingState({
  label = 'Loading leave information',
}: {
  label?: string
}) {
  return (
    <div
      className="grid min-h-56 place-items-center rounded-2xl border bg-card"
      aria-label={label}
    >
      <div className="text-center text-sm text-muted-foreground">
        <LoaderCircle className="mx-auto mb-3 size-6 animate-spin text-primary" />
        {label}…
      </div>
    </div>
  )
}

export function ErrorState({ retry }: { retry: () => void }) {
  return (
    <div
      className="grid min-h-56 place-items-center rounded-2xl border bg-card p-8 text-center"
      role="alert"
    >
      <div>
        <AlertCircle className="mx-auto size-8 text-destructive" />
        <h2 className="mt-3 font-semibold">
          Leave information could not be loaded
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Check your connection, then try again.
        </p>
        <button
          className="mt-4 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
          onClick={retry}
          type="button"
        >
          Retry
        </button>
      </div>
    </div>
  )
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string
  detail: string
  action?: ReactNode
}) {
  return (
    <div className="rounded-2xl border border-dashed bg-muted/20 p-8 text-center">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Modal({
  title,
  description,
  children,
  onClose,
  size = 'max-w-2xl',
}: {
  title: string
  description?: string
  children: ReactNode
  onClose: () => void
  size?: string
}) {
  return (
    <div
      className="fixed inset-0 z-[70] grid place-items-center bg-black/55 p-3 sm:p-6"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section
        aria-describedby={description ? 'leave-dialog-description' : undefined}
        aria-labelledby="leave-dialog-title"
        aria-modal="true"
        className={`max-h-[94vh] w-full ${size} overflow-y-auto rounded-2xl border bg-background shadow-2xl`}
        role="dialog"
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b bg-background/95 p-5 backdrop-blur">
          <div>
            <h2 className="text-xl font-semibold" id="leave-dialog-title">
              {title}
            </h2>
            {description && (
              <p
                className="mt-1 text-sm text-muted-foreground"
                id="leave-dialog-description"
              >
                {description}
              </p>
            )}
          </div>
          <button
            aria-label="Close dialog"
            className="rounded-lg px-3 py-1.5 text-xl text-muted-foreground hover:bg-muted"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </header>
        <div className="p-5">{children}</div>
      </section>
    </div>
  )
}

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm">
      <span className="text-muted-foreground">
        {total
          ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`
          : '0 results'}
      </span>
      <div className="flex items-center gap-2">
        <button
          className="rounded-lg border px-3 py-1.5 disabled:opacity-40"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          type="button"
        >
          Previous
        </button>
        <span aria-label={`Page ${page} of ${pages}`}>
          {page} / {pages}
        </span>
        <button
          className="rounded-lg border px-3 py-1.5 disabled:opacity-40"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          type="button"
        >
          Next
        </button>
      </div>
    </div>
  )
}

export function PersonMark({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
  return (
    <span
      aria-hidden="true"
      className="grid size-9 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary"
    >
      {initials || '?'}
    </span>
  )
}
