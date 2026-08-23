import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { ApiError, authApi } from '@/features/auth/api'
import { FormField } from '@/features/auth/form-field'

interface Values {
  current_password: string
  new_password: string
  confirm_password: string
}

export function ChangePasswordPage() {
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>()
  const submit = handleSubmit(async (values) => {
    if (values.new_password !== values.confirm_password) {
      setError('Passwords do not match')
      return
    }
    try {
      await authApi.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
        confirm_new_password: values.confirm_password,
      })
      window.location.assign('/')
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Unable to change password',
      )
    }
  })
  return (
    <div className="mx-auto max-w-xl p-6 lg:p-10">
      <section className="rounded-2xl border bg-card p-6 shadow-sm">
        <p className="text-sm font-semibold text-primary">Account security</p>
        <h1 className="mt-1 text-2xl font-semibold">Choose a new password</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Your temporary password must be replaced before continuing.
        </p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          {error && (
            <p
              className="rounded-xl bg-red-500/10 p-3 text-sm text-red-600"
              role="alert"
            >
              {error}
            </p>
          )}
          <FormField
            id="current_password"
            label="Temporary password"
            type="password"
            error={errors.current_password?.message}
            {...register('current_password', {
              required: 'Password is required',
            })}
          />
          <FormField
            id="new_password"
            label="New password"
            type="password"
            error={errors.new_password?.message}
            {...register('new_password', {
              required: 'New password is required',
              minLength: { value: 12, message: 'Use at least 12 characters' },
            })}
          />
          <FormField
            id="confirm_password"
            label="Confirm new password"
            type="password"
            error={errors.confirm_password?.message}
            {...register('confirm_password', {
              required: 'Confirm your password',
            })}
          />
          <button
            className="h-11 w-full rounded-xl bg-primary font-semibold text-primary-foreground disabled:opacity-50"
            disabled={isSubmitting}
            type="submit"
          >
            Update password
          </button>
        </form>
      </section>
    </div>
  )
}
