import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Clock3, Heart, Search } from 'lucide-react'
import { Fragment, type ReactNode, useMemo, useState } from 'react'

import { helpApi, type HelpArticle } from '@/features/help/api'

type Collection = 'all' | 'favorites' | 'recent'

export function HelpCenterPage() {
  const [search, setSearch] = useState('')
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
  const favorite = useMutation({
    mutationFn: (articleId: string) => helpApi.toggleFavorite(articleId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['help-articles'] }),
  })
  const grouped = useMemo(
    () =>
      (articles.data ?? []).reduce<Record<string, HelpArticle[]>>(
        (result, article) => {
          result[article.category] = [
            ...(result[article.category] ?? []),
            article,
          ]
          return result
        },
        {},
      ),
    [articles.data],
  )
  const active =
    articles.data?.find((article) => article.slug === selected) ??
    articles.data?.[0]
  const toc =
    active?.content
      .split('\n')
      .filter((line) => line.startsWith('## '))
      .map((line) => line.slice(3)) ?? []

  return (
    <div className="mx-auto max-w-[1500px] p-4 sm:p-6">
      <header className="rounded-3xl bg-gradient-to-br from-primary/15 via-card to-card p-6 sm:p-8">
        <p className="text-sm font-semibold text-primary">MeetingHQ Learn</p>
        <h1 className="mt-1 text-3xl font-semibold">Help Center</h1>
        <p className="mt-2 text-muted-foreground">
          Product guidance, administrator documentation, deployment guides,
          release notes, and troubleshooting.
        </p>
        <label className="relative mt-6 block max-w-2xl">
          <Search className="absolute left-4 top-3.5 size-5 text-muted-foreground" />
          <input
            aria-label="Search documentation"
            className="h-12 w-full rounded-2xl border bg-background pl-12 pr-4 shadow-sm"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search MeetingHQ documentation"
            value={search}
          />
        </label>
        <div
          className="mt-4 flex flex-wrap gap-2"
          aria-label="Help collections"
        >
          {(
            [
              ['all', BookOpen, 'All articles'],
              ['favorites', Heart, 'Favorites'],
              ['recent', Clock3, 'Recently viewed'],
            ] as const
          ).map(([key, Icon, label]) => (
            <button
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm ${
                collection === key
                  ? 'bg-primary text-primary-foreground'
                  : 'border bg-background'
              }`}
              key={key}
              onClick={() => setCollection(key)}
              type="button"
            >
              <Icon className="size-4" /> {label}
            </button>
          ))}
        </div>
      </header>
      <div className="mt-6 grid gap-6 lg:grid-cols-[270px_minmax(0,1fr)_220px]">
        <aside className="rounded-2xl border bg-card p-3 lg:self-start">
          {articles.isLoading && (
            <p className="p-4 text-sm text-muted-foreground">Searching…</p>
          )}
          {Object.entries(grouped).map(([category, items]) => (
            <details key={category} open>
              <summary className="cursor-pointer rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {category}
              </summary>
              <div className="space-y-1 pb-3">
                {items?.map((article) => (
                  <button
                    className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                      active?.slug === article.slug
                        ? 'bg-primary/10 font-semibold text-primary'
                        : 'hover:bg-muted'
                    }`}
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
        </aside>
        <main className="min-w-0 rounded-2xl border bg-card p-6 sm:p-9">
          {articles.isError ? (
            <div role="alert" className="text-red-600">
              Documentation could not be loaded.
            </div>
          ) : active ? (
            <>
              <div className="mb-7 border-b pb-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <BookOpen className="size-4" />
                    {active.category} · Version {active.version}
                  </div>
                  <button
                    aria-label="Add article to Help Center favorites"
                    className="rounded-lg border p-2 text-muted-foreground hover:bg-muted hover:text-primary"
                    disabled={favorite.isPending}
                    onClick={() => favorite.mutate(active.id)}
                    title="Favorite inside Help Center"
                    type="button"
                  >
                    <Heart className="size-4" />
                  </button>
                </div>
                <p className="mt-3 text-muted-foreground">{active.summary}</p>
              </div>
              <MarkdownContent content={active.content} />
            </>
          ) : (
            <p className="py-16 text-center text-muted-foreground">
              No documentation matches this collection.
            </p>
          )}
        </main>
        <aside className="hidden rounded-2xl border bg-card p-4 lg:block lg:self-start">
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
          {active?.related_slugs.length ? (
            <>
              <p className="mt-6 text-xs font-semibold uppercase text-muted-foreground">
                Related articles
              </p>
              <div className="mt-2 space-y-1">
                {active.related_slugs.map((slug) => (
                  <button
                    className="block text-left text-sm text-primary hover:underline"
                    key={slug}
                    onClick={() => setSelected(slug)}
                    type="button"
                  >
                    {slug.replaceAll('-', ' ')}
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </aside>
      </div>
    </div>
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
    if (image) {
      blocks.push(
        <img
          alt={image[1]}
          className="max-h-[520px] rounded-xl border object-contain"
          key={index}
          loading="lazy"
          src={image[2]}
        />,
      )
    } else if (!line) blocks.push(<div className="h-1" key={index} />)
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
  const parts = value.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, index) =>
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
