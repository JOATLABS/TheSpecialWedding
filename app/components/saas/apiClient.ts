export function resolveApiUrl(path: string): string {
  if (!path) {
    throw new Error('resolveApiUrl requires a non-empty path');
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

  if (!configuredBase) {
    throw new Error(
      'NEXT_PUBLIC_API_BASE_URL must be set to resolve SaaS API endpoints. Update your environment configuration.'
    );
  }

  const base = configuredBase.endsWith('/') ? configuredBase.slice(0, -1) : configuredBase;

  return `${base}${normalizedPath}`;
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
