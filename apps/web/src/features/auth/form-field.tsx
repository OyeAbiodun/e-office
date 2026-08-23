import type { InputHTMLAttributes } from 'react'

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
}

export function FormField({ label, error, id, ...props }: FormFieldProps) {
  return (
    <label className="block text-sm font-medium" htmlFor={id}>
      {label}
      <input
        aria-invalid={Boolean(error)}
        className="mt-2 h-11 w-full rounded-xl border border-border bg-background px-3 outline-none ring-primary/20 transition focus:border-primary focus:ring-3 aria-invalid:border-red-500"
        id={id}
        {...props}
      />
      {error && (
        <span className="mt-1.5 block text-xs text-red-500">{error}</span>
      )}
    </label>
  )
}
