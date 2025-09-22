// Centralized API base URL resolution
// Provides consistent fallback logic and throws early if missing in critical admin contexts

const DEFAULT_LOCAL = 'http://localhost:8000';

export interface ApiBaseOptions {
  /** If true, will throw when env var missing instead of returning fallback */
  require?: boolean;
  /** Optional path segment to append (no leading slash needed) */
  path?: string;
}

export function getApiBase(options: ApiBaseOptions = {}): string {
  const env = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!env && options.require) {
    throw new Error('NEXT_PUBLIC_API_BASE_URL not configured');
  }
  return env || DEFAULT_LOCAL;
}

export function buildApiUrl(path: string, options: ApiBaseOptions = {}): string {
  const base = getApiBase(options);
  const clean = path.startsWith('/') ? path.slice(1) : path;
  return `${base.replace(/\/$/, '')}/${clean}`;
}
