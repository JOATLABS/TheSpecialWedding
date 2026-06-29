export function buildAdminApiUrl(
  apiBaseUrl: string,
  path: string,
  browserOrigin = typeof window !== 'undefined' ? window.location.origin : undefined,
): URL {
  const normalizedBase = apiBaseUrl.trim().replace(/\/+$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  if (!normalizedBase) {
    throw new Error('API base URL is required.');
  }

  return new URL(`${normalizedBase}${normalizedPath}`, browserOrigin);
}
