'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import NextImage from 'next/image';
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
  Menu,
  X,
  ChevronLeft,
  Sun,
  Moon,
  Bell,
  ExternalLink,
  ArrowRight,
  CheckCircle2,
  ShieldCheck,
} from 'lucide-react';
import { ThemeProvider, useTheme } from '@/contexts/ThemeContext';
import { Toaster } from 'sonner';
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

function clearLegacyVendorPortalStorage() {
  if (typeof window === 'undefined') {
    return;
  }

  localStorage.removeItem('vendor_ad_token');
  localStorage.removeItem('vendor_ad_user');
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
  const isPublicPage = pathname === '/portal/ads/signup';
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<VendorUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const bootstrapVendorSession = async () => {
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
          setUser({
            _id: profile._id || profile.id || '',
            email: profile.email || '',
            name: profile.business_name || profile.company_name || profile.email || 'Advertising Vendor',
            role: profile.is_root_admin ? 'root_admin' : (profile.role || 'advertising_vendor'),
            must_change_password: profile.must_change_password || false,
          });
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
  }, []);

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      setSidebarOpen(!mobile);
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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
    const vendorUser: VendorUser = {
      _id: profile._id || profile.id || '',
      email: profile.email || email,
      name: profile.business_name || profile.company_name || email,
      role: profile.role || 'advertising_vendor',
      must_change_password: profile.must_change_password || false,
    };
    setUser(vendorUser);
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
          <PortalBackground />
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
        <PortalBackground />
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
      <div className="min-h-screen overflow-x-hidden bg-light-bg text-light-text transition-colors duration-300 dark:bg-dark-bg dark:text-dark-text">
        <PortalBackground />

        <VendorSidebar
          user={user}
          isOpen={sidebarOpen}
          isMobile={isMobile}
          onClose={() => setSidebarOpen(false)}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          onLogout={logout}
          isActive={isActive}
        />

        <div
          className="relative z-10 flex min-h-screen flex-col transition-[margin] duration-300 ease-out"
          style={{ marginLeft: !isMobile ? (sidebarOpen ? '18rem' : '5rem') : '0' }}
        >
          <VendorTopHeader
            user={user}
            onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          />

          <main className="flex-1 overflow-x-hidden p-4 sm:p-6 lg:p-8">
            {children}
          </main>
        </div>
      </div>
      <Toaster position="top-right" richColors theme="system" />
    </VendorAuthContext.Provider>
  );
}

function PortalBackground() {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden opacity-40 dark:opacity-20" aria-hidden="true">
      <div className="absolute left-[-10%] top-[-10%] h-[40%] w-[40%] rounded-full bg-primary-400/30 blur-[100px] animate-float" />
      <div
        className="absolute bottom-[-10%] right-[-10%] h-[40%] w-[40%] rounded-full bg-secondary-400/30 blur-[100px] animate-float"
        style={{ animationDelay: '-3s' }}
      />
    </div>
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
  return (
    <>
      {isMobile && isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/50 transition-opacity duration-200 lg:hidden"
          aria-hidden="true"
        />
      )}

      <aside
        className={`
          fixed left-0 top-0 z-50 flex h-screen flex-col border-r border-slate-200/50 bg-white/80 backdrop-blur-xl transition-[width,transform] duration-300 ease-out dark:border-slate-700/50 dark:bg-slate-900/80
          ${isMobile ? (isOpen ? 'translate-x-0' : '-translate-x-full') : ''}
        `}
        style={{ width: isOpen ? '18rem' : '5rem' }}
        role="navigation"
        aria-label="Vendor portal navigation"
      >
        <div className="flex h-16 items-center justify-between border-b border-slate-200/50 px-3 dark:border-slate-700/50">
          <Link href="/portal/ads" className="mr-2 flex min-w-0 flex-1 items-center">
            {isOpen ? (
              <div className="flex items-center gap-3">
                <img
                  src="/logo.svg"
                  alt="The Special Wedding"
                  width={144}
                  height={36}
                  className="block shrink-0"
                />
                <span className="rounded-full border border-primary-200 bg-primary-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-primary-600 dark:border-primary-800 dark:bg-primary-900/20 dark:text-primary-300">
                  Ads
                </span>
              </div>
            ) : (
              <NextImage
                src="/favicon.svg"
                alt="The Special Wedding"
                width={32}
                height={32}
                className="h-8 w-8"
                priority
              />
            )}
          </Link>

          {isMobile ? (
            <button
              onClick={onClose}
              className="rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Close sidebar"
            >
              <X size={20} />
            </button>
          ) : (
            <button
              onClick={onToggle}
              className="rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
              aria-expanded={isOpen}
            >
              <ChevronLeft className={`h-5 w-5 transition-transform ${!isOpen ? 'rotate-180' : ''}`} />
            </button>
          )}
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label="Vendor portal pages">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => isMobile && onClose()}
                className={`
                  flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors duration-200
                  ${active
                    ? 'bg-primary-50 text-primary-600 dark:bg-primary-900/20 dark:text-primary-400'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                  }
                `}
                aria-current={active ? 'page' : undefined}
                title={!isOpen ? item.name : undefined}
              >
                <Icon size={20} className={active ? 'text-primary-500' : ''} aria-hidden="true" />
                {isOpen && (
                  <span className="flex-1 overflow-hidden whitespace-nowrap text-sm font-medium text-left">
                    {item.name}
                  </span>
                )}
              </Link>
            );
          })}

          {user?.role === 'root_admin' && isOpen && (
            <>
              <p className="px-3 pt-4 pb-1 text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Shortcuts
              </p>
              <Link
                href="/admin/ads"
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-wedding-gold transition-colors duration-200 hover:bg-amber-50 dark:hover:bg-amber-900/10"
              >
                <ExternalLink size={20} className="text-wedding-gold" aria-hidden="true" />
                <span className="text-sm font-medium">Back to Admin</span>
                <span className="ml-auto rounded bg-wedding-gold px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wide text-slate-900">
                  Admin
                </span>
              </Link>
            </>
          )}
        </nav>

        <div className="border-t border-slate-200/50 p-3 dark:border-slate-700/50">
          {isOpen && user && (
            <div className="mb-2 rounded-xl border border-white/40 bg-white/50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800/60">
              <p className="truncate text-sm font-medium text-slate-900 dark:text-white">{user.name}</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user.email}</p>
            </div>
          )}
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-900/20 dark:hover:text-red-400"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut size={20} aria-hidden="true" />
            {isOpen && <span className="text-sm font-medium">Sign Out</span>}
          </button>
        </div>
      </aside>
    </>
  );
}

function VendorTopHeader({
  user,
  onMenuClick,
}: {
  user: VendorUser | null;
  onMenuClick: () => void;
}) {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/50 bg-white/80 backdrop-blur-xl dark:border-slate-700/50 dark:bg-slate-900/80" role="banner">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800 lg:hidden"
            aria-label="Toggle navigation menu"
          >
            <Menu size={20} className="text-slate-600 dark:text-slate-400" aria-hidden="true" />
          </button>

          <div className="hidden sm:block">
            <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-primary-500/80 dark:text-primary-300/80">
              Ad Platform
            </p>
            <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
              Vendor Portal
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
            className="rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
            title={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {resolvedTheme === 'dark' ? (
              <Sun size={20} className="text-amber-500" aria-hidden="true" />
            ) : (
              <Moon size={20} className="text-slate-600" aria-hidden="true" />
            )}
          </button>

          <Link
            href="/portal/ads/notifications"
            className="rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Open notifications"
            title="Notifications"
          >
            <Bell size={20} className="text-slate-600 dark:text-slate-400" aria-hidden="true" />
          </Link>

          {user && (
            <div className="ml-1 hidden items-center gap-3 rounded-xl border border-white/40 bg-white/60 px-3 py-2 dark:border-slate-700 dark:bg-slate-800/60 sm:flex">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-primary-400 to-secondary-400 text-sm font-semibold text-white">
                {getUserInitials(user)}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900 dark:text-white">{user.name}</p>
                <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                  {user.role === 'root_admin' ? 'Root Admin' : 'Advertising Vendor'}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
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
