import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import { SECURE_ROUTES } from '@/admin/config/routePolicy';
import { normalizeRole, type NormalizedRole } from '@/admin/utils/role';

const ROLE_HOME_ROUTE: Partial<Record<NormalizedRole, string>> = {
  ROOT_ADMIN: '/admin/saas',
  WEDDING_PLANNER: '/admin/planner',
  VENDOR: '/admin/vendor',
};

function resolveRoleDestination(role: NormalizedRole): string {
  if (role in ROLE_HOME_ROUTE) {
    return ROLE_HOME_ROUTE[role as keyof typeof ROLE_HOME_ROUTE] ?? '/admin/login';
  }

  const defaultSecureRoute = SECURE_ROUTES.find((route) => route.path !== '/admin');
  return defaultSecureRoute?.path ?? '/admin/login';
}

async function fetchAdminProfile(token: string) {
  const backendUrl =
    process.env.API_BASE_URL ||
    process.env.BACKEND_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!backendUrl) {
    console.error('Admin landing missing API base URL configuration');
    return null;
  }

  try {
    const response = await fetch(`${backendUrl}/admin/profile`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (response.status === 401) {
      return null;
    }

    if (!response.ok) {
      console.error('Admin landing failed to load profile', {
        status: response.status,
        statusText: response.statusText,
      });
      return null;
    }

    return (await response.json()) as Record<string, unknown> | null;
  } catch (error) {
    console.error('Admin landing profile request failed', error);
    return null;
  }
}

export default async function AdminLandingPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('admin_token')?.value;
  const isAuthenticated = cookieStore.get('admin_authenticated')?.value === 'true';

  if (!token || !isAuthenticated) {
    redirect('/admin/login');
  }

  const profile = await fetchAdminProfile(token);

  if (!profile) {
    redirect('/admin/login');
  }

  const destination = resolveRoleDestination(normalizeRole(profile));

  redirect(destination);

  return null;
}
