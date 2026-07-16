export interface StorefrontRouteState {
  tab: 'domain' | null;
  attemptId: string | null;
}

export type StorefrontRouteUpdate =
  | { tab: 'domain'; attemptId?: string | null }
  | { tab: null; attemptId?: null };

const SAFE_ATTEMPT_ID = /^[A-Za-z0-9_-]{1,128}$/;

function safeAttemptId(value: string | null | undefined): string | null {
  if (!value || !SAFE_ATTEMPT_ID.test(value)) return null;
  return value;
}

export function parseStorefrontRouteState(
  searchParams: URLSearchParams,
): StorefrontRouteState {
  if (searchParams.get('storefront') !== 'domain') {
    return { tab: null, attemptId: null };
  }
  return {
    tab: 'domain',
    attemptId: safeAttemptId(searchParams.get('attempt')),
  };
}

export function buildStorefrontRouteUrl(
  pathname: string,
  currentSearchParams: URLSearchParams,
  update: StorefrontRouteUpdate,
): string {
  const next = new URLSearchParams(currentSearchParams);
  if (update.tab === 'domain') {
    next.set('storefront', 'domain');
    const attemptId = safeAttemptId(update.attemptId);
    if (attemptId) next.set('attempt', attemptId);
    else next.delete('attempt');
  } else {
    next.delete('storefront');
    next.delete('attempt');
  }
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}
