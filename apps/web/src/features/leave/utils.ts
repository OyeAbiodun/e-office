export const formatDay = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(`${value}T12:00:00`))

export const formatDateTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))

export const formatDays = (value: number) =>
  `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} day${Number(value) === 1 ? '' : 's'}`
