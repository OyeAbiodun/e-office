export type FeedbackTone = 'success' | 'error' | 'warning' | 'info'

export interface FeedbackDetail {
  title: string
  description?: string
  tone: FeedbackTone
  persistent?: boolean
  action?: { label: string; onClick: () => void }
}

export const feedbackEvent = 'meetinghq:feedback'
export const operationEvent = 'meetinghq:operation'
export const confirmationEvent = 'meetinghq:confirmation'

export function notify(detail: FeedbackDetail) {
  window.dispatchEvent(new CustomEvent(feedbackEvent, { detail }))
}

export function operation(active: boolean) {
  window.dispatchEvent(new CustomEvent(operationEvent, { detail: { active } }))
}

export interface ConfirmationRequest {
  title: string
  description: string
  confirmLabel: string
  resolve: (approved: boolean) => void
}

export function confirmDestructiveAction(path: string): Promise<boolean> {
  const normalized = path.toLowerCase()
  const verb = normalized.includes('archive')
    ? 'Archive'
    : normalized.includes('disable')
      ? 'Disable'
      : 'Delete'
  return new Promise<boolean>((resolve) => {
    const handled = window.dispatchEvent(
      new CustomEvent<ConfirmationRequest>(confirmationEvent, {
        cancelable: true,
        detail: {
          title: `${verb} this item?`,
          description:
            verb === 'Delete'
              ? 'This action can remove data for other users and may not be reversible.'
              : `This ${verb.toLowerCase()} action immediately changes availability for other users.`,
          confirmLabel: verb,
          resolve,
        },
      }),
    )
    if (handled) resolve(true)
  })
}
