import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from '@tanstack/react-router'
import { LoaderCircle } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { ApiError } from '@/features/auth/api'
import { useAuth } from '@/features/auth/auth-store'
import { FormField } from '@/features/auth/form-field'
import { loginSchema, type LoginValues } from '@/features/auth/auth-schema'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [mfaRequired, setMfaRequired] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  const submit = handleSubmit(async (values) => {
    setError(null)
    try {
      const user = await login(values)
      await navigate({
        to: user.force_password_change ? '/change-password' : '/',
      })
    } catch (caught) {
      const message =
        caught instanceof ApiError ? caught.message : 'Unable to sign in'
      if (message.toLowerCase().includes('multi-factor')) setMfaRequired(true)
      setError(message)
    }
  })

  return (
    <section>
      <h2 className="text-3xl font-semibold tracking-tight">Welcome back</h2>
      <p className="mt-2 text-muted-foreground">
        Sign in to your MeetingHQ workspace.
      </p>
      <form className="mt-8 space-y-5" onSubmit={submit}>
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
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <FormField
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register('password')}
        />
        {mfaRequired && (
          <FormField
            id="mfa_code"
            label="Verification code"
            type="text"
            autoComplete="one-time-code"
            error={errors.mfa_code?.message}
            {...register('mfa_code')}
          />
        )}
        <div className="text-right">
          <Link
            className="text-sm font-medium text-primary hover:underline"
            to="/forgot-password"
          >
            Forgot password?
          </Link>
        </div>
        <button
          disabled={isSubmitting}
          className="flex h-11 w-full items-center justify-center rounded-xl bg-primary font-medium text-primary-foreground disabled:opacity-60"
          type="submit"
        >
          {isSubmitting ? (
            <LoaderCircle className="size-5 animate-spin" />
          ) : (
            'Sign in'
          )}
        </button>
      </form>
    </section>
  )
}
