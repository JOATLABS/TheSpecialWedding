import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { isNonWeddingSlug } from '@/utils/slug-constants';
import { STOREFRONT_DOMAIN_PROBE_PATH } from '@/utils/storefrontDomainVerification';
import { resolveCustomStorefrontHost } from '@/utils/storefrontHost';

export function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // ---------- Request authority / active custom storefront host ----------
  // This is routing only. The public storefront API remains authoritative and
  // returns 404 unless this exact hostname is active and published. Entitlement
  // loss blocks new setup but must not silently disable an existing mapping.
  // Host is the request authority boundary. A client-controlled forwarded host
  // must never override it and select another tenant's storefront. Authority is
  // resolved before auth redirects so custom or malformed hosts cannot expose
  // first-party platform routes or login locations.
  const storefrontHostConfig = {
    platformDomains: process.env.STOREFRONT_PLATFORM_DOMAINS,
    frontendUrl: process.env.FRONTEND_URL,
    apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
    cnameTarget: process.env.STOREFRONT_CNAME_TARGET,
  };
  const storefrontAuthority = resolveCustomStorefrontHost(
    request.headers.get('host'),
    storefrontHostConfig,
  );
  if (storefrontAuthority.kind === 'custom' && pathname === '/') {
    const rewriteUrl = request.nextUrl.clone();
    rewriteUrl.pathname = `/storefront/${encodeURIComponent(storefrontAuthority.hostname)}`;
    return NextResponse.rewrite(rewriteUrl);
  }
  if (
    storefrontAuthority.kind === 'custom' &&
    pathname === STOREFRONT_DOMAIN_PROBE_PATH
  ) {
    return NextResponse.next();
  }
  if (storefrontAuthority.kind !== 'platform') {
    return new NextResponse('Not Found', { status: 404 });
  }

  // ---------- Admin auth guard (verified platform authority only) ----------
  if (
    pathname.startsWith('/admin') &&
    !pathname.startsWith('/admin/login') &&
    !pathname.startsWith('/admin/team/accept')
  ) {
    const token = request.cookies.get('admin_token')?.value;
    if (!token) {
      return NextResponse.redirect(new URL('/admin/login', request.url));
    }
  }

  // ---------- Slug route guard ----------
  // Prevent static-asset requests and reserved paths from reaching the [slug]
  // dynamic route, which would trigger a pointless backend API call and inflate
  // error counts against the SSR container's IP.
  //
  // Uses the shared isNonWeddingSlug() helper (slug-constants.ts) so the
  // validation logic stays in one place between middleware and layout.tsx.
  // Skip slug guard for admin routes (already handled above)
  if (!pathname.startsWith('/admin')) {
    const segments = pathname.split('/').filter(Boolean);
    if (segments.length === 1) {
      const segment = segments[0];
      if (isNonWeddingSlug(segment)) {
        return new NextResponse('Not Found', { status: 404 });
      }
    }
  }

  return NextResponse.next();
}

export const config = {
  // Run on admin routes AND top-level paths that could be wedding slugs.
  // Next.js automatically excludes _next/static, _next/image, and favicon.ico.
  // We also exclude api routes to avoid unnecessary middleware overhead.
  matcher: [
    '/admin/:path*',
    '/((?!_next/static|_next/image|api/|.*\\..*).*)',
  ],
};
