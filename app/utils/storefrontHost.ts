const PLATFORM_DOMAINS = ['thespecialwedding.io', 'thespecialwedding.com'] as const;

function isPlatformHostname(hostname: string): boolean {
  return PLATFORM_DOMAINS.some(
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

function normalizeHostHeader(hostHeader: string): string | null {
  const candidate = hostHeader.trim().toLowerCase();
  if (
    !candidate ||
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
  if (
    !hostname ||
    hostname.length > 253 ||
    hostname === 'localhost' ||
    hostname.endsWith('.localhost') ||
    isIpAddress(hostname) ||
    !hostname.includes('.')
  ) {
    return null;
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
    return null;
  }

  return hostname;
}

/**
 * Resolve a custom storefront host without changing ordinary platform routes.
 * The backend remains authoritative: the rewrite target will render only when
 * this exact hostname belongs to a currently active storefront domain.
 */
export function resolveStorefrontRewriteHost(
  hostHeader: string | null,
  pathname: string,
): string | null {
  if (pathname !== '/' || hostHeader === null) {
    return null;
  }

  const hostname = normalizeHostHeader(hostHeader);
  if (!hostname || isPlatformHostname(hostname)) {
    return null;
  }

  return hostname;
}
