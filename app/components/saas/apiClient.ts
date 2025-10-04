export function resolveApiUrl(path: string): string {
  if (!path) {
    throw new Error('resolveApiUrl requires a non-empty path');
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '');

  if (configuredBase) {
    return `${configuredBase}${normalizedPath}`;
  }

  // When no explicit API base URL is provided we rely on the frontend proxying requests
  // through a rewrite such as `/api/:path* -> https://api.example.com/:path*`. Default to
  // the conventional `/api` prefix while allowing deployments to override it.
  const proxyPrefixEnv = process.env.NEXT_PUBLIC_API_PROXY_PREFIX;
  const proxyPrefix = proxyPrefixEnv
    ? proxyPrefixEnv.startsWith('/')
      ? proxyPrefixEnv.replace(/\/$/, '')
      : `/${proxyPrefixEnv.replace(/\/$/, '')}`
    : '/api';

  if (!proxyPrefix || proxyPrefix === '/') {
    return normalizedPath;
  }

  const normalizedProxyPrefix = proxyPrefix.replace(/\/$/, '');

  if (normalizedPath.startsWith(`${normalizedProxyPrefix}/`)) {
    return normalizedPath;
  }

  return `${normalizedProxyPrefix}${normalizedPath}`;
}

export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
  timeoutMs = 8000
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(input, {
      ...init,
      signal: controller.signal,
    });

    return response;
  } finally {
    clearTimeout(timer);
  }
}
