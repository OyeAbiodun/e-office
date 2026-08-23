import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, 'Password is required'),
  mfa_code: z.string().max(32).optional(),
})

export const registerSchema = z
  .object({
    organization_name: z.string().min(2).max(160),
    organization_slug: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
    workspace_name: z.string().min(2).max(160),
    username: z.string().regex(/^[a-zA-Z0-9_.-]{3,64}$/),
    first_name: z.string().min(1).max(80),
    last_name: z.string().min(1).max(80),
    email: z.string().email(),
    password: z
      .string()
      .min(12)
      .regex(/[a-z]/)
      .regex(/[A-Z]/)
      .regex(/\d/)
      .regex(/[^A-Za-z0-9]/),
    confirm_password: z.string(),
  })
  .refine((value) => value.password === value.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
