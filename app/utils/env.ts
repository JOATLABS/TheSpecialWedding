/**
 * Environment configuration utilities
 *
 * This module provides type-safe access to environment variables with required validation.
 * All environment variables are validated at runtime to ensure they are set.
 * NO FALLBACKS - missing variables will throw errors and notify root admin.
 */

function reportConfigError(errorType: string, message: string, variableName: string, currentValue?: string): void {
  if (typeof window === 'undefined') return;

  const payload = JSON.stringify({
    error_type: errorType,
    message,
    variable_name: variableName,
    current_value: currentValue,
    hostname: window.location.hostname,
    user_agent: navigator.userAgent,
  });

  // Use sendBeacon for reliable delivery even if page crashes/navigates
  if (navigator.sendBeacon) {
    const blob = new Blob([payload], { type: 'application/json' });
    navigator.sendBeacon('/report-config-error', blob);
  } else {
    // Fallback to fetch (fire-and-forget)
    fetch('/report-config-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true, // Ensures request completes even if page unloads
    }).catch(() => {});
  }
}

const LOCAL_HOSTNAMES = new Set(['localhost', '127.0.0.1']);

function normalizeBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, '');
}

export function getBrowserOrigin(): string {
  if (typeof window === 'undefined') {
    throw new Error('Unable to determine this app URL outside the browser.');
  }

  const origin = window.location?.origin?.trim();
  if (origin) {
    return normalizeBaseUrl(origin);
  }

  throw new Error('Unable to determine this app URL. Refresh and try again.');
}

export function resolveBrowserUrl(pathname: string): string {
  const normalizedPath = pathname.startsWith('/') ? pathname : `/${pathname}`;
  return new URL(normalizedPath, `${getBrowserOrigin()}/`).toString();
}

function deriveApiOrigin(protocol: string, hostname: string): string | null {
  if (!hostname) {
    return null;
  }

  const normalizedProtocol = protocol === 'https:' ? 'https:' : 'http:';

  if (LOCAL_HOSTNAMES.has(hostname)) {
    return `${normalizedProtocol}//${hostname}:8000`;
  }

  if (hostname === 'thespecialwedding.io' || hostname === 'www.thespecialwedding.io') {
    return `${normalizedProtocol}//api.thespecialwedding.io`;
  }

  if (hostname === 'staging.thespecialwedding.io') {
    return `${normalizedProtocol}//api.staging.thespecialwedding.io`;
  }

  if (hostname.startsWith('api.')) {
    return `${normalizedProtocol}//${hostname}`;
  }

  return `${normalizedProtocol}//api.${hostname}`;
}

function deriveApiBaseUrlFromFrontendUrl(frontendUrl?: string): string | null {
  if (!frontendUrl) {
    return null;
  }

  try {
    const parsed = new URL(frontendUrl);
    const derived = deriveApiOrigin(parsed.protocol, parsed.hostname);
    return derived ? normalizeBaseUrl(derived) : null;
  } catch {
    return null;
  }
}

function getConfiguredApiBaseUrl(): string {
  const internalUrl = process.env.INTERNAL_API_BASE_URL?.trim();
  if (internalUrl) {
    return normalizeBaseUrl(internalUrl);
  }

  // Bracket notation prevents Next.js from statically replacing this with the
  // literal value at build time, keeping the API URL out of the client bundle.
  // This function is server-side only; the browser path returns '/api/proxy' first.
  const publicUrl = (process.env['NEXT_PUBLIC_API_BASE_URL'] as string | undefined)?.trim();
  if (publicUrl) {
    return normalizeBaseUrl(publicUrl);
  }

  const derivedFromFrontend = deriveApiBaseUrlFromFrontendUrl(process.env.FRONTEND_URL?.trim());
  if (derivedFromFrontend) {
    return derivedFromFrontend;
  }

  const errorMsg = 'CRITICAL: Could not resolve API base URL. Configure INTERNAL_API_BASE_URL, ' +
    'NEXT_PUBLIC_API_BASE_URL, or FRONTEND_URL for this deployment.';
  console.error(errorMsg);
  reportConfigError('MissingEnvVar', errorMsg, 'INTERNAL_API_BASE_URL | NEXT_PUBLIC_API_BASE_URL | FRONTEND_URL');
  throw new Error(errorMsg);
}

/**
 * Get the API base URL.
 *
 * In the browser, always returns the relative path '/api/proxy' so that all
 * API calls are routed through the Next.js rewrite rule. This keeps the API
 * subdomain invisible to crawlers and out of the client bundle.
 *
 * On the server (SSR/RSC/sitemap/etc.) uses deployment env vars so that
 * server-side fetches reach the backend directly without a round trip through
 * the public proxy.
 */
export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    return '/api/proxy';
  }

  return getConfiguredApiBaseUrl();
}

/**
 * Get the server-side API base URL.
 *
 * In single-container deployments such as the current Coolify setup, the
 * frontend can bypass the public proxy and talk to the colocated backend over
 * loopback. That removes an unnecessary network hop for server-rendered data
 * fetches while preserving the public browser-facing API base URL.
 */
export function getServerApiBaseUrl(): string {
  return getConfiguredApiBaseUrl();
}

/**
 * Get the frontend base URL (for server-side use only)
 * @throws {Error} if FRONTEND_URL is not set
 */
export function getFrontendUrl(): string {
  const url = process.env.FRONTEND_URL;
  if (!url) {
    throw new Error(
      'FRONTEND_URL environment variable is required. ' +
      'Please set it in your .env file.'
    );
  }
  return url;
}

/**
 * Check if API base URL is configured
 */
export function isApiConfigured(): boolean {
  try {
    return !!getApiBaseUrl();
  } catch {
    return false;
  }
}
