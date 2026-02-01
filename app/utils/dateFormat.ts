export type DateInput = string | number | Date | null | undefined

const DATE_ONLY_REGEX = /^(\d{4})-(\d{2})-(\d{2})$/

// Default timezone for the platform (Root Admin)
export const DEFAULT_TIMEZONE = 'America/Chicago'

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

    const isoDateMatch = trimmed.match(DATE_ONLY_REGEX)
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

/**
 * Get timezone abbreviation (e.g., "CST", "EST", "WAT")
 */
export function getTimezoneAbbreviation(timezone: string = DEFAULT_TIMEZONE, date?: Date): string {
  try {
    const testDate = date || new Date()
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      timeZoneName: 'short',
    })
    const parts = formatter.formatToParts(testDate)
    const tzPart = parts.find(p => p.type === 'timeZoneName')
    return tzPart?.value || timezone
  } catch {
    return timezone
  }
}

const DEFAULT_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
}

/**
 * Format a date with optional timezone support
 * @param value - Date input (string, number, Date, null, undefined)
 * @param options - Intl.DateTimeFormatOptions
 * @param locale - Locale string (default: 'en-US')
 * @param timezone - IANA timezone string (default: 'UTC' for backward compatibility)
 */
export function formatDate(
  value: DateInput,
  options: Intl.DateTimeFormatOptions = DEFAULT_DATE_OPTIONS,
  locale = 'en-US',
  timezone = 'UTC',
): string {
  const parsed = parseDateInput(value)
  if (!parsed) {
    return ''
  }

  const formatter = new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
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

/**
 * Format a date with time, optional timezone support
 * @param value - Date input
 * @param options - Intl.DateTimeFormatOptions
 * @param locale - Locale string (default: 'en-US')
 * @param timezone - IANA timezone string (default: 'UTC' for backward compatibility)
 */
export function formatDateTime(
  value: DateInput,
  options: Intl.DateTimeFormatOptions = DEFAULT_DATETIME_OPTIONS,
  locale = 'en-US',
  timezone = 'UTC',
): string {
  const mergedOptions: Intl.DateTimeFormatOptions = {
    hour12: true,
    ...options,
  }

  return formatDate(value, mergedOptions, locale, timezone)
}

/**
 * Format a date/time with timezone abbreviation suffix
 * Example: "Jan 30, 2026 at 3:00 PM CST"
 * @param value - Date input
 * @param timezone - IANA timezone string
 * @param options - Optional Intl.DateTimeFormatOptions
 * @param locale - Locale string (default: 'en-US')
 */
export function formatDateTimeWithTz(
  value: DateInput,
  timezone: string = DEFAULT_TIMEZONE,
  options: Intl.DateTimeFormatOptions = DEFAULT_DATETIME_OPTIONS,
  locale = 'en-US',
): string {
  const parsed = parseDateInput(value)
  if (!parsed) {
    return ''
  }

  const formatted = formatDateTime(value, options, locale, timezone)
  const tzAbbrev = getTimezoneAbbreviation(timezone, parsed)

  return `${formatted} ${tzAbbrev}`
}

/**
 * Format a date (no time) with timezone abbreviation suffix
 * Example: "January 30, 2026 CST"
 * @param value - Date input
 * @param timezone - IANA timezone string
 * @param options - Optional Intl.DateTimeFormatOptions
 * @param locale - Locale string (default: 'en-US')
 */
export function formatDateWithTz(
  value: DateInput,
  timezone: string = DEFAULT_TIMEZONE,
  options: Intl.DateTimeFormatOptions = DEFAULT_DATE_OPTIONS,
  locale = 'en-US',
): string {
  const parsed = parseDateInput(value)
  if (!parsed) {
    return ''
  }

  const formatted = formatDate(value, options, locale, timezone)
  const tzAbbrev = getTimezoneAbbreviation(timezone, parsed)

  return `${formatted} ${tzAbbrev}`
}

/**
 * Format timestamp for admin displays (with timezone indicator)
 * This is the primary function for admin dashboard timestamps
 * @param value - Date input
 * @param timezone - IANA timezone string (planner's timezone or DEFAULT_TIMEZONE)
 */
export function formatAdminTimestamp(
  value: DateInput,
  timezone: string = DEFAULT_TIMEZONE,
): string {
  return formatDateTimeWithTz(value, timezone, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format date for display in lists/tables (shorter format with timezone)
 * Example: "Jan 30, 2026, 3:00 PM CST"
 */
export function formatListTimestamp(
  value: DateInput,
  timezone: string = DEFAULT_TIMEZONE,
): string {
  return formatDateTimeWithTz(value, timezone, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format date only (no time) for admin displays
 * Example: "Jan 30, 2026"
 */
export function formatAdminDate(
  value: DateInput,
  timezone: string = DEFAULT_TIMEZONE,
): string {
  return formatDate(value, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }, 'en-US', timezone)
}

export function endOfLocalDay(value: DateInput): Date | null {
  if (value == null) {
    return null
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) {
      return null
    }

    const isoDateMatch = trimmed.match(DATE_ONLY_REGEX)
    if (isoDateMatch) {
      const [, year, month, day] = isoDateMatch
      const endOfDay = new Date(
        Number(year),
        Number(month) - 1,
        Number(day),
        23,
        59,
        59,
        999,
      )

      return isValidDate(endOfDay) ? endOfDay : null
    }
  }

  const parsed = parseDateInput(value)
  if (!parsed) {
    return null
  }

  return parsed
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

export function isSameLocalCalendarDate(a: DateInput, b: DateInput): boolean {
  const first = parseDateInput(a)
  const second = parseDateInput(b)

  if (!first || !second) {
    return false
  }

  return (
    first.getFullYear() === second.getFullYear() &&
    first.getMonth() === second.getMonth() &&
    first.getDate() === second.getDate()
  )
}
