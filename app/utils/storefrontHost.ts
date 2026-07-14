const CANONICAL_PLATFORM_DOMAINS = [
  'thespecialwedding.io',
  'thespecialwedding.com',
] as const;

export interface StorefrontPlatformHostConfig {
  platformDomains?: string | null;
  frontendUrl?: string | null;
  apiBaseUrl?: string | null;
  cnameTarget?: string | null;
}

export type StorefrontHostResolution =
  | { kind: 'invalid' }
  | { kind: 'platform'; hostname: string }
  | { kind: 'custom'; hostname: string };

function isPlatformHostname(
  hostname: string,
  platformDomains: ReadonlySet<string>,
): boolean {
  return Array.from(platformDomains).some(
    (domain) => hostname === domain || hostname.endsWith(`.${domain}`),
  );
}

function isIpAddress(hostname: string): boolean {
  if (hostname.includes(':')) {
    return true;
  }

  const parts = hostname.split('.');
  return (
    parts.length === 4 &&
    parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255)
  );
}

function normalizeHostAuthority(hostHeader: string): string | null {
  const candidate = hostHeader.trim().toLowerCase();
  if (
    !candidate ||
    candidate.endsWith(':') ||
    candidate.includes(',') ||
    /[\s/@\\%?#]/.test(candidate) ||
    candidate.includes('://')
  ) {
    return null;
  }

  let parsed: URL;
  try {
    parsed = new URL(`http://${candidate}`);
  } catch {
    return null;
  }

  const hostname = parsed.hostname.toLowerCase().replace(/\.$/, '');
  if (!hostname || hostname.length > 253) {
    return null;
  }

  return hostname;
}

function isCustomStorefrontHostname(hostname: string): boolean {
  if (
    hostname === 'localhost' ||
    hostname.endsWith('.localhost') ||
    isIpAddress(hostname) ||
    !hostname.includes('.')
  ) {
    return false;
  }

  const labels = hostname.split('.');
  if (
    labels.some(
      (label) =>
        !label ||
        label.length > 63 ||
        !/^[a-z0-9-]+$/.test(label) ||
        label.startsWith('-') ||
        label.endsWith('-'),
    )
  ) {
    return false;
  }

  return true;
}

function parseConfiguredDomains(value: string | null | undefined): string[] {
  const candidate = value?.trim();
  if (!candidate) {
    return [];
  }

  if (candidate.startsWith('[')) {
    try {
      const parsed = JSON.parse(candidate) as unknown;
      if (Array.isArray(parsed)) {
        return parsed
          .filter((item): item is string => typeof item === 'string')
          .map((item) => item.trim())
          .filter(Boolean);
      }
    } catch {
      // Fall through to the backend-compatible comma-separated parser.
    }
  }

  return candidate
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeConfiguredHostname(value: string): string | null {
  const candidate = value.trim();
  if (!candidate) {
    return null;
  }

  if (candidate.includes('://')) {
    try {
      const parsed = new URL(candidate);
      if (
        !['http:', 'https:'].includes(parsed.protocol) ||
        parsed.username ||
        parsed.password
      ) {
        return null;
      }
      return normalizeHostAuthority(parsed.host);
    } catch {
      return null;
    }
  }

  return normalizeHostAuthority(candidate);
}

function resolvePlatformDomains(
  config: StorefrontPlatformHostConfig,
): ReadonlySet<string> {
  const domains = new Set<string>(CANONICAL_PLATFORM_DOMAINS);
  const configuredCandidates = [
    ...parseConfiguredDomains(config.platformDomains),
    config.frontendUrl,
    config.apiBaseUrl,
    config.cnameTarget,
  ];

  for (const candidate of configuredCandidates) {
    if (typeof candidate !== 'string') {
      continue;
    }
    const hostname = normalizeConfiguredHostname(candidate);
    if (hostname) {
      domains.add(hostname);
    }
  }

  return domains;
}

/**
 * Resolve a custom storefront host without changing ordinary platform routes.
 * The backend remains authoritative: the rewrite target will render only when
 * this exact hostname belongs to a currently active storefront domain.
 */
export function resolveStorefrontRewriteHost(
  hostHeader: string | null,
  pathname: string,
  platformConfig: StorefrontPlatformHostConfig = {},
): string | null {
  if (pathname !== '/') {
    return null;
  }

  const authority = resolveCustomStorefrontHost(hostHeader, platformConfig);
  return authority.kind === 'custom' ? authority.hostname : null;
}

/**
 * Classify the actual request authority independently from its path.
 * Only an explicit platform result may enter unrestricted first-party routes;
 * custom storefront hosts remain tenant boundaries and invalid authority must
 * fail closed rather than inheriting platform access from a nullable result.
 */
export function resolveCustomStorefrontHost(
  hostHeader: string | null,
  platformConfig: StorefrontPlatformHostConfig = {},
): StorefrontHostResolution {
  if (hostHeader === null) {
    return { kind: 'invalid' };
  }

  const hostname = normalizeHostAuthority(hostHeader);
  if (!hostname) {
    return { kind: 'invalid' };
  }
  if (isPlatformHostname(hostname, resolvePlatformDomains(platformConfig))) {
    return { kind: 'platform', hostname };
  }
  if (!isCustomStorefrontHostname(hostname)) {
    return { kind: 'invalid' };
  }

  return { kind: 'custom', hostname };
}
