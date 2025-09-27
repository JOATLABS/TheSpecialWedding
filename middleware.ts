import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (pathname.startsWith('/admin') && !pathname.startsWith('/admin/login')) {
    const isAuthenticated = req.cookies.get('admin_authenticated')?.value === 'true';

    if (!isAuthenticated) {
      const loginUrl = new URL('/admin/login', req.url);
      loginUrl.searchParams.set('next', pathname);
      return NextResponse.redirect(loginUrl);
    }

    // User is authenticated - allow access
    return NextResponse.next();
  }

  return NextResponse.next();
}

// (Optional) limit matcher if you only want admin guarding
export const config = {
  matcher: ['/admin/:path*'],
};