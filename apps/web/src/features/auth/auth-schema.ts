import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, 'Password is required'),
  mfa_code: z.string().max(32).optional(),
})

export const strongPasswordSchema = z
  .string()
  .min(12, 'Use at least 12 characters')
  .max(128, 'Use no more than 128 characters')
  .regex(/[a-z]/, 'Include a lowercase letter')
  .regex(/[A-Z]/, 'Include an uppercase letter')
  .regex(/\d/, 'Include a number')
  .regex(/[^A-Za-z0-9]/, 'Include a symbol')

export function strongPasswordError(value: string): true | string {
  const result = strongPasswordSchema.safeParse(value)
  return result.success
    ? true
    : (result.error.issues[0]?.message ?? 'Invalid password')
}

export const registerSchema = z
  .object({
    organization_name: z.string().min(2).max(160),
    organization_slug: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
    workspace_name: z.string().min(2).max(160),
    username: z.string().regex(/^[a-zA-Z0-9_.-]{3,64}$/),
    first_name: z.string().min(1).max(80),
    last_name: z.string().min(1).max(80),
    email: z.string().email(),
    password: strongPasswordSchema,
    confirm_password: z.string(),
  })
  .refine((value) => value.password === value.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
