export type AllowedRole = 'ROOT_ADMIN' | 'WEDDING_PLANNER' | 'VENDOR';

export interface SecureRoute {
  path: string;
  label: string;
  icon: string;
  roles: AllowedRole[];
}

export const SECURE_ROUTES: SecureRoute[] = [
  { path: '/admin', label: 'Dashboard', icon: '🏠', roles: ['ROOT_ADMIN','WEDDING_PLANNER','VENDOR'] },
  { path: '/admin/saas', label: 'Platform Management', icon: '⚙️', roles: ['ROOT_ADMIN'] },
  { path: '/admin/metrics', label: 'Platform Metrics', icon: '📊', roles: ['ROOT_ADMIN'] },
  { path: '/admin/weddings', label: 'My Weddings', icon: '💍', roles: ['WEDDING_PLANNER'] },
  { path: '/admin/forms', label: 'Forms', icon: '📝', roles: ['WEDDING_PLANNER'] },
  { path: '/admin/vendors', label: 'Vendors', icon: '🛠️', roles: ['WEDDING_PLANNER'] },
  { path: '/admin/tasks', label: 'My Tasks', icon: '📋', roles: ['VENDOR'] },
];