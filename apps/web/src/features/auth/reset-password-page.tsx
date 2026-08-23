import { useState } from 'react'
import { Link, useSearch } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'

import { authApi, ApiError } from '@/features/auth/api'
import { FormField } from '@/features/auth/form-field'

interface Values {
  new_password: string
}

export function ResetPasswordPage() {
  const search = useSearch({ strict: false }) as { token?: string }
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>()
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const submit = handleSubmit(async (values) => {
    if (!search.token) return setError('Reset token is missing')
    try {
      setMessage(
        (await authApi.resetPassword({ token: search.token, ...values }))
          .message,
      )
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Unable to reset password',
      )
    }
  })
  return (
    <section>
      <h2 className="text-3xl font-semibold tracking-tight">
        Choose a new password
      </h2>
      <p className="mt-2 text-muted-foreground">
        Use at least 12 characters with uppercase, lowercase, number, and
        symbol.
      </p>
      <form className="mt-8 space-y-5" onSubmit={submit}>
        {message && (
          <div
            role="status"
            className="rounded-xl bg-emerald-500/10 p-3 text-sm text-emerald-600"
          >
            {message}
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="rounded-xl bg-red-500/10 p-3 text-sm text-red-600"
          >
            {error}
          </div>
        )}
        <FormField
          id="new_password"
          label="New password"
          type="password"
          error={errors.new_password?.message}
          {...register('new_password', {
            required: 'Password is required',
            minLength: { value: 12, message: 'Use at least 12 characters' },
          })}
        />
        <button
          disabled={isSubmitting}
          className="h-11 w-full rounded-xl bg-primary font-medium text-primary-foreground"
          type="submit"
        >
          Reset password
        </button>
      </form>
      {message && (
        <Link
          className="mt-6 block text-center text-sm font-medium text-primary"
          to="/login"
        >
          Continue to sign in
        </Link>
      )}
    </section>
  )
}
