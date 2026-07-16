export const UMAMI_BEFORE_SEND_HANDLER_NAME = '__tswUmamiBeforeSend';

const SENSITIVE_PATH_ROOT = '/domain-instructions';
const URL_PARSE_BASE = 'https://privacy.invalid';

export type UmamiAnalyticsPayload = Record<string, unknown>;

export function isAnalyticsSensitivePath(pathname: string | null | undefined): boolean {
  return (
    pathname === SENSITIVE_PATH_ROOT ||
    Boolean(pathname?.startsWith(`${SENSITIVE_PATH_ROOT}/`))
  );
}

export function filterSensitiveUmamiPayload<T extends UmamiAnalyticsPayload>(
  payload: T,
): T | false {
  for (const field of ['url', 'referrer'] as const) {
    const value = payload[field];
    if (typeof value !== 'string' || value.length === 0) {
      continue;
    }

    try {
      const pathname = new URL(value, URL_PARSE_BASE).pathname;
      if (isAnalyticsSensitivePath(pathname)) {
        return false;
      }
    } catch {
      // A malformed URL cannot be proven safe, so fail closed rather than risk
      // forwarding a secret-bearing value to analytics.
      return false;
    }
  }

  return payload;
}

/**
 * Umami resolves `data-before-send` by a function name on `window`. This
 * guard is installed in the root document before either tracker loader runs,
 * so SPA navigation from a tracked page cannot submit an instruction token.
 */
export const UMAMI_PRIVACY_GUARD_SCRIPT = `(() => {
  const sensitiveRoot = ${JSON.stringify(SENSITIVE_PATH_ROOT)};
  const handlerName = ${JSON.stringify(UMAMI_BEFORE_SEND_HANDLER_NAME)};
  window[handlerName] = (_type, payload) => {
    if (!payload || typeof payload !== 'object') return false;
    for (const field of ['url', 'referrer']) {
      const value = payload[field];
      if (typeof value !== 'string' || value.length === 0) continue;
      try {
        const pathname = new URL(value, ${JSON.stringify(URL_PARSE_BASE)}).pathname;
        if (pathname === sensitiveRoot || pathname.startsWith(sensitiveRoot + '/')) return false;
      } catch {
        return false;
      }
    }
    return payload;
  };
})();`;
