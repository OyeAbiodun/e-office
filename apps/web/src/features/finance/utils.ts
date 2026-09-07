export const label = (value: string) =>
  value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())

export const voucherStatuses = [
  'draft',
  'submitted',
  'returned',
  'rejected',
  'approved',
  'partially_disbursed',
  'completed',
]
