export type DateInput = string | number | Date | null | undefined

function isValidDate(date: Date): boolean {
  return !Number.isNaN(date.getTime())
}

export function parseDateInput(value: DateInput): Date | null {
  if (value == null) {
    return null
  }

  if (value instanceof Date) {
    return isValidDate(value) ? value : null
  }

  if (typeof value === 'number') {
    const parsed = new Date(value)
    return isValidDate(parsed) ? parsed : null
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) {
      return null
    }

    const isoDateMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/)
    if (isoDateMatch) {
      const [, year, month, day] = isoDateMatch
      const parsed = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)))
      return isValidDate(parsed) ? parsed : null
    }

    const parsed = new Date(trimmed)
    return isValidDate(parsed) ? parsed : null
  }

  return null
}

const DEFAULT_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
}

export function formatDate(
  value: DateInput,
  options: Intl.DateTimeFormatOptions = DEFAULT_DATE_OPTIONS,
  locale = 'en-US',
): string {
  const parsed = parseDateInput(value)
  if (!parsed) {
    return ''
  }

  const formatter = new Intl.DateTimeFormat(locale, {
    timeZone: 'UTC',
    ...options,
  })

  return formatter.format(parsed)
}

const DEFAULT_DATETIME_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
}

export function formatDateTime(
  value: DateInput,
  options: Intl.DateTimeFormatOptions = DEFAULT_DATETIME_OPTIONS,
  locale = 'en-US',
): string {
  const mergedOptions: Intl.DateTimeFormatOptions = {
    hour12: true,
    ...options,
  }

  return formatDate(value, mergedOptions, locale)
}

export function isSameUtcCalendarDate(a: DateInput, b: DateInput): boolean {
  const first = parseDateInput(a)
  const second = parseDateInput(b)

  if (!first || !second) {
    return false
  }

  return (
    first.getUTCFullYear() === second.getUTCFullYear() &&
    first.getUTCMonth() === second.getUTCMonth() &&
    first.getUTCDate() === second.getUTCDate()
  )
}
