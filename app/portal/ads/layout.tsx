'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import {
  bootstrapAdminAuthToken,
  clearAdminAuthStorage,
  persistAdminAuthToken,
} from '@/utils/adminAuthStorage';
import {
  LayoutDashboard,
  Megaphone,
  Image,
  Users,
  CreditCard,
  Settings,
  LogOut,
  Bell,
  ExternalLink,
  ArrowRight,
  CheckCircle2,
  ShieldCheck,
} from 'lucide-react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { Toaster } from 'sonner';
import {
  WorkspaceBackground,
  WorkspaceShellFrame,
  WorkspaceSidebar,
  WorkspaceTopHeader,
  useResponsiveWorkspaceSidebar,
  type WorkspaceNavItem,
} from '@/components/layout/WorkspaceChrome';
import {
  vendorInputClass,
  vendorInsetClass,
  vendorPrimaryButtonClass,
  vendorSecondaryButtonClass,
  vendorSurfaceClass,
} from './components/styles';
import { VendorAuthShell, VendorAuthShowcase } from './components/VendorAuthShell';
import {
  VendorAuthContext,
  type VendorUser,
} from './components/VendorAuthContext';

const API_BASE = getApiBaseUrl();
const PUBLIC_VENDOR_PORTAL_ROUTES = new Set(['/portal/ads/signup']);

type VendorPortalProfile = {
  _id?: string;
  id?: string;
  email?: string;
  role?: string;
  is_root_admin?: boolean;
  company_name?: string;
  business_name?: string;
  must_change_password?: boolean;
  user_data?: {
    business_name?: string;
    company_name?: string;
    must_change_password?: boolean;
  };
};

function clearLegacyVendorPortalStorage() {
  if (typeof window === 'undefined') {
    return;
  }

  localStorage.removeItem('vendor_ad_token');
  localStorage.removeItem('vendor_ad_user');
}

function shapeVendorPortalUser(
  profile: VendorPortalProfile,
  fallbackEmail = '',
): VendorUser {
  const businessName =
    profile.business_name ||
    profile.user_data?.business_name ||
    profile.company_name ||
    profile.user_data?.company_name ||
    profile.email ||
    fallbackEmail ||
    'Advertising Vendor';

  return {
    _id: profile._id || profile.id || '',
    email: profile.email || fallbackEmail,
    name: businessName,
    role: profile.is_root_admin ? 'root_admin' : (profile.role || 'advertising_vendor'),
    must_change_password:
      profile.must_change_password || profile.user_data?.must_change_password || false,
  };
}

// =============================================================================
// Navigation Items
// =============================================================================

const navItems = [
  { name: 'Overview', href: '/portal/ads', icon: LayoutDashboard },
  { name: 'Campaigns', href: '/portal/ads/campaigns', icon: Megaphone },
  { name: 'Creatives', href: '/portal/ads/creatives', icon: Image },
  { name: 'Leads', href: '/portal/ads/leads', icon: Users },
  { name: 'Billing', href: '/portal/ads/billing', icon: CreditCard },
  { name: 'Notifications', href: '/portal/ads/notifications', icon: Bell },
  { name: 'Settings', href: '/portal/ads/settings', icon: Settings },
];

// =============================================================================
// Layout Component
// =============================================================================

export default function VendorPortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <VendorPortalLayoutInner>{children}</VendorPortalLayoutInner>
    </ThemeProvider>
  );
}

function VendorPortalLayoutInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicPage = PUBLIC_VENDOR_PORTAL_ROUTES.has(pathname);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<VendorUser | null>(null);
  const [loading, setLoading] = useState(() => !isPublicPage);
  const {
    isMobile,
    isSidebarOpen: sidebarOpen,
    setIsSidebarOpen: setSidebarOpen,
  } = useResponsiveWorkspaceSidebar();

  useEffect(() => {
    let cancelled = false;

    if (isPublicPage) {
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    const bootstrapVendorSession = async () => {
      if (!cancelled) {
        setLoading(true);
      }
      clearLegacyVendorPortalStorage();

      try {
        const accessToken = await bootstrapAdminAuthToken();
        if (!accessToken) {
          return;
        }

        const profileRes = await fetch(`${API_BASE}/admin/profile`, {
          headers: { Authorization: `Bearer ${accessToken}` },
          credentials: 'include',
        });

        if (!profileRes.ok) {
          clearAdminAuthStorage();
          return;
        }

        const profile = await profileRes.json();
        if (!profile.is_root_admin && profile.role !== 'advertising_vendor') {
          clearAdminAuthStorage();
          return;
        }

        if (!cancelled) {
          setToken(accessToken);
          setUser(shapeVendorPortalUser(profile));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    bootstrapVendorSession();

    return () => {
      cancelled = true;
    };
  }, [isPublicPage]);

  const login = async (email: string, password: string) => {
    // Uses the same /admin/token endpoint as AdminContext — it's role-agnostic
    const response = await fetch(`${API_BASE}/admin/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      credentials: 'include',
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Login failed');
    }

    const data = await response.json();
    const accessToken = data.access_token;

    // Fetch profile to get vendor details (same as AdminContext pattern)
    const profileRes = await fetch(`${API_BASE}/admin/profile`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    });

    if (!profileRes.ok) {
      throw new Error('Failed to verify account');
    }

    const profile = await profileRes.json();

    // Only allow advertising_vendor or root_admin into the vendor portal
    if (!profile.is_root_admin && profile.role !== 'advertising_vendor') {
      throw new Error('This portal is for advertising vendors only');
    }

    persistAdminAuthToken(accessToken, true);
    setToken(accessToken);
    setUser(shapeVendorPortalUser(profile, email));
  };

  const logout = useCallback(() => {
    void fetch(`${API_BASE}/admin/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
    clearAdminAuthStorage();
    clearLegacyVendorPortalStorage();
    setToken(null);
    setUser(null);
  }, []);

  const isActive = (href: string) => {
    if (href === '/portal/ads') return pathname === '/portal/ads';
    return pathname.startsWith(href);
  };

  const authValue = { token, user, loading, login, logout };

  if (isPublicPage) {
    return (
      <VendorAuthContext.Provider value={authValue}>
        <div className="min-h-screen bg-light-bg text-light-text transition-colors duration-300 dark:bg-dark-bg dark:text-dark-text">
          <WorkspaceBackground />
          <main className="relative z-10 min-h-screen">
            {children}
          </main>
          <Toaster position="top-right" richColors theme="system" />
        </div>
      </VendorAuthContext.Provider>
    );
  }

  // Show login if not authenticated
  if (!loading && !token) {
    return (
      <VendorAuthContext.Provider value={authValue}>
        <LoginPage onLogin={login} />
        <Toaster position="top-right" richColors theme="system" />
      </VendorAuthContext.Provider>
    );
  }

  // Force password change screen — intercepts before portal access
  if (!loading && token && user?.must_change_password) {
    return (
      <VendorAuthContext.Provider value={authValue}>
        <ForcePasswordChangePage
          token={token}
          userEmail={user.email}
          onPasswordChanged={() => {
            const updated = { ...user, must_change_password: false };
            setUser(updated);
          }}
          onLogout={logout}
        />
        <Toaster position="top-right" richColors theme="system" />
      </VendorAuthContext.Provider>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-light-bg text-light-text transition-colors duration-300 dark:bg-dark-bg dark:text-dark-text">
        <WorkspaceBackground />
        <div className="relative z-10 flex min-h-screen items-center justify-center">
          <div className={`${vendorSurfaceClass} flex items-center gap-3 px-6 py-4 text-sm text-slate-600 dark:text-slate-300`}>
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
            Loading vendor workspace...
          </div>
        </div>
      </div>
    );
  }

  return (
    <VendorAuthContext.Provider value={authValue}>
      <WorkspaceShellFrame
        sidebar={
          <VendorSidebar
            user={user}
            isOpen={sidebarOpen}
            isMobile={isMobile}
            onClose={() => setSidebarOpen(false)}
            onToggle={() => setSidebarOpen(!sidebarOpen)}
            onLogout={logout}
            isActive={isActive}
          />
        }
        header={
          <VendorTopHeader
            user={user}
            token={token}
            onMenuClick={() => setSidebarOpen(!sidebarOpen)}
            onLogout={logout}
          />
        }
        isMobile={isMobile}
        isSidebarOpen={sidebarOpen}
        afterShell={<Toaster position="top-right" richColors theme="system" />}
      >
        {children}
      </WorkspaceShellFrame>
    </VendorAuthContext.Provider>
  );
}

function VendorSidebar({
  user,
  isOpen,
  isMobile,
  onClose,
  onToggle,
  onLogout,
  isActive,
}: {
  user: VendorUser | null;
  isOpen: boolean;
  isMobile: boolean;
  onClose: () => void;
  onToggle: () => void;
  onLogout: () => void;
  isActive: (href: string) => boolean;
}) {
  const mainItems: WorkspaceNavItem[] = navItems.map((item) => ({
    key: item.name,
    name: item.name,
    href: item.href,
    icon: item.icon,
    active: isActive(item.href),
  }));
  const secondaryItems: WorkspaceNavItem[] = user?.role === 'root_admin'
    ? [
        {
          key: 'back-to-admin',
          name: 'Back to Admin',
          href: '/admin/ads',
          icon: ExternalLink,
          active: false,
          tone: 'shortcut',
          badge: 'Admin',
        },
      ]
    : [];

  return (
    <WorkspaceSidebar
      brandHref="/portal/ads"
      navigationLabel="Vendor portal navigation"
      isOpen={isOpen}
      isMobile={isMobile}
      onClose={onClose}
      onToggle={onToggle}
      mainItems={mainItems}
      secondaryItems={secondaryItems}
      secondarySectionLabel="Shortcuts"
      footerAction={{
        label: 'Sign Out',
        ariaLabel: 'Sign out',
        title: 'Sign out',
        onClick: onLogout,
      }}
    />
  );
}

function VendorTopHeader({
  user,
  token,
  onMenuClick,
  onLogout,
}: {
  user: VendorUser | null;
  token: string | null;
  onMenuClick: () => void;
  onLogout: () => void;
}) {
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchUnreadCount = useCallback(async () => {
    if (!token) {
      return 0;
    }

    try {
      const response = await fetch(`${API_BASE}/admin/user/notifications/count`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        cache: 'no-store',
      });

      if (!response.ok) {
        return null;
      }

      const data = await response.json();
      return data.unread || 0;
    } catch {
      // Keep the bell quiet on transient failures.
      return null;
    }
  }, [token]);

  useEffect(() => {
    let cancelled = false;

    const loadUnreadCount = async () => {
      const nextUnreadCount = await fetchUnreadCount();
      if (!cancelled && typeof nextUnreadCount === 'number') {
        setUnreadCount(nextUnreadCount);
      }
    };

    void loadUnreadCount();

    return () => {
      cancelled = true;
    };
  }, [fetchUnreadCount]);

  useEffect(() => {
    const handleNotificationsUpdated = () => {
      void fetchUnreadCount().then((nextUnreadCount) => {
        if (typeof nextUnreadCount === 'number') {
          setUnreadCount(nextUnreadCount);
        }
      });
    };

    window.addEventListener('notifications-updated', handleNotificationsUpdated);
    return () => window.removeEventListener('notifications-updated', handleNotificationsUpdated);
  }, [fetchUnreadCount]);

  return (
    <WorkspaceTopHeader
      onMenuClick={onMenuClick}
      notificationHref="/portal/ads/notifications"
      notificationCount={unreadCount}
      user={{
        name: user?.name || user?.email?.split('@')[0] || 'Vendor',
        email: user?.email,
        initials: user ? getUserInitials(user) : 'VP',
      }}
      menuItems={[
        {
          key: 'settings',
          label: 'Account Settings',
          icon: Settings,
          href: '/portal/ads/settings',
        },
        {
          key: 'logout',
          label: 'Logout',
          icon: LogOut,
          tone: 'danger',
          onSelect: onLogout,
        },
      ]}
    />
  );
}

function getUserInitials(user: VendorUser) {
  const base = user.name || user.email || 'Vendor';
  const parts = base.trim().split(/\s+/).filter(Boolean);

  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }

  return base.slice(0, 2).toUpperCase();
}

// =============================================================================
// Login Page
// =============================================================================

function LoginPage({ onLogin }: { onLogin: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await onLogin(email, password);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <VendorAuthShell
      showcase={(
        <VendorAuthShowcase
          eyebrow="Vendor ads"
          title="Show up like a premium partner, not a pasted listing."
          description="Sign in to manage your campaign creative, business profile, and lead flow inside the same branded workspace the rest of the platform already uses."
          highlights={[
            {
              label: 'Campaigns that look polished',
              description: 'Build creative, swap media, and keep your brand assets aligned without pasting raw URLs into forms.',
            },
            {
              label: 'One place for leads and spend',
              description: 'Track campaigns, incoming leads, and billing from the same workspace your team uses every day.',
            },
          ]}
          stats={[
            { value: 'Shared', caption: 'Media flow across creatives, campaigns, and logo settings' },
            { value: 'Live', caption: 'Lead and campaign visibility from the vendor dashboard' },
          ]}
        />
      )}
    >
      <div className="flex h-full flex-col justify-center">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-wedding-rose/70">Vendor portal</p>
            <h2 className="mt-2 text-[1.75rem] font-semibold leading-tight text-wedding-navy dark:text-white">Welcome back</h2>
            <p className="mt-2 text-[0.95rem] leading-relaxed text-wedding-navy/70 dark:text-slate-300">
              Access your campaigns, creative assets, and profile settings without leaving The Special Wedding ecosystem.
            </p>
          </div>
          <div className="hidden rounded-full bg-white/55 p-4 text-wedding-rose shadow-sm backdrop-blur sm:block dark:bg-slate-800/65">
            <Megaphone className="h-8 w-8" />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
          {error ? (
            <div className="rounded-2xl border border-red-200/70 bg-red-50/80 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
              {error}
            </div>
          ) : null}

          <div className={`${vendorInsetClass} space-y-5 p-5`}>
            <div className="space-y-2">
              <label htmlFor="vendor-email" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                Email address
              </label>
              <input
                id="vendor-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className={vendorInputClass}
                placeholder="vendor@example.com"
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="vendor-password" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                Password
              </label>
              <input
                id="vendor-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className={vendorInputClass}
                placeholder="Enter your password"
                autoComplete="current-password"
              />
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="submit"
              disabled={loading}
              className={`${vendorPrimaryButtonClass} w-full sm:flex-1`}
            >
              {loading ? 'Signing in...' : 'Sign In'}
              {!loading ? <ArrowRight className="h-4 w-4" /> : null}
            </button>
            <Link href="/portal/ads/signup" className={`${vendorSecondaryButtonClass} w-full sm:w-auto`}>
              Register as a vendor
            </Link>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/35 pt-4 text-sm text-wedding-navy/65 dark:border-slate-700/60 dark:text-slate-400">
            <Link href="/vendors" className="transition hover:text-wedding-rose dark:hover:text-primary-300">
              Back to vendor directory
            </Link>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-wedding-sage" />
              <span>Secure vendor access</span>
            </div>
          </div>
        </form>
      </div>
    </VendorAuthShell>
  );
}

// =============================================================================
// Force Password Change Page (first login after admin approval)
// =============================================================================

function ForcePasswordChangePage({
  token,
  userEmail,
  onPasswordChanged,
  onLogout,
}: {
  token: string;
  userEmail: string;
  onPasswordChanged: () => void;
  onLogout: () => void;
}) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (!/[A-Z]/.test(newPassword) || !/[a-z]/.test(newPassword) || !/\d/.test(newPassword) || !/[!@#$%^&*()_+\-\[\]{}|;:,.<>?]/.test(newPassword)) {
      setError('Password must include uppercase, lowercase, number, and special character.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/vendors/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Password change failed.');
      }

      onPasswordChanged();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <VendorAuthShell
      showcase={(
        <VendorAuthShowcase
          eyebrow="First sign-in"
          title="Lock in your vendor account before you start publishing."
          description="Update the temporary password that was sent to your inbox, then continue into the same vendor workspace used for campaigns, billing, and profile management."
          highlights={[
            {
              label: 'Secure the workspace first',
              description: 'Protect your campaigns, leads, and profile assets before you start editing or publishing anything.',
            },
            {
              label: 'One-time setup, then you are in',
              description: 'After this password update, you move straight into the same vendor dashboard used for daily campaign management.',
            },
          ]}
          stats={[
            { value: 'Required', caption: 'Before first access to the vendor workspace' },
            { value: 'Secure', caption: 'Shared auth path with the rest of the platform' },
          ]}
        />
      )}
    >
      <div className="flex h-full flex-col justify-center">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-wedding-rose/70">Account security</p>
            <h2 className="mt-2 text-[1.75rem] font-semibold leading-tight text-wedding-navy dark:text-white">Change your password</h2>
            <p className="mt-2 text-[0.95rem] leading-relaxed text-wedding-navy/70 dark:text-slate-300">
              This is required once before you can access the vendor portal as <span className="font-medium">{userEmail}</span>.
            </p>
          </div>
          <div className="hidden rounded-full bg-white/55 p-4 text-wedding-gold shadow-sm backdrop-blur sm:block dark:bg-slate-800/65">
            <ShieldCheck className="h-8 w-8" />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          {error ? (
            <div className="rounded-2xl border border-red-200/70 bg-red-50/80 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
              {error}
            </div>
          ) : null}

          <div className={`${vendorInsetClass} space-y-5 p-5`}>
            <div className="space-y-2">
              <label htmlFor="vendor-temp-password" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                Temporary password
              </label>
              <input
                id="vendor-temp-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                className={vendorInputClass}
                placeholder="Enter your temporary password"
                autoComplete="current-password"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="vendor-new-password" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                New password
              </label>
              <input
                id="vendor-new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                className={vendorInputClass}
                placeholder="At least 8 characters"
                autoComplete="new-password"
              />
              <p className="flex items-center gap-2 text-xs text-wedding-navy/60 dark:text-slate-400">
                <CheckCircle2 className="h-3.5 w-3.5 text-wedding-sage" />
                Must include uppercase, lowercase, number, and special character.
              </p>
            </div>

            <div className="space-y-2">
              <label htmlFor="vendor-confirm-password" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                Confirm new password
              </label>
              <input
                id="vendor-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className={vendorInputClass}
                placeholder="Repeat your new password"
                autoComplete="new-password"
              />
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button type="submit" disabled={loading} className={`${vendorPrimaryButtonClass} w-full sm:flex-1`}>
              {loading ? 'Changing Password...' : 'Change Password & Continue'}
              {!loading ? <ArrowRight className="h-4 w-4" /> : null}
            </button>
            <button type="button" onClick={onLogout} className={`${vendorSecondaryButtonClass} w-full sm:w-auto`}>
              Sign Out
            </button>
          </div>
        </form>
      </div>
    </VendorAuthShell>
  );
}
