import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { isNonWeddingSlug } from '@/utils/slug-constants';

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // ---------- Admin auth guard ----------
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
