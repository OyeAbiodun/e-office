import { Link } from '@tanstack/react-router'
import { ArrowUpRight } from 'lucide-react'

export interface DecisionChartDatum {
  label: string
  value: number
  to: string
  tone?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
}

const toneClass = {
  primary: 'bg-primary',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
}

export function DecisionBarChart({
  title,
  description,
  data,
}: {
  title: string
  description: string
  data: DecisionChartDatum[]
}) {
  const maximum = Math.max(1, ...data.map((item) => item.value))
  const total = data.reduce((sum, item) => sum + item.value, 0)
  return (
    <section
      aria-label={`${title} chart`}
      className="surface min-w-0 p-5"
      data-decision-chart
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        <span className="rounded-lg bg-primary-subtle px-2.5 py-1 text-sm font-semibold text-primary">
          {total}
        </span>
      </div>
      <ul className="mt-5 space-y-3">
        {data.map((item) => (
          <li key={item.label}>
            <Link
              aria-label={`${item.label}: ${item.value}. Open filtered results`}
              className="group block rounded-lg outline-none transition focus-visible:ring-2 focus-visible:ring-primary"
              to={item.to as never}
            >
              <span className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium">{item.label}</span>
                <span className="flex items-center gap-1 tabular-nums text-muted-foreground group-hover:text-primary">
                  {item.value} <ArrowUpRight className="size-3.5" />
                </span>
              </span>
              <span
                aria-hidden="true"
                className="mt-1.5 block h-2 overflow-hidden rounded-full bg-muted"
              >
                <span
                  className={`block h-full min-w-1 rounded-full transition-all ${toneClass[item.tone ?? 'primary']}`}
                  style={{
                    width: `${Math.max(3, (item.value / maximum) * 100)}%`,
                  }}
                />
              </span>
            </Link>
          </li>
        ))}
        {!data.length && (
          <p className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
            No data is available for this period.
          </p>
        )}
      </ul>
      <p className="sr-only">
        {data.map((item) => `${item.label}: ${item.value}`).join('. ')}
      </p>
    </section>
  )
}
