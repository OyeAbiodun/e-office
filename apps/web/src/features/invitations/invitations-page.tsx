import { useQuery, useQueryClient } from '@tanstack/react-query'
import { MailPlus } from 'lucide-react'
import { useState } from 'react'

import { organizationApi } from '@/features/organizations/api'

export function InvitationsPage() {
  const queryClient = useQueryClient()
  const invitations = useQuery({
    queryKey: ['invitations'],
    queryFn: organizationApi.invitations,
  })
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('Member')
  const invite = async () => {
    await organizationApi.invite({ email, role_name: role })
    setEmail('')
    await queryClient.invalidateQueries({ queryKey: ['invitations'] })
  }
  return (
    <div className="mx-auto max-w-5xl p-5 sm:p-8">
      <h1 className="text-3xl font-semibold">Invitations</h1>
      <p className="mt-2 text-muted-foreground">
        Invite people and track pending access.
      </p>
      <div className="mt-6 grid gap-3 rounded-2xl border bg-card p-5 sm:grid-cols-[1fr_180px_auto]">
        <input
          className="h-11 rounded-xl border bg-background px-3"
          placeholder="colleague@company.com"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <select
          className="h-11 rounded-xl border bg-background px-3"
          value={role}
          onChange={(event) => setRole(event.target.value)}
        >
          <option>Member</option>
          <option>Manager</option>
          <option>Guest</option>
        </select>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-primary px-5 text-primary-foreground"
          onClick={() => void invite()}
        >
          <MailPlus className="size-4" />
          Invite
        </button>
      </div>
      <div className="mt-8 overflow-hidden rounded-2xl border bg-card">
        {invitations.data?.length === 0 && (
          <p className="p-8 text-center text-muted-foreground">
            No invitations yet.
          </p>
        )}
        {invitations.data?.map((invitation) => (
          <div
            className="flex items-center border-b p-4 last:border-0"
            key={invitation.id}
          >
            <div className="flex-1">
              <p className="font-medium">{invitation.email}</p>
              <p className="text-sm text-muted-foreground">
                {invitation.role_name} · expires{' '}
                {new Date(invitation.expires_at).toLocaleDateString()}
              </p>
            </div>
            <span className="rounded-full bg-muted px-2.5 py-1 text-xs capitalize">
              {invitation.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
