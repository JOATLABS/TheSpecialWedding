import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (pathname.startsWith('/admin') && !pathname.startsWith('/admin/login')) {
    const token = req.cookies.get('admin_token')?.value;

    if (!token) {
      const loginUrl = new URL('/admin/login', req.url);
      loginUrl.searchParams.set('next', pathname);
      return NextResponse.redirect(loginUrl);
    }

    // Validate token with backend
    try {
      const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
      if (!backendUrl) {
        throw new Error('Backend URL not configured');
      }

      const response = await fetch(`${backendUrl}/admin/profile`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        // Add timeout to prevent hanging
        signal: AbortSignal.timeout(5000),
      });

      if (!response.ok) {
        // Invalid token - clear cookies and redirect
        const loginUrl = new URL('/admin/login', req.url);
        const redirectResponse = NextResponse.redirect(loginUrl);
        redirectResponse.cookies.delete('admin_token');
        redirectResponse.cookies.delete('admin_authenticated');
        return redirectResponse;
      }

      // Token is valid - continue to page
      return NextResponse.next();

    } catch (error) {
      console.error('Auth middleware error:', error);
      // On error, redirect to login and clear cookies
      const loginUrl = new URL('/admin/login', req.url);
      const redirectResponse = NextResponse.redirect(loginUrl);
      redirectResponse.cookies.delete('admin_token');
      redirectResponse.cookies.delete('admin_authenticated');
      return redirectResponse;
    }
  }

  return NextResponse.next();
}

// (Optional) limit matcher if you only want admin guarding
export const config = {
  matcher: ['/admin/:path*'],
};