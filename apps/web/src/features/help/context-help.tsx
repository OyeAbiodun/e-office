import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { BookOpen, ChevronRight, GraduationCap, X } from 'lucide-react'
import { useState } from 'react'

import { helpApi } from '@/features/help/api'

export function ContextHelp({
  contextId,
  open,
  onClose,
}: {
  contextId: string
  open: boolean
  onClose: () => void
}) {
  const [tourStep, setTourStep] = useState<number | null>(null)
  const result = useQuery({
    queryKey: ['help-context', contextId],
    queryFn: () => helpApi.context(contextId),
    enabled: open,
  })
  if (!open) return null
  const tour = result.data?.tour
  const step = tourStep === null ? null : tour?.steps[tourStep]

  return (
    <div className="fixed inset-0 z-[90] bg-black/45" role="presentation">
      <aside
        aria-label="Help for this page"
        aria-modal="true"
        className="ml-auto flex h-full w-full max-w-md flex-col border-l bg-background shadow-2xl"
        role="dialog"
      >
        <header className="flex items-center gap-3 border-b p-5">
          <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
            <BookOpen className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold">Help for this page</h2>
            <p className="truncate text-xs text-muted-foreground">
              {contextId}
            </p>
          </div>
          <button
            aria-label="Close contextual help"
            className="rounded-lg p-2 hover:bg-muted"
            onClick={onClose}
            type="button"
          >
            <X className="size-4" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-5">
          {result.isLoading && (
            <div className="space-y-3" aria-label="Loading contextual help">
              <div className="h-7 w-3/4 animate-pulse rounded bg-muted" />
              <div className="h-20 animate-pulse rounded bg-muted" />
            </div>
          )}
          {result.isError && (
            <p className="rounded-xl bg-destructive/10 p-4 text-sm text-destructive">
              Help could not be loaded. Try again.
            </p>
          )}
          {result.data?.article ? (
            <>
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                {result.data.article.category}
              </p>
              <h3 className="mt-2 text-2xl font-semibold">
                {result.data.article.title}
              </h3>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                {result.data.article.summary}
              </p>
              <a
                className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-primary"
                href={`/help?article=${encodeURIComponent(result.data.article.slug)}`}
                onClick={onClose}
              >
                Read full guide <ChevronRight className="size-4" />
              </a>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No page-specific guide has been published yet. Search the Help
              Center for general guidance.
            </p>
          )}
          {tour && (
            <section className="mt-7 rounded-2xl border bg-card p-4">
              <div className="flex gap-3">
                <GraduationCap className="size-5 text-primary" />
                <div>
                  <h3 className="font-semibold">{tour.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {tour.description}
                  </p>
                </div>
              </div>
              {step ? (
                <div className="mt-4 rounded-xl bg-muted p-4">
                  <p className="text-xs font-semibold text-primary">
                    Step {Number(tourStep) + 1} of {tour.steps.length}
                  </p>
                  <p className="mt-2 font-medium">{step.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {step.body}
                  </p>
                  <button
                    className="mt-4 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground"
                    onClick={() =>
                      setTourStep((current) =>
                        current === null || current + 1 >= tour.steps.length
                          ? null
                          : current + 1,
                      )
                    }
                    type="button"
                  >
                    {Number(tourStep) + 1 >= tour.steps.length
                      ? 'Finish'
                      : 'Next'}
                  </button>
                </div>
              ) : (
                <button
                  className="mt-4 w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
                  onClick={() => setTourStep(0)}
                  type="button"
                >
                  Start walkthrough
                </button>
              )}
            </section>
          )}
        </div>
        <footer className="border-t p-4">
          <Link
            className="block rounded-xl border px-4 py-2.5 text-center text-sm font-semibold hover:bg-muted"
            onClick={onClose}
            to="/help"
          >
            Browse all documentation
          </Link>
        </footer>
      </aside>
    </div>
  )
}
