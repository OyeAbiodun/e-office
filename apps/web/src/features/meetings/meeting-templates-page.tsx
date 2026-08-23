import { useQuery, useQueryClient } from '@tanstack/react-query'
import { LayoutTemplate, Plus } from 'lucide-react'
import { useState } from 'react'

import { meetingApi } from '@/features/meetings/api'

export function MeetingTemplatesPage() {
  const queryClient = useQueryClient()
  const templates = useQuery({
    queryKey: ['meeting-templates'],
    queryFn: meetingApi.templates,
  })
  const [name, setName] = useState('')
  const create = async () => {
    if (!name.trim()) return
    await meetingApi.createTemplate({
      name,
      default_duration: 30,
      default_visibility: 'members',
      default_agenda: [],
    })
    setName('')
    await queryClient.invalidateQueries({ queryKey: ['meeting-templates'] })
  }
  return (
    <div className="mx-auto max-w-6xl p-5 sm:p-8">
      <p className="text-sm font-medium text-primary">Reusable formats</p>
      <h1 className="mt-2 text-3xl font-semibold">Meeting templates</h1>
      <p className="mt-2 text-muted-foreground">
        Create consistent agendas and defaults for recurring ways of working.
      </p>
      <div className="mt-7 flex max-w-xl gap-2 rounded-2xl border bg-card p-3">
        <input
          aria-label="Template name"
          className="h-11 flex-1 rounded-xl bg-background px-3"
          placeholder="e.g. Weekly planning"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <button
          className="rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground"
          onClick={() => void create()}
        >
          <Plus className="mr-2 inline size-4" />
          Create
        </button>
      </div>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {templates.data?.map((template) => (
          <article
            className="rounded-2xl border bg-card p-5 shadow-sm"
            key={String(template.id)}
          >
            <div className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
              <LayoutTemplate className="size-5" />
            </div>
            <h2 className="mt-5 font-semibold">{String(template.name)}</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {String(template.description ?? 'A customizable meeting format.')}
            </p>
            <p className="mt-5 text-xs font-medium text-primary">
              {String(template.default_duration)} minutes
            </p>
          </article>
        ))}
      </div>
      {!templates.isLoading && templates.data?.length === 0 && (
        <div className="mt-8 rounded-2xl border border-dashed p-12 text-center text-sm text-muted-foreground">
          Create your first template to standardize agendas and outcomes.
        </div>
      )}
    </div>
  )
}
