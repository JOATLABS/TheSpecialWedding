const DEFAULT_PUBLIC_FRONTEND_URL = 'https://thespecialwedding.io';

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, '');
}

export function getPublicFrontendBaseUrl(): string {
  const configured =
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.FRONTEND_URL ||
    (typeof window !== 'undefined' ? window.location.origin : '') ||
    DEFAULT_PUBLIC_FRONTEND_URL;

  return normalizeBaseUrl(configured);
}

export function buildGuestOtpVerifyUrl({
  baseUrl = getPublicFrontendBaseUrl(),
  slug,
  token,
}: {
  baseUrl?: string;
  slug: string;
  token: string;
}): string {
  const normalizedBase = normalizeBaseUrl(baseUrl || DEFAULT_PUBLIC_FRONTEND_URL);
  const params = new URLSearchParams({ slug, token });
  return `${normalizedBase}/otp/verify?${params.toString()}`;
}
