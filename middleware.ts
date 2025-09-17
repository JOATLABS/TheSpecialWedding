import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Check if the request is for an admin route (excluding login and API routes)
  if (request.nextUrl.pathname.startsWith('/admin') &&
      !request.nextUrl.pathname.startsWith('/admin/login') &&
      !request.nextUrl.pathname.startsWith('/admin/api')) {

    // Check for EITHER admin_token (httpOnly) OR admin_authenticated (readable) cookie
    // The admin_token is set by the API route but might not be visible during SSR
    // The admin_authenticated cookie is always readable and indicates logged-in state
    const token = request.cookies.get('admin_token')?.value;
    const authenticated = request.cookies.get('admin_authenticated')?.value;

    // Also check for the cookies in the cookie header
    const cookieHeader = request.headers.get('cookie');
    const hasTokenInHeader = cookieHeader && cookieHeader.includes('admin_token=');
    const hasAuthInHeader = cookieHeader && cookieHeader.includes('admin_authenticated=true');

    // If we have neither the token nor the authenticated cookie, redirect to login
    if (!token && !authenticated && !hasTokenInHeader && !hasAuthInHeader) {
      return NextResponse.redirect(new URL('/admin/login', request.url));
    }

    // User is authenticated if any of these conditions are met:
    // 1. We have the admin_token cookie
    // 2. We have the admin_authenticated=true cookie
    // 3. Either cookie exists in the header
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: '/admin/:path*'
};