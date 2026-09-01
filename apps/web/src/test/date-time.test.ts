import { toLocalDateTimeInput, toZonedDateTimeInput } from '@/lib/date-time'

test('datetime-local values round trip without shifting the instant', () => {
  const instant = new Date('2026-08-25T20:00:00.000Z')
  const localValue = toLocalDateTimeInput(instant)

  expect(new Date(localValue).getTime()).toBe(instant.getTime())
})

test('timezone-aware datetime inputs preserve the selected wall time', () => {
  const instant = '2026-08-25T20:00:00.000Z'

  expect(toZonedDateTimeInput(instant, 'UTC')).toBe('2026-08-25T20:00')
  expect(toZonedDateTimeInput(instant, 'America/Chicago')).toBe(
    '2026-08-25T15:00',
  )
})
