import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { RESERVED_SLUG_PATHS } from '@/utils/slug-constants';

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // ---------- Admin auth guard ----------
  if (pathname.startsWith('/admin') && !pathname.startsWith('/admin/login')) {
    const token = request.cookies.get('admin_token')?.value;
    if (!token) {
      return NextResponse.redirect(new URL('/admin/login', request.url));
    }
  }

  // ---------- Slug route guard ----------
  // Prevent static-asset requests (apple-touch-icon.png, logo_all.png, etc.)
  // from reaching the [slug] dynamic route, which would trigger a pointless
  // backend API call and inflate error counts against the SSR container's IP.
  //
  // We return a 404 directly so the request never reaches [slug]/layout.tsx.
  // Reserved paths (admin, api, etc.) are left alone — they have their own
  // route handlers and Next.js won't match them to [slug].
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length === 1) {
    const segment = segments[0];
    // Contains a dot → file with extension (favicon.ico, logo.png, sw.js, etc.)
    // These are NOT wedding slugs (slugs are alphanumeric + hyphens only).
    if (segment.includes('.')) {
      return new NextResponse('Not Found', { status: 404 });
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
    '/((?!_next/static|_next/image|api/).*)',
  ],
};
