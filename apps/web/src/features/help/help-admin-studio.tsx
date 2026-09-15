import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Eye,
  FileClock,
  ImagePlus,
  Plus,
  Save,
  Search,
  Sparkles,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { EmptyState, LoadingState, Surface } from '@/components/page'
import {
  helpApi,
  type HelpArticle,
  type HelpArticleDraft,
} from '@/features/help/api'

const emptyDraft: HelpArticleDraft = {
  slug: '',
  title: '',
  summary: '',
  category: 'User Handbook',
  content:
    '# New guide\n\n## What this feature does\n\nDescribe the outcome.\n\n## How to use it\n\n1. Add the first step.',
  workflow_status: 'draft',
  search_weight: 100,
  context_ids: [],
  related_slugs: [],
  video_metadata: null,
}

export function HelpAdminStudio() {
  const queryClient = useQueryClient()
  const editor = useRef<HTMLTextAreaElement>(null)
  const [search, setSearch] = useState('')
  const [selectedSlug, setSelectedSlug] = useState('')
  const [isNew, setIsNew] = useState(false)
  const [preview, setPreview] = useState(false)
  const [draft, setDraft] = useState<HelpArticleDraft>(emptyDraft)
  const articles = useQuery({
    queryKey: ['help-admin-articles'],
    queryFn: () => helpApi.articles('', true),
  })
  const analytics = useQuery({
    queryKey: ['help-analytics'],
    queryFn: helpApi.analytics,
  })
  const selected = articles.data?.find(
    (article) => article.slug === selectedSlug,
  )
  const versions = useQuery({
    queryKey: ['help-versions', selectedSlug],
    queryFn: () => helpApi.versions(selectedSlug),
    enabled: Boolean(selectedSlug) && !isNew,
  })
  const attachments = useQuery({
    queryKey: ['help-attachments', selected?.id],
    queryFn: () => helpApi.attachments(selected!.id),
    enabled: Boolean(selected?.id),
  })

  useEffect(() => {
    if (!selected && articles.data?.[0] && !isNew)
      setSelectedSlug(articles.data[0].slug)
  }, [articles.data, isNew, selected])
  useEffect(() => {
    if (!selected || isNew) return
    setDraft({
      slug: selected.slug,
      title: selected.title,
      summary: selected.summary,
      category: selected.category,
      content: selected.content,
      workflow_status: selected.workflow_status,
      search_weight: selected.search_weight,
      context_ids: selected.context_ids,
      related_slugs: selected.related_slugs,
      video_metadata: selected.video_metadata,
    })
  }, [isNew, selected])

  const save = useMutation({
    mutationFn: () =>
      isNew
        ? helpApi.createArticle(draft)
        : helpApi.reviseArticle(draft.slug, withoutSlug(draft)),
    onSuccess: (article) => {
      setIsNew(false)
      setSelectedSlug(article.slug)
      queryClient.invalidateQueries({ queryKey: ['help-admin-articles'] })
      queryClient.invalidateQueries({ queryKey: ['help-articles'] })
      queryClient.invalidateQueries({
        queryKey: ['help-versions', article.slug],
      })
      queryClient.invalidateQueries({ queryKey: ['help-analytics'] })
    },
  })
  const upload = useMutation({
    mutationFn: (file: File) => helpApi.uploadAttachment(selected!.id, file),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ['help-attachments', selected?.id],
      }),
  })
  const rows = (articles.data ?? []).filter((article) =>
    `${article.title} ${article.category} ${article.workflow_status}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  )

  function startNew() {
    setIsNew(true)
    setSelectedSlug('')
    setDraft(emptyDraft)
    setPreview(false)
  }
  function insertMarkdown(before: string, after = '') {
    const field = editor.current
    if (!field) return
    const start = field.selectionStart
    const end = field.selectionEnd
    const next = `${draft.content.slice(0, start)}${before}${draft.content.slice(start, end)}${after}${draft.content.slice(end)}`
    setDraft((current) => ({ ...current, content: next }))
    requestAnimationFrame(() => {
      field.focus()
      field.setSelectionRange(start + before.length, end + before.length)
    })
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <div className="space-y-5">
        <section
          className="grid grid-cols-3 gap-2"
          aria-label="Knowledge analytics"
        >
          <Stat
            value={analytics.data?.published_articles ?? 0}
            label="Published"
          />
          <Stat value={analytics.data?.total_views ?? 0} label="Views" />
          <Stat value={analytics.data?.favorite_count ?? 0} label="Favorites" />
        </section>
        <Surface className="p-3">
          <div className="flex items-center gap-2 p-2">
            <div className="relative min-w-0 flex-1">
              <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
              <input
                aria-label="Search help content"
                className="h-9 w-full rounded-lg border bg-background pl-9 pr-3 text-sm"
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search content"
                value={search}
              />
            </div>
            <button
              aria-label="Create guide"
              className="button-primary p-2"
              onClick={startNew}
              type="button"
            >
              <Plus className="size-4" />
            </button>
          </div>
          {articles.isLoading && <LoadingState label="Loading content" />}
          <div className="max-h-[680px] space-y-1 overflow-y-auto">
            {rows.map((article) => (
              <button
                className={`w-full rounded-xl p-3 text-left ${selectedSlug === article.slug && !isNew ? 'bg-primary/10' : 'hover:bg-muted'}`}
                key={article.id}
                onClick={() => {
                  setIsNew(false)
                  setSelectedSlug(article.slug)
                }}
                type="button"
              >
                <span className="block truncate text-sm font-semibold">
                  {article.title}
                </span>
                <span className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>{article.category}</span>
                  <span className="status-badge">
                    {article.workflow_status}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </Surface>
      </div>
      <Surface className="p-5 sm:p-7">
        {!selected && !isNew ? (
          <EmptyState
            title="Choose a guide"
            description="Select existing content or create a new guide."
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-5">
              <div>
                <p className="page-eyebrow">Content studio</p>
                <h2 className="text-xl font-semibold">
                  {isNew ? 'Create a guide' : `Edit ${selected?.title}`}
                </h2>
              </div>
              <div className="flex gap-2">
                <button
                  className="button-secondary"
                  onClick={() => setPreview((current) => !current)}
                  type="button"
                >
                  <Eye className="size-4" />
                  {preview ? 'Edit' : 'Preview'}
                </button>
                <button
                  className="button-primary"
                  disabled={
                    save.isPending ||
                    !draft.slug ||
                    !draft.title ||
                    !draft.summary
                  }
                  onClick={() => save.mutate()}
                  type="button"
                >
                  <Save className="size-4" />
                  {save.isPending
                    ? 'Saving…'
                    : isNew
                      ? 'Create guide'
                      : 'Save revision'}
                </button>
              </div>
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <Field
                label="Title"
                value={draft.title}
                onChange={(value) =>
                  setDraft((current) => ({ ...current, title: value }))
                }
              />
              <Field
                disabled={!isNew}
                label="Slug"
                value={draft.slug}
                onChange={(value) =>
                  setDraft((current) => ({
                    ...current,
                    slug: value
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, '-')
                      .replace(/(^-|-$)/g, ''),
                  }))
                }
              />
              <Field
                label="Category"
                value={draft.category}
                onChange={(value) =>
                  setDraft((current) => ({ ...current, category: value }))
                }
              />
              <label className="grid gap-2 text-sm font-medium">
                Workflow
                <select
                  className="h-11 rounded-xl border bg-background px-3"
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      workflow_status: event.target
                        .value as HelpArticle['workflow_status'],
                    }))
                  }
                  value={draft.workflow_status}
                >
                  <option value="draft">Draft</option>
                  <option value="review">In review</option>
                  <option value="published">Published</option>
                  <option value="archived">Archived</option>
                </select>
              </label>
            </div>
            <label className="mt-4 grid gap-2 text-sm font-medium">
              Summary
              <textarea
                className="min-h-20 rounded-xl border bg-background p-3"
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    summary: event.target.value,
                  }))
                }
                value={draft.summary}
              />
            </label>
            <div className="mt-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium">Guide content</span>
                {!preview && (
                  <div className="flex gap-1" aria-label="Markdown tools">
                    <Tool
                      label="Heading"
                      onClick={() => insertMarkdown('\n## ')}
                    />
                    <Tool
                      label="Bold"
                      onClick={() => insertMarkdown('**', '**')}
                    />
                    <Tool label="List" onClick={() => insertMarkdown('\n- ')} />
                    <Tool
                      label="Code"
                      onClick={() => insertMarkdown('`', '`')}
                    />
                    <Tool label="Note" onClick={() => insertMarkdown('\n> ')} />
                  </div>
                )}
              </div>
              {preview ? (
                <MarkdownPreview content={draft.content} />
              ) : (
                <textarea
                  aria-label="Guide Markdown content"
                  className="min-h-[420px] w-full rounded-xl border bg-background p-4 font-mono text-sm leading-6"
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      content: event.target.value,
                    }))
                  }
                  ref={editor}
                  value={draft.content}
                />
              )}
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field
                label="Page context IDs"
                hint="Comma-separated, for example calendar, meetings.detail"
                value={draft.context_ids.join(', ')}
                onChange={(value) =>
                  setDraft((current) => ({
                    ...current,
                    context_ids: splitValues(value),
                  }))
                }
              />
              <Field
                label="Related guide slugs"
                hint="Comma-separated"
                value={draft.related_slugs.join(', ')}
                onChange={(value) =>
                  setDraft((current) => ({
                    ...current,
                    related_slugs: splitValues(value),
                  }))
                }
              />
            </div>
            {!isNew && selected && (
              <div className="mt-6 grid gap-5 border-t pt-5 lg:grid-cols-2">
                <section>
                  <h3 className="flex items-center gap-2 font-semibold">
                    <FileClock className="size-4 text-primary" />
                    Version history
                  </h3>
                  <div className="mt-3 space-y-2">
                    {versions.data?.map((version) => (
                      <div
                        className="flex items-center justify-between rounded-lg bg-muted/60 px-3 py-2 text-sm"
                        key={version.id}
                      >
                        <span>Version {version.version}</span>
                        <span className="status-badge">
                          {version.workflow_status}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
                <section>
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="flex items-center gap-2 font-semibold">
                      <ImagePlus className="size-4 text-primary" />
                      Images & attachments
                    </h3>
                    <label className="button-secondary cursor-pointer px-3 py-2 text-xs">
                      Upload
                      <input
                        className="sr-only"
                        onChange={(event) => {
                          const file = event.target.files?.[0]
                          if (file) upload.mutate(file)
                        }}
                        type="file"
                      />
                    </label>
                  </div>
                  <div className="mt-3 space-y-2">
                    {attachments.data?.map((attachment) => (
                      <a
                        className="block truncate rounded-lg bg-muted/60 px-3 py-2 text-sm text-primary hover:underline"
                        href={attachment.url}
                        key={attachment.id}
                      >
                        {attachment.filename}
                      </a>
                    ))}
                    {!attachments.data?.length && (
                      <p className="text-sm text-muted-foreground">
                        No attachments yet.
                      </p>
                    )}
                  </div>
                </section>
              </div>
            )}
            {save.isError && (
              <p className="mt-4 text-sm text-danger" role="alert">
                The guide could not be saved. Review the required fields and try
                again.
              </p>
            )}
          </>
        )}
      </Surface>
    </div>
  )
}

function withoutSlug(draft: HelpArticleDraft): Omit<HelpArticleDraft, 'slug'> {
  const { slug: _, ...body } = draft
  return body
}
function splitValues(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}
function Stat({ value, label }: { value: number; label: string }) {
  return (
    <Surface className="p-3 text-center">
      <strong className="block text-xl">{value}</strong>
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
    </Surface>
  )
}
function Field({
  label,
  value,
  onChange,
  hint,
  disabled = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  hint?: string
  disabled?: boolean
}) {
  return (
    <label className="grid gap-2 text-sm font-medium">
      {label}
      <input
        className="h-11 rounded-xl border bg-background px-3 disabled:opacity-60"
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
      {hint && (
        <span className="text-xs font-normal text-muted-foreground">
          {hint}
        </span>
      )}
    </label>
  )
}
function Tool({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      className="rounded-md border px-2 py-1 text-xs hover:bg-muted"
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  )
}
function MarkdownPreview({ content }: { content: string }) {
  return (
    <div className="min-h-[420px] space-y-3 rounded-xl border bg-background p-5">
      {content.split('\n').map((line, index) =>
        line.startsWith('# ') ? (
          <h1 className="text-2xl font-semibold" key={index}>
            {line.slice(2)}
          </h1>
        ) : line.startsWith('## ') ? (
          <h2 className="pt-3 text-xl font-semibold" key={index}>
            {line.slice(3)}
          </h2>
        ) : line.startsWith('- ') ? (
          <p className="pl-4" key={index}>
            • {line.slice(2)}
          </p>
        ) : line ? (
          <p className="text-muted-foreground" key={index}>
            {line}
          </p>
        ) : (
          <div className="h-1" key={index} />
        ),
      )}
    </div>
  )
}
