import { useState } from 'react'
import { Link, useSearch } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'

import { authApi, ApiError } from '@/features/auth/api'
import { strongPasswordError } from '@/features/auth/auth-schema'
import { FormField } from '@/features/auth/form-field'

interface Values {
  new_password: string
  confirm_password: string
}

export function ResetPasswordPage() {
  const search = useSearch({ strict: false }) as { token?: string }
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<Values>()
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const submit = handleSubmit(async (values) => {
    if (!search.token) return setError('Reset token is missing')
    try {
      setMessage(
        (
          await authApi.resetPassword({
            token: search.token,
            new_password: values.new_password,
          })
        ).message,
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
        symbol. Reset links expire after 20 minutes and can only be used once.
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
          autoComplete="new-password"
          error={errors.new_password?.message}
          {...register('new_password', {
            required: 'Password is required',
            validate: strongPasswordError,
          })}
        />
        <FormField
          id="confirm_password"
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_password?.message}
          {...register('confirm_password', {
            required: 'Please confirm your password',
            validate: (value) =>
              value === getValues('new_password') || 'Passwords do not match',
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
