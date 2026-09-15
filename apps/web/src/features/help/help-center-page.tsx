import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BookOpen,
  BriefcaseBusiness,
  Clock3,
  GraduationCap,
  Heart,
  LifeBuoy,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Fragment, type ReactNode, useMemo, useState } from 'react'

import {
  EmptyState,
  ErrorState,
  LoadingState,
  Page,
  PageHeader,
  Surface,
} from '@/components/page'
import { useAuth } from '@/features/auth/auth-store'
import {
  helpApi,
  type HelpArticle,
  type SupportRequest,
} from '@/features/help/api'

type Collection = 'all' | 'favorites' | 'recent'
type View = 'learn' | 'support'
const categoryCards = [
  [
    'Getting Started',
    Sparkles,
    'Set up your workspace and learn the essentials.',
  ],
  [
    'User Handbook',
    BriefcaseBusiness,
    'Guidance for daily work across OfficeFlow.',
  ],
  [
    'Administrator Handbook',
    ShieldCheck,
    'Manage people, access, operations, and policy.',
  ],
  [
    'Troubleshooting',
    LifeBuoy,
    'Resolve common issues and recover your workflow.',
  ],
  [
    'Deployment Guides',
    Settings2,
    'Install, configure, back up, and operate OfficeFlow.',
  ],
  [
    'Release Notes',
    GraduationCap,
    'Discover improvements and important changes.',
  ],
] as const

export function HelpCenterPage() {
  const { user } = useAuth()
  const [view, setView] = useState<View>('learn')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [selected, setSelected] = useState(
    () => new URLSearchParams(window.location.search).get('article') ?? '',
  )
  const [collection, setCollection] = useState<Collection>('all')
  const queryClient = useQueryClient()
  const articles = useQuery({
    queryKey: ['help-articles', collection, search],
    queryFn: async () => {
      const rows =
        collection === 'favorites'
          ? await helpApi.favorites()
          : collection === 'recent'
            ? await helpApi.recent()
            : await helpApi.articles(search)
      if (!search || collection === 'all') return rows
      const term = search.toLowerCase()
      return rows.filter((row) =>
        `${row.title} ${row.summary} ${row.content}`
          .toLowerCase()
          .includes(term),
      )
    },
  })
  const filtered = useMemo(
    () =>
      (articles.data ?? []).filter(
        (article) => !category || article.category === category,
      ),
    [articles.data, category],
  )
  const grouped = useMemo(
    () =>
      filtered.reduce<Record<string, HelpArticle[]>>((result, article) => {
        result[article.category] = [
          ...(result[article.category] ?? []),
          article,
        ]
        return result
      }, {}),
    [filtered],
  )
  const active =
    filtered.find((article) => article.slug === selected) ?? filtered[0]
  const favorite = useMutation({
    mutationFn: helpApi.toggleFavorite,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['help-articles'] }),
  })

  return (
    <Page>
      <PageHeader
        eyebrow="Knowledge and support"
        title="Help & Support"
        description="Learn OfficeFlow, follow role-aware guidance, or raise a support request with the right context."
        actions={
          <div
            className="flex rounded-xl border bg-card p-1"
            role="tablist"
            aria-label="Help views"
          >
            {(['learn', 'support'] as const).map((item) => (
              <button
                aria-selected={view === item}
                className={
                  view === item
                    ? 'button-primary px-4 py-2'
                    : 'button-ghost px-4 py-2'
                }
                key={item}
                onClick={() => setView(item)}
                role="tab"
                type="button"
              >
                {item === 'learn' ? 'Learn' : 'Get support'}
              </button>
            ))}
          </div>
        }
      />
      {view === 'support' ? (
        <SupportWorkspace />
      ) : (
        <>
          <Surface className="overflow-hidden bg-gradient-to-br from-primary/10 via-card to-card p-6 sm:p-8">
            <p className="max-w-2xl text-sm text-muted-foreground">
              Welcome {user?.first_name}. Search step-by-step guidance or choose
              a learning path for your role.
            </p>
            <label className="relative mt-5 block max-w-3xl">
              <Search className="absolute left-4 top-3.5 size-5 text-muted-foreground" />
              <input
                aria-label="Search OfficeFlow help"
                className="h-12 w-full rounded-xl border bg-background pl-12 pr-4 shadow-sm"
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search features, workflows, setup, or troubleshooting"
                value={search}
              />
            </label>
            <div
              className="mt-4 flex flex-wrap gap-2"
              aria-label="Help collections"
            >
              {(
                [
                  ['all', BookOpen, 'All guides'],
                  ['favorites', Heart, 'Favorites'],
                  ['recent', Clock3, 'Recently viewed'],
                ] as const
              ).map(([key, Icon, label]) => (
                <button
                  className={
                    collection === key
                      ? 'button-primary px-3 py-2'
                      : 'button-secondary px-3 py-2'
                  }
                  key={key}
                  onClick={() => setCollection(key)}
                  type="button"
                >
                  <Icon className="size-4" /> {label}
                </button>
              ))}
            </div>
          </Surface>
          {!search && collection === 'all' && (
            <section
              className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
              aria-label="Browse by category"
            >
              {categoryCards.map(([label, Icon, copy]) => (
                <button
                  className={`surface flex items-start gap-4 p-5 text-left transition hover:-translate-y-0.5 hover:border-primary/40 ${category === label ? 'border-primary bg-primary/5' : ''}`}
                  key={label}
                  onClick={() =>
                    setCategory((current) => (current === label ? '' : label))
                  }
                  type="button"
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                    <Icon className="size-5" />
                  </span>
                  <span>
                    <strong className="block">{label}</strong>
                    <span className="mt-1 block text-sm text-muted-foreground">
                      {copy}
                    </span>
                  </span>
                </button>
              ))}
            </section>
          )}
          <div className="grid gap-5 lg:grid-cols-[270px_minmax(0,1fr)] xl:grid-cols-[270px_minmax(0,1fr)_220px]">
            <Surface className="p-3 lg:self-start">
              {articles.isLoading && (
                <LoadingState label="Searching the knowledge base" />
              )}
              {Object.entries(grouped).map(([group, items]) => (
                <details key={group} open>
                  <summary className="cursor-pointer rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {group}
                  </summary>
                  <div className="space-y-1 pb-3">
                    {items.map((article) => (
                      <button
                        className={`w-full rounded-lg px-3 py-2 text-left text-sm ${active?.slug === article.slug ? 'bg-primary/10 font-semibold text-primary' : 'hover:bg-muted'}`}
                        key={article.id}
                        onClick={() => setSelected(article.slug)}
                        type="button"
                      >
                        {article.title}
                      </button>
                    ))}
                  </div>
                </details>
              ))}
            </Surface>
            <Surface as="main" className="min-w-0 p-6 sm:p-9">
              {articles.isError ? (
                <ErrorState
                  title="Help is temporarily unavailable"
                  description="We could not load the knowledge base."
                />
              ) : active ? (
                <>
                  <div className="mb-7 border-b pb-6">
                    <div className="flex items-start justify-between gap-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                        {active.category} · Version {active.version}
                      </p>
                      <button
                        aria-label="Add guide to favorites"
                        className="button-ghost p-2"
                        disabled={favorite.isPending}
                        onClick={() => favorite.mutate(active.id)}
                        type="button"
                      >
                        <Heart className="size-4" />
                      </button>
                    </div>
                    <p className="mt-3 text-muted-foreground">
                      {active.summary}
                    </p>
                  </div>
                  <MarkdownContent content={active.content} />
                </>
              ) : (
                <EmptyState
                  title="No guides found"
                  description="Try a broader search or clear the selected category."
                  action={
                    <button
                      className="button-secondary"
                      onClick={() => {
                        setSearch('')
                        setCategory('')
                      }}
                      type="button"
                    >
                      Clear filters
                    </button>
                  }
                />
              )}
            </Surface>
            <ArticleOutline article={active} onSelect={setSelected} />
          </div>
        </>
      )}
    </Page>
  )
}

function SupportWorkspace() {
  const queryClient = useQueryClient()
  const [created, setCreated] = useState<SupportRequest | null>(null)
  const requests = useQuery({
    queryKey: ['support-requests'],
    queryFn: helpApi.supportRequests,
  })
  const create = useMutation({
    mutationFn: helpApi.createSupportRequest,
    onSuccess: (request) => {
      setCreated(request)
      queryClient.invalidateQueries({ queryKey: ['support-requests'] })
    },
  })
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Surface className="p-6 sm:p-8">
        <p className="page-eyebrow">Contact support</p>
        <h2 className="mt-1 text-2xl font-semibold">How can we help?</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Describe the outcome you need. OfficeFlow includes the current page
          and safe browser context—never passwords or form values.
        </p>
        {created && (
          <div
            className="mt-5 rounded-xl border border-success/30 bg-success/10 p-4 text-sm text-success"
            role="status"
          >
            Request <strong>{created.reference}</strong> was created. You can
            track it in your request history.
          </div>
        )}
        <form
          className="mt-6 grid gap-5"
          onSubmit={(event) => {
            event.preventDefault()
            const form = new FormData(event.currentTarget)
            create.mutate({
              request_type: String(
                form.get('request_type'),
              ) as SupportRequest['request_type'],
              priority: String(
                form.get('priority'),
              ) as SupportRequest['priority'],
              subject: String(form.get('subject')),
              description: String(form.get('description')),
              page_url: window.location.href,
              module: 'help',
              diagnostics: {
                route: window.location.pathname,
                viewport: `${window.innerWidth}x${window.innerHeight}`,
                browser: navigator.userAgent.slice(0, 240),
              },
            })
            event.currentTarget.reset()
          }}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField
              label="Request type"
              name="request_type"
              options={[
                ['help', 'How-to help'],
                ['issue', 'Report an issue'],
                ['feature', 'Suggest an improvement'],
                ['administration', 'Administration help'],
              ]}
            />
            <SelectField
              label="Priority"
              name="priority"
              options={[
                ['normal', 'Normal'],
                ['low', 'Low'],
                ['high', 'High'],
                ['urgent', 'Urgent — work blocked'],
              ]}
            />
          </div>
          <label className="grid gap-2 text-sm font-medium">
            Subject
            <input
              className="h-11 rounded-xl border bg-background px-3"
              minLength={4}
              name="subject"
              required
            />
          </label>
          <label className="grid gap-2 text-sm font-medium">
            What happened, and what did you expect?
            <textarea
              className="min-h-36 rounded-xl border bg-background p-3"
              minLength={10}
              name="description"
              required
            />
          </label>
          {create.isError && (
            <p className="text-sm text-danger" role="alert">
              Your request could not be submitted. Check the details and try
              again.
            </p>
          )}
          <button
            className="button-primary justify-self-start"
            disabled={create.isPending}
            type="submit"
          >
            <Send className="size-4" />
            {create.isPending ? 'Submitting…' : 'Submit request'}
          </button>
        </form>
      </Surface>
      <Surface className="p-5 xl:self-start">
        <h2 className="font-semibold">Request history</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Recent support activity visible to you.
        </p>
        <div className="mt-4 space-y-3">
          {requests.isLoading && <LoadingState label="Loading requests" />}
          {requests.data?.map((request) => (
            <article className="rounded-xl border p-4" key={request.id}>
              <div className="flex items-center justify-between gap-3">
                <strong className="text-sm">{request.reference}</strong>
                <span className="status-badge">{request.status}</span>
              </div>
              <p className="mt-2 text-sm font-medium">{request.subject}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {new Date(request.created_at).toLocaleString()}
              </p>
            </article>
          ))}
          {!requests.isLoading && !requests.data?.length && (
            <EmptyState
              title="No support requests"
              description="Requests you submit will appear here."
            />
          )}
        </div>
      </Surface>
    </div>
  )
}

function SelectField({
  label,
  name,
  options,
}: {
  label: string
  name: string
  options: readonly (readonly [string, string])[]
}) {
  return (
    <label className="grid gap-2 text-sm font-medium">
      {label}
      <select className="h-11 rounded-xl border bg-background px-3" name={name}>
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </label>
  )
}
function ArticleOutline({
  article,
  onSelect,
}: {
  article?: HelpArticle
  onSelect: (slug: string) => void
}) {
  const toc =
    article?.content
      .split('\n')
      .filter((line) => line.startsWith('## '))
      .map((line) => line.slice(3)) ?? []
  return (
    <Surface as="aside" className="hidden p-4 xl:block xl:self-start">
      <p className="text-xs font-semibold uppercase text-muted-foreground">
        On this page
      </p>
      <ol className="mt-3 space-y-2">
        {toc.map((heading) => (
          <li className="text-sm text-muted-foreground" key={heading}>
            {heading}
          </li>
        ))}
      </ol>
      {article?.related_slugs.length ? (
        <>
          <p className="mt-6 text-xs font-semibold uppercase text-muted-foreground">
            Related guides
          </p>
          {article.related_slugs.map((slug) => (
            <button
              className="mt-2 block text-left text-sm capitalize text-primary hover:underline"
              key={slug}
              onClick={() => onSelect(slug)}
              type="button"
            >
              {slug.replaceAll('-', ' ')}
            </button>
          ))}
        </>
      ) : null}
    </Surface>
  )
}
function MarkdownContent({ content }: { content: string }) {
  const blocks: ReactNode[] = []
  let code: string[] = []
  let inCode = false
  content.split('\n').forEach((line, index) => {
    if (line.startsWith('```')) {
      if (inCode) {
        blocks.push(
          <pre
            className="overflow-x-auto rounded-xl bg-slate-950 p-4 text-sm text-slate-100"
            key={`code-${index}`}
          >
            <code>{code.join('\n')}</code>
          </pre>,
        )
        code = []
      }
      inCode = !inCode
      return
    }
    if (inCode) {
      code.push(line)
      return
    }
    const image = /^!\[([^\]]*)\]\(([^)]+)\)$/.exec(line)
    if (image)
      blocks.push(
        <img
          alt={image[1]}
          className="max-h-[520px] rounded-xl border object-contain"
          key={index}
          loading="lazy"
          src={image[2]}
        />,
      )
    else if (!line) blocks.push(<div className="h-1" key={index} />)
    else if (line.startsWith('# '))
      blocks.push(
        <h1 className="text-3xl font-semibold" key={index}>
          {line.slice(2)}
        </h1>,
      )
    else if (line.startsWith('## '))
      blocks.push(
        <h2 className="pt-4 text-xl font-semibold" key={index}>
          {line.slice(3)}
        </h2>,
      )
    else if (line.startsWith('### '))
      blocks.push(
        <h3 className="pt-3 font-semibold" key={index}>
          {line.slice(4)}
        </h3>,
      )
    else if (line.startsWith('- '))
      blocks.push(
        <p className="pl-4 text-muted-foreground" key={index}>
          • {line.slice(2)}
        </p>,
      )
    else if (/^\d+\. /.test(line))
      blocks.push(
        <p className="pl-4 text-muted-foreground" key={index}>
          {line}
        </p>,
      )
    else if (line.startsWith('> '))
      blocks.push(
        <blockquote
          className="border-l-4 border-primary bg-primary/5 p-4 text-sm"
          key={index}
        >
          {line.slice(2)}
        </blockquote>,
      )
    else
      blocks.push(
        <p className="text-muted-foreground" key={index}>
          {renderInline(line)}
        </p>,
      )
  })
  return <article className="space-y-4 leading-7">{blocks}</article>
}
function renderInline(value: string) {
  return value.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) =>
    part.startsWith('**') ? (
      <strong className="text-foreground" key={index}>
        {part.slice(2, -2)}
      </strong>
    ) : part.startsWith('`') ? (
      <code
        className="rounded bg-muted px-1.5 py-0.5 text-sm text-foreground"
        key={index}
      >
        {part.slice(1, -1)}
      </code>
    ) : (
      <Fragment key={index}>{part}</Fragment>
    ),
  )
}
