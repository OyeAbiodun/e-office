import path from 'node:path'
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

const currentDirectory = path.dirname(fileURLToPath(import.meta.url))
const repositoryRoot = path.resolve(currentDirectory, '../..')

export default defineConfig(({ mode }) => {
  // The repository owns local runtime configuration. Without this, Vite is
  // started from apps/web and silently misses the root VITE_API_URL setting.
  const env = loadEnv(mode, repositoryRoot, '')
  const configuredApiUrl = env.VITE_API_URL?.trim()
  const apiOrigin = configuredApiUrl ? new URL(configuredApiUrl).origin : null

  return {
    envDir: repositoryRoot,
    plugins: [react(), tailwindcss()],
    server: apiOrigin
      ? {
          // Retain a same-origin development fallback for already-open tabs
          // whose module graph was loaded before VITE_API_URL was available.
          proxy: { '/api': { target: apiOrigin, changeOrigin: true } },
        }
      : undefined,
    resolve: {
      alias: {
        '@': path.resolve(currentDirectory, './src'),
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            router: ['@tanstack/react-router', '@tanstack/react-query'],
            motion: ['framer-motion'],
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      globals: true,
      css: true,
      exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    },
  }
})
