'use client';

import { useAdmin } from '@/contexts/AdminContext';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useState, useEffect } from 'react';

export default function AdminHeader() {
  const { logout, userProfile, fetchUserProfile, isAuthenticated, token } = useAdmin();
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isLoginPage = pathname === '/admin/login';

  useEffect(() => {
    if (!userProfile && isAuthenticated && token) {
      fetchUserProfile();
    }
  }, [userProfile, fetchUserProfile, isAuthenticated, token]);

  if (isLoginPage) return null;

  // Role-based navigation links
  const getNavLinks = () => {
    if (!userProfile) return [];

    const baseLinks = [
      { href: '/admin', label: 'Dashboard', roles: ['ROOT_ADMIN', 'wedding_planner', 'vendor'] }
    ];

    if (userProfile.is_root_admin) {
      return [
        ...baseLinks,
        { href: '/admin/saas', label: 'Platform Management', roles: ['ROOT_ADMIN'] },
        { href: '/admin/metrics', label: 'Platform Metrics', roles: ['ROOT_ADMIN'] },
        { href: '/admin/notifications', label: 'Notifications', roles: ['ROOT_ADMIN'] },
        { href: '/admin/support', label: 'Support', roles: ['ROOT_ADMIN'] },
      ];
    } else if (userProfile.is_wedding_planner) {
      return [
        ...baseLinks,
        { href: '/admin/weddings', label: 'My Weddings', roles: ['wedding_planner'] },
        { href: '/admin/budget', label: 'Budget', roles: ['wedding_planner'] },
        { href: '/admin/forms', label: 'Forms', roles: ['wedding_planner'] },
        { href: '/admin/gallery/upload', label: 'Gallery', roles: ['wedding_planner'] },
        { href: '/admin/guests', label: 'Guests', roles: ['wedding_planner'] },
        { href: '/admin/reminders', label: 'Reminders', roles: ['wedding_planner'] },
        { href: '/admin/profile', label: 'Profile', roles: ['wedding_planner'] },
      ];
    } else if (userProfile.is_vendor) {
      return [
        ...baseLinks,
        { href: '/admin/vendor', label: 'My Tasks', roles: ['vendor'] },
        { href: '/admin/vendor/ads', label: 'Advertising', roles: ['vendor'] },
      ];
    }

    return baseLinks;
  };

  const navLinks = getNavLinks();

  return (
    <>
      <header className="glass px-4 sm:px-6 md:px-8 py-3 sm:py-4 flex items-center justify-between relative" role="banner">
        <div>
          <h1 className="font-heading text-xl sm:text-2xl text-wedding-rose">
            {userProfile?.is_root_admin ? 'Admin Panel' :
             userProfile?.is_wedding_planner ? 'Wedding Planner' :
             userProfile?.is_vendor ? 'Vendor Portal' : 'Admin Panel'}
          </h1>
          {userProfile && (
            <p className="text-sm text-gray-600">
              {userProfile.user_data?.company_name || userProfile.email}
            </p>
          )}
        </div>

        {/* Desktop Navigation */}
        <nav className="hidden lg:flex space-x-4 xl:space-x-6 font-medium" aria-label="Main navigation">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="hover:text-wedding-gold transition"
            >
              {link.label}
            </Link>
          ))}
          <button
            onClick={logout}
            className="text-red-500 hover:underline"
            aria-label="Logout from account"
          >
            Logout
          </button>
        </nav>

        {/* Mobile Menu Button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="lg:hidden p-2 rounded-lg hover:bg-white/10 transition"
          aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={mobileMenuOpen}
          aria-controls="mobile-nav-menu"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            {mobileMenuOpen ? (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            ) : (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            )}
          </svg>
        </button>
      </header>

      {/* Mobile Navigation Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden glass border-t border-white/10" id="mobile-nav-menu" role="navigation" aria-label="Mobile navigation">
          <nav className="flex flex-col px-4 py-2 font-medium">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="py-3 px-2 hover:bg-white/10 rounded-lg transition"
                onClick={() => setMobileMenuOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            <button
              onClick={() => {
                logout();
                setMobileMenuOpen(false);
              }}
              className="py-3 px-2 text-red-500 hover:bg-white/10 rounded-lg transition text-left"
            >
              Logout
            </button>
          </nav>
        </div>
      )}
    </>
  );
}