const RAW_QUOTE_REGEX = /^['"]+|['"]+$/g;
const ENCODED_QUOTE_REGEX = /^(%22|&quot;)+|(%22|&quot;)+$/gi;
const PROTOCOL_SINGLE_SLASH_REGEX = /^([a-z][a-z0-9+.-]*:\/)([^/])/i;

const stripQuotes = (value: string) => value.replace(RAW_QUOTE_REGEX, '');
const stripEncodedQuotes = (value: string) => value.replace(ENCODED_QUOTE_REGEX, '');

const ensureProtocolDoubleSlash = (value: string) =>
  value.replace(PROTOCOL_SINGLE_SLASH_REGEX, (_match, scheme: string, rest: string) => `${scheme}/${rest}`);

/**
 * Cleans up values that are expected to be URLs but might contain wrapping quotes,
 * percent-encoded quotes, or malformed protocol separators (e.g. `https:/example.com`).
 */
export const cleanUrlLikeInput = (value: unknown): string => {
  const raw = value?.toString?.().trim?.() ?? '';
  if (!raw) {
    return '';
  }

  let cleaned = stripEncodedQuotes(stripQuotes(raw));

  try {
    cleaned = stripEncodedQuotes(stripQuotes(decodeURIComponent(cleaned)));
  } catch (error) {
    // Ignore decoding failures and fall back to the non-decoded value.
    cleaned = stripEncodedQuotes(stripQuotes(cleaned));
  }

  cleaned = ensureProtocolDoubleSlash(cleaned);

  return cleaned.trim();
};

/**
 * Attempts to normalise a value into an absolute HTTP(S) URL. Returns `null` when the
 * value cannot be interpreted as a safe, absolute URL.
 */
export const tryParseHttpUrl = (value: unknown): string | null => {
  const cleaned = cleanUrlLikeInput(value);
  if (!cleaned) {
    return null;
  }

  try {
    const parsed = new URL(cleaned);
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return null;
    }
    return parsed.toString();
  } catch (error) {
    return null;
  }
};
