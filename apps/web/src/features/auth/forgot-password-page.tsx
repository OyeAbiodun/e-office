import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'

import { authApi, ApiError } from '@/features/auth/api'
import { FormField } from '@/features/auth/form-field'

interface Values {
  email: string
}

export function ForgotPasswordPage() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>()
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const submit = handleSubmit(async (values) => {
    setError(null)
    try {
      setMessage((await authApi.forgotPassword(values)).message)
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Unable to submit request',
      )
    }
  })
  return (
    <section>
      <h2 className="text-3xl font-semibold tracking-tight">
        Reset your password
      </h2>
      <p className="mt-2 text-muted-foreground">
        We’ll send recovery instructions if the account exists.
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
          id="email"
          label="Work email"
          type="email"
          required
          error={errors.email?.message}
          {...register('email', { required: 'Email is required' })}
        />
        <button
          disabled={isSubmitting}
          className="h-11 w-full rounded-xl bg-primary font-medium text-primary-foreground disabled:opacity-60"
          type="submit"
        >
          Send recovery instructions
        </button>
      </form>
      <Link
        className="mt-6 block text-center text-sm font-medium text-primary"
        to="/login"
      >
        Back to sign in
      </Link>
    </section>
  )
}
