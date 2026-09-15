import { Workflow } from 'lucide-react'

import { PRODUCT } from '@/lib/product'

export function ProductWordmark({
  compact = false,
  inverse = false,
}: {
  compact?: boolean
  inverse?: boolean
}) {
  return (
    <span
      aria-label={PRODUCT.name}
      className="inline-flex min-w-0 items-center gap-2.5"
    >
      <span
        aria-hidden="true"
        className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-primary text-primary-foreground shadow-sm shadow-primary/20"
      >
        <Workflow className="size-[18px]" strokeWidth={2.1} />
      </span>
      {!compact && (
        <span className="min-w-0">
          <span
            className={`block truncate text-[15px] font-semibold tracking-[-0.01em] ${inverse ? 'text-white' : 'text-foreground'}`}
          >
            {PRODUCT.name}
          </span>
          <span
            className={`block truncate text-[10px] font-medium uppercase tracking-[0.15em] ${inverse ? 'text-blue-100/70' : 'text-muted-foreground'}`}
          >
            {PRODUCT.tagline}
          </span>
        </span>
      )}
    </span>
  )
}
