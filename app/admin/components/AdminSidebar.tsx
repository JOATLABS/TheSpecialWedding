'use client';

import { useAdmin } from '@/contexts/AdminContext';
import { useDarkMode } from '@/contexts/DarkModeContext';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useState, useEffect } from 'react';

interface AdminSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AdminSidebar({ isOpen, onClose }: AdminSidebarProps) {
  const { logout, userProfile, fetchUserProfile, isAuthenticated, token } = useAdmin();
  const { isDarkMode, toggleDarkMode } = useDarkMode();
  const pathname = usePathname();
  const isLoginPage = pathname === '/admin/login';

  // Security: Fetch user profile if authenticated but profile missing
  useEffect(() => {
    if (!userProfile && isAuthenticated && token) {
      fetchUserProfile();
    }
  }, [userProfile, fetchUserProfile, isAuthenticated, token]);

  // Security: Don't render sidebar on login page
  if (isLoginPage) return null;

  // Security: Role-based navigation links (PRESERVED from AdminHeader)
  const getNavLinks = () => {
    if (!userProfile) return [];

    const baseLinks = [
      { href: '/admin', label: 'Dashboard', roles: ['ROOT_ADMIN', 'admin', 'wedding_planner', 'vendor'], icon: '🏠' }
    ];

    if (userProfile.is_root_admin) {
      return [
        ...baseLinks,
        { href: '/admin/saas', label: 'Platform Management', roles: ['ROOT_ADMIN'], icon: '⚙️' },
        { href: '/admin/metrics', label: 'Platform Metrics', roles: ['ROOT_ADMIN'], icon: '📊' },
        { href: '/admin/notifications', label: 'Notifications', roles: ['ROOT_ADMIN'], icon: '🔔' },
        { href: '/admin/support', label: 'Support', roles: ['ROOT_ADMIN'], icon: '🎧' },
      ];
    } else if (userProfile.is_wedding_planner) {
      return [
        ...baseLinks,
        { href: '/admin/weddings', label: 'My Weddings', roles: ['wedding_planner'], icon: '💍' },
        { href: '/admin/budget', label: 'Budget', roles: ['wedding_planner'], icon: '💰' },
        { href: '/admin/forms', label: 'Forms', roles: ['wedding_planner'], icon: '📝' },
        { href: '/admin/gallery/upload', label: 'Gallery', roles: ['wedding_planner'], icon: '📸' },
        { href: '/admin/guests', label: 'Guests', roles: ['wedding_planner'], icon: '👥' },
        { href: '/admin/reminders', label: 'Reminders', roles: ['wedding_planner'], icon: '⏰' },
        { href: '/admin/profile', label: 'Profile', roles: ['wedding_planner'], icon: '👤' },
      ];
    } else if (userProfile.is_vendor) {
      return [
        ...baseLinks,
        { href: '/admin/vendor', label: 'My Tasks', roles: ['vendor'], icon: '📋' },
      ];
    }

    return baseLinks;
  };

  const navLinks = getNavLinks();

  // Security: Secure logout function (PRESERVED)
  const handleLogout = () => {
    logout();
    onClose(); // Auto-close sidebar
  };

  // Auto-close sidebar when navigation item is clicked
  const handleNavClick = () => {
    onClose();
  };

  // Get role-based title
  const getRoleTitle = () => {
    if (!userProfile) return 'Admin Panel';
    if (userProfile.is_root_admin) return 'Admin Panel';
    if (userProfile.is_wedding_planner) return 'Wedding Planner';
    if (userProfile.is_vendor) return 'Vendor Portal';
    return 'Admin Panel';
  };

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-64 bg-white dark:bg-gray-800 shadow-xl z-50 transform transition-transform duration-300 ease-in-out flex flex-col
        ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto
      `}>
        {/* Header */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-heading text-xl text-wedding-rose dark:text-wedding-rose">
                {getRoleTitle()}
              </h1>
              {userProfile && (
                <p className="text-sm text-gray-600 dark:text-gray-400 truncate">
                  {userProfile.user_data?.company_name || userProfile.email}
                </p>
              )}
            </div>
            {/* Close button for mobile */}
            <button
              onClick={onClose}
              className="lg:hidden p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition"
              aria-label="Close sidebar"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-2">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={handleNavClick}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-lg transition font-medium
                  ${isActive
                    ? 'bg-wedding-rose text-white'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }
                `}
              >
                <span className="text-lg">{link.icon}</span>
                <span>{link.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Footer with Settings & Logout */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 space-y-2">
          {/* Dark Mode Toggle */}
          <button
            onClick={toggleDarkMode}
            className="w-full flex items-center gap-3 px-4 py-3 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition font-medium"
          >
            <span className="text-lg">{isDarkMode ? '☀️' : '🌙'}</span>
            <span>{isDarkMode ? 'Light Mode' : 'Dark Mode'}</span>
          </button>

          {/* Logout Button */}
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition font-medium"
          >
            <span className="text-lg">🚪</span>
            <span>Logout</span>
          </button>
        </div>
      </aside>
    </>
  );
}