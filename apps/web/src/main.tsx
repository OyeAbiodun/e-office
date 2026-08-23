import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { queryClient } from '@/app/query-client'
import { router } from '@/app/router'
import { ThemeProvider } from '@/components/theme-provider'
import { FeedbackProvider } from '@/components/feedback/feedback-provider'
import { AuthProvider } from '@/features/auth/auth-context'
import '@/styles.css'

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element was not found')

createRoot(rootElement).render(
  <StrictMode>
    <ThemeProvider>
      <FeedbackProvider>
        <AuthProvider>
          <QueryClientProvider client={queryClient}>
            <RouterProvider router={router} />
          </QueryClientProvider>
        </AuthProvider>
      </FeedbackProvider>
    </ThemeProvider>
  </StrictMode>,
)
