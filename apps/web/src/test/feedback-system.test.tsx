import { act, fireEvent, render, screen } from '@testing-library/react'

import { useConfirmation } from '@/components/feedback/confirmation'
import {
  confirmDestructiveAction,
  notify,
  operation,
} from '@/components/feedback/events'
import { FeedbackProvider } from '@/components/feedback/feedback-provider'

function Harness() {
  const confirm = useConfirmation()
  return (
    <>
      <button
        onClick={() =>
          notify({
            tone: 'success',
            title: 'Workspace saved',
            description: 'Changes are live.',
          })
        }
        type="button"
      >
        Notify
      </button>
      <button
        onClick={() =>
          void confirm({
            title: 'Delete workspace?',
            description: 'This cannot be undone.',
            tone: 'danger',
          })
        }
        type="button"
      >
        Delete
      </button>
      <button onClick={() => operation(true)} type="button">
        Start
      </button>
    </>
  )
}

test('renders accessible global feedback and confirmation states', async () => {
  render(
    <FeedbackProvider>
      <Harness />
    </FeedbackProvider>,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Notify' }))
  expect(await screen.findByText('Workspace saved')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
  expect(
    screen.getByRole('dialog', { name: 'Delete workspace?' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()

  fireEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(
    screen.getByRole('progressbar', { name: 'Operation in progress' }),
  ).toBeInTheDocument()
})

test('intercepts destructive API actions with the shared confirmation dialog', async () => {
  render(
    <FeedbackProvider>
      <p>Application</p>
    </FeedbackProvider>,
  )

  let decision: Promise<boolean> | undefined
  act(() => {
    decision = confirmDestructiveAction('/users/user-1')
  })
  expect(
    await screen.findByRole('dialog', { name: 'Delete this item?' }),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  await expect(decision).resolves.toBe(false)
})
