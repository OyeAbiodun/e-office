import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from '@tanstack/react-router'
import { LoaderCircle } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { ApiError } from '@/features/auth/api'
import { useAuth } from '@/features/auth/auth-store'
import {
  registerSchema,
  type RegisterValues,
} from '@/features/auth/auth-schema'
import { FormField } from '@/features/auth/form-field'

export function RegisterPage() {
  const { register: createAccount } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) })
  const submit = handleSubmit(async ({ confirm_password, ...values }) => {
    void confirm_password
    setError(null)
    try {
      await createAccount(values)
      await navigate({ to: '/' })
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Unable to create organization',
      )
    }
  })
  return (
    <section>
      <h2 className="text-3xl font-semibold tracking-tight">
        Create your workspace
      </h2>
      <p className="mt-2 text-muted-foreground">
        Set up your organization and administrator account.
      </p>
      <form className="mt-7 grid gap-4 sm:grid-cols-2" onSubmit={submit}>
        {error && (
          <div
            role="alert"
            className="col-span-full rounded-xl bg-red-500/10 p-3 text-sm text-red-600"
          >
            {error}
          </div>
        )}
        <div className="sm:col-span-2">
          <FormField
            id="organization_name"
            label="Organization name"
            error={errors.organization_name?.message}
            {...register('organization_name')}
          />
        </div>
        <FormField
          id="organization_slug"
          label="Organization slug"
          error={errors.organization_slug?.message}
          {...register('organization_slug')}
        />
        <FormField
          id="workspace_name"
          label="Workspace name"
          error={errors.workspace_name?.message}
          {...register('workspace_name')}
        />
        <FormField
          id="first_name"
          label="First name"
          error={errors.first_name?.message}
          {...register('first_name')}
        />
        <FormField
          id="last_name"
          label="Last name"
          error={errors.last_name?.message}
          {...register('last_name')}
        />
        <FormField
          id="username"
          label="Username"
          error={errors.username?.message}
          {...register('username')}
        />
        <FormField
          id="email"
          label="Work email"
          type="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <FormField
          id="password"
          label="Password"
          type="password"
          error={errors.password?.message}
          {...register('password')}
        />
        <FormField
          id="confirm_password"
          label="Confirm password"
          type="password"
          error={errors.confirm_password?.message}
          {...register('confirm_password')}
        />
        <button
          disabled={isSubmitting}
          className="col-span-full flex h-11 items-center justify-center rounded-xl bg-primary font-medium text-primary-foreground disabled:opacity-60"
          type="submit"
        >
          {isSubmitting ? (
            <LoaderCircle className="size-5 animate-spin" />
          ) : (
            'Create organization'
          )}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link className="font-medium text-primary" to="/login">
          Sign in
        </Link>
      </p>
    </section>
  )
}
