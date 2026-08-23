import { useQuery } from '@tanstack/react-query'
import { UserRound } from 'lucide-react'

import { organizationApi } from '@/features/organizations/api'

export function MembersPage() {
  const members = useQuery({
    queryKey: ['members'],
    queryFn: organizationApi.members,
  })
  return (
    <div className="mx-auto max-w-6xl p-5 sm:p-8">
      <h1 className="text-3xl font-semibold">Members</h1>
      <p className="mt-2 text-muted-foreground">
        People with access to your organization.
      </p>
      <div className="mt-8 overflow-hidden rounded-2xl border bg-card">
        {members.data?.map((member) => (
          <div
            className="flex items-center gap-4 border-b p-4 last:border-0"
            key={member.id}
          >
            <div className="grid size-10 place-items-center rounded-full bg-primary/10 text-primary">
              {member.avatar_url ? (
                <img
                  alt=""
                  className="size-10 rounded-full object-cover"
                  src={member.avatar_url}
                />
              ) : (
                <UserRound className="size-5" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{member.display_name}</p>
              <p className="truncate text-sm text-muted-foreground">
                {member.email}
              </p>
            </div>
            <span className="rounded-full bg-muted px-2.5 py-1 text-xs capitalize">
              {member.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
