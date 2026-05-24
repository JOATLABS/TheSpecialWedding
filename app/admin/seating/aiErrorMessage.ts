const DEFAULT_SEATING_AI_ERROR = 'Failed to get AI suggestions';

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}

function messageFromRecord(record: Record<string, unknown>): string | null {
  for (const key of ['message', 'detail', 'error']) {
    const value = nonEmptyString(record[key]);
    if (value) {
      return value;
    }
  }

  return null;
}

export function getSeatingAiErrorMessage(
  error: unknown,
  fallback = DEFAULT_SEATING_AI_ERROR
): string {
  const directMessage = nonEmptyString(error);
  if (directMessage) {
    return directMessage;
  }

  if (error instanceof Error) {
    return nonEmptyString(error.message) ?? fallback;
  }

  if (!error || typeof error !== 'object') {
    return fallback;
  }

  const record = error as Record<string, unknown>;
  const detail = record.detail;

  const detailMessage = nonEmptyString(detail);
  if (detailMessage) {
    return detailMessage;
  }

  if (detail && typeof detail === 'object') {
    const nestedMessage = messageFromRecord(detail as Record<string, unknown>);
    if (nestedMessage) {
      return nestedMessage;
    }
  }

  return messageFromRecord(record) ?? fallback;
}
