import { Link, Outlet } from '@tanstack/react-router'

import { ProductWordmark } from '@/components/product-wordmark'
import { PRODUCT } from '@/lib/product'

export function AuthLayout() {
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[minmax(28rem,0.86fr)_1.14fr]">
      <aside className="relative hidden overflow-hidden border-r bg-primary-subtle p-12 lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_16%_18%,color-mix(in_oklch,var(--primary)_15%,transparent),transparent_38%)]" />
        <Link className="relative inline-flex self-start" to="/login">
          <ProductWordmark />
        </Link>
        <div className="relative my-auto max-w-lg">
          <p className="mb-4 text-sm font-semibold uppercase tracking-[0.16em] text-primary">
            {PRODUCT.tagline}
          </p>
          <h1 className="text-[2.75rem] font-semibold leading-[1.08] tracking-[-0.04em] text-foreground">
            Every team, task, and operation. One flow.
          </h1>
          <p className="mt-6 max-w-md text-[17px] leading-7 text-muted-foreground">
            {PRODUCT.description} Built for focused work and accountable
            delivery.
          </p>
          <p className="mt-10 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {PRODUCT.category}
          </p>
        </div>
      </aside>
      <main className="grid min-h-screen place-items-center bg-card p-5 sm:p-10 dark:bg-background">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <ProductWordmark />
          </div>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
