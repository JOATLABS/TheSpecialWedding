import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import { SECURE_ROUTES } from '@/admin/config/routePolicy';
import { normalizeRole, type NormalizedRole } from '@/admin/utils/role';

const ROLE_HOME_ROUTE: Partial<Record<NormalizedRole, string>> = {
  ROOT_ADMIN: '/admin/saas',
  WEDDING_PLANNER: '/admin/planner',
  VENDOR: '/admin/vendor',
};

type SearchParams = Record<string, string | string[] | undefined>;

type ProfileRecord = Record<string, unknown>;

function sanitizeNextPath(rawValue: string | null | undefined): string | null {
  if (!rawValue) {
    return null;
  }

  if (!rawValue.startsWith('/admin')) {
    return null;
  }

  if (rawValue.includes('..')) {
    return null;
  }

  return rawValue;
}

function resolveRoleDestination(role: NormalizedRole, fallback: string | null): string | null {
  if (fallback) {
    return fallback;
  }

  if (role in ROLE_HOME_ROUTE) {
    return ROLE_HOME_ROUTE[role as keyof typeof ROLE_HOME_ROUTE] ?? null;
  }

  const defaultSecureRoute = SECURE_ROUTES.find((route) => route.path !== '/admin');
  return defaultSecureRoute?.path ?? null;
}

async function fetchAdminProfile(token: string): Promise<ProfileRecord | null> {
  const baseUrl = process.env.API_BASE_URL || process.env.BACKEND_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    throw new Error('API base URL not configured');
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);

  try {
    const response = await fetch(`${baseUrl}/admin/profile`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        Pragma: 'no-cache',
      },
      cache: 'no-store',
      signal: controller.signal,
    });

    if (response.status === 401) {
      return null;
    }

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      console.error('Admin landing failed to resolve profile', {
        status: response.status,
        payload,
      });
      return null;
=======

    }

    return (await response.json()) as ProfileRecord;
  } finally {
    clearTimeout(timeout);
  }
}

function toSingleValue(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }

  return value;
}

export default async function AdminLandingPage({ searchParams }: { searchParams?: SearchParams }) {
  const cookieStore = await cookies();
  const isAuthenticated = cookieStore.get('admin_authenticated')?.value === 'true';
  const token = cookieStore.get('admin_token')?.value;

  if (!isAuthenticated || !token) {
    redirect('/admin/login');
  }

  const nextHint = sanitizeNextPath(toSingleValue(searchParams?.next) ?? null);

  let profile: ProfileRecord | null = null;

  try {
    profile = await fetchAdminProfile(token);
  } catch (error) {
    console.error('Admin landing encountered an unexpected profile error', error);
    redirect('/admin/login');
  }

  if (!profile) {
    redirect('/admin/login');
  }

  const normalizedRole = normalizeRole(profile);
  const destination = resolveRoleDestination(normalizedRole, nextHint);

  if (!destination) {
    console.error('Admin landing could not determine a dashboard destination', {
      normalizedRole,
      nextHint,
    });
    redirect('/admin/login');
  }

  redirect(destination);
}
