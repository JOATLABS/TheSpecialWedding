export function resolveApiUrl(path: string): string {
  if (!path) {
    throw new Error('resolveApiUrl requires a non-empty path');
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '');

  if (configuredBase) {
    return `${configuredBase}${normalizedPath}`;
  }

  return normalizedPath;
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
