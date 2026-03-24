'use client';

import React, { useState, useEffect, createContext, useContext, useCallback } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
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
} from 'lucide-react';
import { ThemeProvider, useTheme } from '@/contexts/ThemeContext';

const API_BASE = getApiBaseUrl();

// =============================================================================
// Vendor Auth Context
// =============================================================================

interface VendorUser {
  _id: string;
  email: string;
  name: string;
  role: string;
  must_change_password?: boolean;
}

interface VendorAuthContextType {
  token: string | null;
  user: VendorUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const VendorAuthContext = createContext<VendorAuthContextType>({
  token: null,
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

export function useVendorAuth() {
  return useContext(VendorAuthContext);
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
  const router = useRouter();
  const { setTheme, resolvedTheme } = useTheme();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<VendorUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Check for stored token on mount — vendor token first, then fall back to admin token
  useEffect(() => {
    if (typeof window === 'undefined') {
      setLoading(false);
      return;
    }

    const storedVendorToken = localStorage.getItem('vendor_ad_token');
    const storedAdminToken = localStorage.getItem('admin_token')
      || sessionStorage.getItem('admin_token');

    // 1. Try vendor-specific token first
    if (storedVendorToken) {
      setToken(storedVendorToken);
      fetch(`${API_BASE}/portal/ads/billing`, {
        headers: { Authorization: `Bearer ${storedVendorToken}` },
      })
        .then((res) => {
          if (res.ok) {
            const storedUser = localStorage.getItem('vendor_ad_user');
            if (storedUser) {
              setUser(JSON.parse(storedUser));
            }
          } else {
            localStorage.removeItem('vendor_ad_token');
            localStorage.removeItem('vendor_ad_user');
            setToken(null);
            setUser(null);
          }
        })
        .catch(() => {})
        .finally(() => setLoading(false));
      return;
    }

    // 2. Fall back to admin token — root admin can access vendor portal directly
    if (storedAdminToken) {
      fetch(`${API_BASE}/admin/profile`, {
        headers: { Authorization: `Bearer ${storedAdminToken}` },
      })
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((profile) => {
          if (profile.is_root_admin) {
            setToken(storedAdminToken);
            setUser({
              _id: profile._id || profile.id || '',
              email: profile.email || '',
              name: profile.company_name || profile.email || 'Root Admin',
              role: 'root_admin',
            });
          }
        })
        .catch(() => {
          // Admin token invalid or not root admin — fall through to login
        })
        .finally(() => setLoading(false));
      return;
    }

    setLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    // Uses the same /admin/token endpoint as AdminContext — it's role-agnostic
    const response = await fetch(`${API_BASE}/admin/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
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
    });

    if (!profileRes.ok) {
      throw new Error('Failed to verify account');
    }

    const profile = await profileRes.json();

    // Only allow advertising_vendor or root_admin into the vendor portal
    if (!profile.is_root_admin && profile.role !== 'advertising_vendor') {
      throw new Error('This portal is for advertising vendors only');
    }

    setToken(accessToken);
    const vendorUser: VendorUser = {
      _id: profile._id || profile.id || '',
      email: profile.email || email,
      name: profile.business_name || profile.company_name || email,
      role: profile.role || 'advertising_vendor',
      must_change_password: profile.must_change_password || false,
    };
    setUser(vendorUser);
    localStorage.setItem('vendor_ad_token', accessToken);
    localStorage.setItem('vendor_ad_user', JSON.stringify(vendorUser));
  };

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('vendor_ad_token');
    localStorage.removeItem('vendor_ad_user');
  }, []);

  const isActive = (href: string) => {
    if (href === '/portal/ads') return pathname === '/portal/ads';
    return pathname.startsWith(href);
  };

  const authValue = { token, user, loading, login, logout };

  // Show login if not authenticated
  if (!loading && !token) {
    return (
      <VendorAuthContext.Provider value={authValue}>
        <LoginPage onLogin={login} />
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
            localStorage.setItem('vendor_ad_user', JSON.stringify(updated));
          }}
          onLogout={logout}
        />
      </VendorAuthContext.Provider>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <VendorAuthContext.Provider value={authValue}>
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex">
        {/* Mobile Sidebar Overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={`
            fixed top-0 left-0 z-50 h-screen w-64
            bg-white dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700
            flex flex-col transition-transform duration-300
            lg:translate-x-0 lg:static
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          `}
        >
          {/* Logo */}
          <div className="h-16 flex items-center justify-between px-4 border-b border-slate-200 dark:border-slate-700">
            <Link href="/portal/ads" className="flex items-center gap-2">
              <Megaphone size={24} className="text-primary-500" />
              <span className="text-lg font-semibold text-slate-900 dark:text-white">Ad Portal</span>
            </Link>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
            >
              <X size={20} />
            </button>
          </div>

          {/* Admin mode indicator */}
          {user?.role === 'root_admin' && (
            <div className="mx-3 mt-3 px-3 py-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">Admin Mode</p>
              <Link
                href="/admin/ads"
                className="text-xs text-amber-700 dark:text-amber-300 hover:underline"
              >
                ← Back to Admin
              </Link>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`
                    flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors
                    ${active
                      ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400'
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
                    }
                  `}
                >
                  <Icon size={20} />
                  {item.name}
                </Link>
              );
            })}
          </nav>

          {/* User / Logout */}
          <div className="p-3 border-t border-slate-200 dark:border-slate-700">
            {user && (
              <div className="px-3 py-2 mb-2">
                <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{user.name}</p>
                <p className="text-xs text-slate-500 truncate">{user.email}</p>
              </div>
            )}
            <button
              onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
              className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-sm"
              aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
            >
              {resolvedTheme === 'dark' ? <Sun size={20} className="text-amber-500" /> : <Moon size={20} />}
              {resolvedTheme === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </button>
            <button
              onClick={logout}
              className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 transition-colors text-sm"
            >
              <LogOut size={20} />
              Logout
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1 min-w-0">
          {/* Mobile Header */}
          <div className="lg:hidden h-16 flex items-center px-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg mr-3"
            >
              <Menu size={20} />
            </button>
            <span className="text-lg font-semibold text-slate-900 dark:text-white flex-1">Ad Portal</span>
            <button
              onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
              aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
            >
              {resolvedTheme === 'dark' ? <Sun size={20} className="text-amber-500" /> : <Moon size={20} className="text-slate-600" />}
            </button>
          </div>

          {/* Page Content */}
          <main className="p-4 sm:p-6 lg:p-8">
            {children}
          </main>
        </div>
      </div>
    </VendorAuthContext.Provider>
  );
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Megaphone size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Vendor Ad Portal</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Manage your advertising campaigns on The Special Wedding
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 space-y-4">
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm p-3 rounded-lg">
              {error}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="vendor@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Enter your password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-primary-500 hover:bg-primary-600 text-white font-medium rounded-lg transition-colors disabled:opacity-50 text-sm"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
          <p className="text-center text-xs text-slate-500 dark:text-slate-400">
            Don&apos;t have an account?{' '}
            <a href="/portal/ads/signup" className="text-primary-500 hover:underline">
              Register as a vendor
            </a>
          </p>
        </form>
      </div>
    </div>
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-amber-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Change Your Password</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            You must change your temporary password before accessing the portal.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 space-y-4">
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm p-3 rounded-lg">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
              Temporary Password
            </label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Enter your temporary password"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
              New Password
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="At least 8 characters"
            />
            <p className="text-xs text-slate-400 mt-1">
              Must include uppercase, lowercase, number, and special character.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
              Confirm New Password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Re-enter new password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-medium rounded-lg transition-colors disabled:opacity-50 text-sm"
          >
            {loading ? 'Changing Password...' : 'Change Password & Continue'}
          </button>

          <button
            type="button"
            onClick={onLogout}
            className="w-full py-2 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
          >
            Sign Out
          </button>
        </form>
      </div>
    </div>
  );
}
