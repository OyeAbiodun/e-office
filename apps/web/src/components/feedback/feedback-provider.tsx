import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { type ReactNode, useCallback, useEffect, useState } from 'react'

import {
  ConfirmContext,
  type Confirmation,
  type ConfirmFunction,
} from '@/components/feedback/confirmation'
import {
  feedbackEvent,
  confirmationEvent,
  operationEvent,
  type ConfirmationRequest,
  type FeedbackDetail,
} from '@/components/feedback/events'

interface Toast extends FeedbackDetail {
  id: number
}

const toneIcon = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [operations, setOperations] = useState(0)
  const [confirmation, setConfirmation] = useState<
    (Confirmation & { resolve: (value: boolean) => void }) | null
  >(null)
  useEffect(() => {
    const onFeedback = (event: Event) => {
      const detail = (event as CustomEvent<FeedbackDetail>).detail
      const id = Date.now() + Math.random()
      setToasts((current) => [...current.slice(-3), { ...detail, id }])
      if (!detail.persistent && detail.tone !== 'error')
        window.setTimeout(
          () =>
            setToasts((current) => current.filter((item) => item.id !== id)),
          detail.tone === 'success' ? 9000 : 8500,
        )
    }
    const onOperation = (event: Event) => {
      const active = (event as CustomEvent<{ active: boolean }>).detail.active
      setOperations((current) => Math.max(0, current + (active ? 1 : -1)))
    }
    window.addEventListener(feedbackEvent, onFeedback)
    window.addEventListener(operationEvent, onOperation)
    return () => {
      window.removeEventListener(feedbackEvent, onFeedback)
      window.removeEventListener(operationEvent, onOperation)
    }
  }, [])
  const confirm = useCallback<ConfirmFunction>(
    (options) =>
      new Promise<boolean>((resolve) =>
        setConfirmation({ ...options, resolve }),
      ),
    [],
  )
  useEffect(() => {
    const onConfirmation = (event: Event) => {
      event.preventDefault()
      const request = (event as CustomEvent<ConfirmationRequest>).detail
      setConfirmation({
        title: request.title,
        description: request.description,
        confirmLabel: request.confirmLabel,
        tone: 'danger',
        resolve: request.resolve,
      })
    }
    window.addEventListener(confirmationEvent, onConfirmation)
    return () => window.removeEventListener(confirmationEvent, onConfirmation)
  }, [])
  const finishConfirmation = (answer: boolean) => {
    confirmation?.resolve(answer)
    setConfirmation(null)
  }
  return (
    <ConfirmContext.Provider value={confirm}>
      {operations > 0 && (
        <div
          aria-label="Operation in progress"
          className="fixed inset-x-0 top-0 z-[100] h-1 overflow-hidden bg-primary/15"
          role="progressbar"
        >
          <motion.div
            animate={{ x: ['-40%', '220%'] }}
            className="h-full w-1/3 bg-primary"
            transition={{
              duration: 1.2,
              ease: 'easeInOut',
              repeat: Infinity,
            }}
          />
        </div>
      )}
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed right-4 top-4 z-[110] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2"
      >
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const Icon = toneIcon[toast.tone]
            return (
              <motion.article
                animate={{ opacity: 1, y: 0 }}
                className="pointer-events-auto flex gap-3 rounded-2xl border bg-card p-4 shadow-2xl"
                exit={{ opacity: 0, x: 40 }}
                initial={{ opacity: 0, y: 18 }}
                key={toast.id}
              >
                <Icon
                  className={`mt-0.5 size-5 shrink-0 ${toast.tone === 'error' ? 'text-red-600' : toast.tone === 'warning' ? 'text-amber-600' : toast.tone === 'success' ? 'text-emerald-600' : 'text-primary'}`}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">{toast.title}</p>
                  {toast.description && (
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {toast.description}
                    </p>
                  )}
                  <div className="mt-2 flex items-center gap-3">
                    <time className="text-[10px] text-muted-foreground">
                      {new Date(toast.id).toLocaleTimeString([], {
                        hour: 'numeric',
                        minute: '2-digit',
                      })}
                    </time>
                    {toast.action && (
                      <button
                        className="text-xs font-semibold text-primary"
                        onClick={toast.action.onClick}
                        type="button"
                      >
                        {toast.action.label}
                      </button>
                    )}
                  </div>
                </div>
                <button
                  aria-label="Dismiss notification"
                  className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
                  onClick={() =>
                    setToasts((current) =>
                      current.filter((item) => item.id !== toast.id),
                    )
                  }
                  type="button"
                >
                  <X className="size-4" />
                </button>
              </motion.article>
            )
          })}
        </AnimatePresence>
      </div>
      {confirmation && (
        <div
          aria-labelledby="confirmation-title"
          aria-modal="true"
          className="fixed inset-0 z-[120] grid place-items-center bg-black/55 p-4 backdrop-blur-sm"
          role="dialog"
        >
          <motion.div
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-md rounded-2xl border bg-background p-6 shadow-2xl"
            initial={{ opacity: 0, scale: 0.96 }}
          >
            <div className="grid size-11 place-items-center rounded-xl bg-red-500/10 text-red-600">
              <AlertTriangle className="size-5" />
            </div>
            <h2 className="mt-4 text-xl font-semibold" id="confirmation-title">
              {confirmation.title}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              {confirmation.description}
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                autoFocus
                className="rounded-xl border px-4 py-2.5 text-sm font-semibold"
                onClick={() => finishConfirmation(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className={`rounded-xl px-4 py-2.5 text-sm font-semibold text-white ${confirmation.tone === 'danger' ? 'bg-red-600 hover:bg-red-700' : 'bg-primary'}`}
                onClick={() => finishConfirmation(true)}
                type="button"
              >
                {confirmation.confirmLabel ?? 'Confirm'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}
