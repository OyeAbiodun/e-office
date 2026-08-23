import { useSearch } from '@tanstack/react-router'
import { useState } from 'react'

import { apiRequest } from '@/features/auth/api'

export function AcceptInvitationPage() {
  const search = useSearch({ strict: false }) as { token?: string }
  const [form, setForm] = useState({
    username: '',
    first_name: '',
    last_name: '',
    password: '',
  })
  const [message, setMessage] = useState('')
  const accept = async () => {
    if (!search.token) return setMessage('Invitation token is missing')
    await apiRequest('/invitations/accept', {
      method: 'POST',
      body: JSON.stringify({ token: search.token, ...form }),
    })
    setMessage('Invitation accepted. You can now sign in.')
  }
  return (
    <section>
      <h2 className="text-3xl font-semibold">Join the organization</h2>
      <p className="mt-2 text-muted-foreground">
        Complete your profile to accept this invitation.
      </p>
      <div className="mt-8 space-y-4">
        {(['first_name', 'last_name', 'username', 'password'] as const).map(
          (field) => (
            <input
              className="h-11 w-full rounded-xl border bg-background px-3"
              key={field}
              placeholder={field.replace('_', ' ')}
              type={field === 'password' ? 'password' : 'text'}
              value={form[field]}
              onChange={(event) =>
                setForm({ ...form, [field]: event.target.value })
              }
            />
          ),
        )}
        <button
          className="h-11 w-full rounded-xl bg-primary font-medium text-primary-foreground"
          onClick={() => void accept()}
        >
          Accept invitation
        </button>
        {message && <p className="text-sm text-primary">{message}</p>}
      </div>
    </section>
  )
}
