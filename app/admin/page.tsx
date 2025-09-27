import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { normalizeRole } from '@/admin/utils/role';

type AdminProfile = {
  email: string;
  role?: string;
  is_root_admin?: boolean;
  is_wedding_planner?: boolean;
  is_vendor?: boolean;
};

const ROLE_REDIRECTS: Record<string, string> = {
  ROOT_ADMIN: '/admin/saas',
  WEDDING_PLANNER: '/admin/planner',
  VENDOR: '/admin/vendor',
};

async function fetchProfile(token: string): Promise<AdminProfile | null> {
  const backendUrl = process.env.API_BASE_URL || process.env.BACKEND_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!backendUrl) {
    console.error('Missing backend API base URL environment variable');
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

    if (!response.ok) {
      console.error('Failed to fetch admin profile', response.status, await response.text());
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error('Unexpected error while fetching admin profile', error);
    return null;
  }
}

export default async function AdminDashboardPage() {
  const cookieStore = await cookies();
  const isAuthenticated = cookieStore.get('admin_authenticated')?.value === 'true';
  const token = cookieStore.get('admin_token')?.value;

  if (!isAuthenticated || !token) {
    redirect('/admin/login');
  }

  const profile = await fetchProfile(token);

  if (!profile) {
    redirect('/admin/login');
  }

  const normalizedRole = normalizeRole(profile);
  const destination = ROLE_REDIRECTS[normalizedRole] ?? '/admin/login';

  redirect(destination);
}

