export const SITE_ORIGIN = 'https://thespecialwedding.io';

export const PUBLIC_LOGIN_PATH = '/login';
export const PRIVATE_ADMIN_LOGIN_PATH = '/admin/login';
export const PUBLIC_OG_IMAGE_PATH = '/api/og';

export const ROBOTS_ALLOWED_PATHS = ['/', PUBLIC_OG_IMAGE_PATH] as const;

export const ROBOTS_DISALLOWED_PATHS = [
  '/admin/',
  '/api/',
  '/otp/',
  '/setup-account',
  '/reset-password',
] as const;

type PublicOgTarget =
  | {
      type: 'blog';
      slug: string;
    }
  | {
      type: 'vendor';
      id: string;
    };

export function buildPublicOgImagePath(target: PublicOgTarget): string {
  const params = new URLSearchParams({ type: target.type });

  if (target.type === 'blog') {
    params.set('slug', target.slug);
  } else {
    params.set('id', target.id);
  }

  return `${PUBLIC_OG_IMAGE_PATH}?${params.toString()}`;
}

export function buildPublicOgImageUrl(target: PublicOgTarget): string {
  return `${SITE_ORIGIN}${buildPublicOgImagePath(target)}`;
}
