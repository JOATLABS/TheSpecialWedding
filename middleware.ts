import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Reserved top-level paths that should never be treated as wedding slugs.
// Checked in middleware (before layout.tsx) so the SSR container never makes
// a pointless API call to /weddings/privacy-info/<reserved-path>.
const RESERVED_PATHS = new Set([
  '_next', 'api', 'admin', 'favicon', 'robots', 'sitemap',
]);

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
  // For top-level paths like /<slug>, reject anything that looks like a
  // static asset (contains a dot → favicon.ico, apple-touch-icon.png, etc.)
  // or is a reserved path name.  This runs before the [slug] layout so we
  // avoid unnecessary backend API calls that inflate error counts.
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length >= 1) {
    const firstSegment = segments[0];
    // Contains a dot → file extension (favicon.ico, logo.png, sw.js, etc.)
    if (firstSegment.includes('.')) {
      return NextResponse.next(); // Let Next.js static file handling deal with it
    }
    // Exact reserved path — already handled by other routes, not a slug
    if (RESERVED_PATHS.has(firstSegment.toLowerCase())) {
      return NextResponse.next();
    }
  }

  return NextResponse.next();
}

export const config = {
  // Run on admin routes AND all top-level slug-like paths.
  // Next.js automatically excludes _next/static, _next/image, and favicon.ico
  // from middleware, but other static assets (apple-touch-icon.png, etc.) can
  // still leak through to dynamic routes.
  matcher: [
    '/admin/:path*',
    '/((?!_next/static|_next/image).*)',
  ],
};
