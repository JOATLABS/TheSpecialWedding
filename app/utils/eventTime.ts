const TWELVE_HOUR_TIME_WITH_MINUTES = /^(0?[1-9]|1[0-2]):([0-5]\d)\s*([AP]M)$/i;
const TWELVE_HOUR_TIME_ON_THE_HOUR = /^(0?[1-9]|1[0-2])\s*([AP]M)$/i;
const TWENTY_FOUR_HOUR_TIME = /^([01]\d|2[0-3]):([0-5]\d)$/;

export const EVENT_TIME_FORMAT_HINT = 'Use a time like 3:00 PM, 3 PM, or 15:00.';

type ParsedEventTime = {
  hours24: number;
  minutes: number;
};

function parseEventTime(value?: string | null): ParsedEventTime | null {
  if (typeof value !== 'string') return null;

  const trimmed = value.trim().replace(/\s+/g, ' ');
  if (!trimmed) return null;

  const twelveHourWithMinutes = trimmed.match(TWELVE_HOUR_TIME_WITH_MINUTES);
  if (twelveHourWithMinutes) {
    let hours = parseInt(twelveHourWithMinutes[1], 10);
    const minutes = parseInt(twelveHourWithMinutes[2], 10);
    const period = twelveHourWithMinutes[3].toUpperCase();

    if (period === 'PM' && hours !== 12) hours += 12;
    if (period === 'AM' && hours === 12) hours = 0;

    return { hours24: hours, minutes };
  }

  const twelveHourOnTheHour = trimmed.match(TWELVE_HOUR_TIME_ON_THE_HOUR);
  if (twelveHourOnTheHour) {
    let hours = parseInt(twelveHourOnTheHour[1], 10);
    const period = twelveHourOnTheHour[2].toUpperCase();

    if (period === 'PM' && hours !== 12) hours += 12;
    if (period === 'AM' && hours === 12) hours = 0;

    return { hours24: hours, minutes: 0 };
  }

  const twentyFourHour = trimmed.match(TWENTY_FOUR_HOUR_TIME);
  if (twentyFourHour) {
    return {
      hours24: parseInt(twentyFourHour[1], 10),
      minutes: parseInt(twentyFourHour[2], 10),
    };
  }

  return null;
}

function formatNormalizedEventTime(hours24: number, minutes: number): string {
  const normalizedHours = hours24 % 12 || 12;
  const period = hours24 >= 12 ? 'PM' : 'AM';
  return `${normalizedHours}:${minutes.toString().padStart(2, '0')} ${period}`;
}

export function getEventTimeValidationMessage(value?: string | null): string | null {
  if (typeof value !== 'string') return null;
  if (!value.trim()) return null;
  return parseEventTime(value) ? null : EVENT_TIME_FORMAT_HINT;
}

export function normalizeEventTimeInput(value?: string | null): string {
  if (typeof value !== 'string') return '';

  const trimmed = value.trim().replace(/\s+/g, ' ');
  if (!trimmed) return '';

  const parsed = parseEventTime(trimmed);
  return parsed ? formatNormalizedEventTime(parsed.hours24, parsed.minutes) : trimmed;
}
