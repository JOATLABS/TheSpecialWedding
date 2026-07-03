type EnvLike = Record<string, string | undefined>;

export type UmamiScriptConfig = {
  websiteId: string;
  src: string;
};

const LOCAL_OR_PRIVATE_HOSTS = new Set(['localhost', '0.0.0.0', '::1']);

function isPrivateIpv4(hostname: string): boolean {
  const parts = hostname.split('.').map((part) => Number(part));
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
    return false;
  }

  const [first, second] = parts;
  return (
    first === 10 ||
    first === 127 ||
    (first === 172 && second >= 16 && second <= 31) ||
    (first === 192 && second === 168)
  );
}

function getPublicOrigin(value: string | undefined): string | null {
  if (!value) return null;

  try {
    const url = new URL(value);
    const hostname = url.hostname.toLowerCase();
    if (
      url.protocol !== 'https:' ||
      LOCAL_OR_PRIVATE_HOSTS.has(hostname) ||
      hostname.endsWith('.local') ||
      !hostname.includes('.') ||
      isPrivateIpv4(hostname)
    ) {
      return null;
    }

    return url.origin;
  } catch {
    return null;
  }
}

function normalizeScriptSrc(value: string | undefined): string | null {
  if (!value) return null;

  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return null;
    return url.toString();
  } catch {
    return null;
  }
}

function deriveOriginFromApiBase(value: string | undefined): string | null {
  const origin = getPublicOrigin(value);
  if (!origin || !value) return null;

  try {
    const url = new URL(value);
    if (!url.pathname.replace(/\/+$/, '').endsWith('/api')) {
      return null;
    }
    return origin;
  } catch {
    return null;
  }
}

export function resolveUmamiScriptConfig(env: EnvLike = process.env): UmamiScriptConfig | null {
  const websiteId = env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || env.UMAMI_WEBSITE_ID;
  if (!websiteId) return null;

  const explicitSrc = normalizeScriptSrc(env.NEXT_PUBLIC_UMAMI_SRC);
  if (explicitSrc) {
    return { websiteId, src: explicitSrc };
  }

  const publicOrigin =
    getPublicOrigin(env.UMAMI_DASHBOARD_URL) ||
    deriveOriginFromApiBase(env.UMAMI_API_BASE);

  if (!publicOrigin) return null;

  return {
    websiteId,
    src: `${publicOrigin}/script.js`,
  };
}
