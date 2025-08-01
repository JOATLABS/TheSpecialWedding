'use client';

import { useAdmin } from '@/contexts/AdminContext';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useState } from 'react';

export default function AdminHeader() {
  const { logout } = useAdmin();
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isLoginPage = pathname === '/admin/login';

  if (isLoginPage) return null;

  const navLinks = [
    { href: '/admin/weddings', label: 'Weddings' },
    { href: '/admin/gallery/upload', label: 'Gallery' },
    { href: '/admin/import', label: 'Import Guests' },
    { href: '/admin/guests', label: 'Manage Guests' },
    { href: '/admin/reminders', label: 'SMS Reminders' },
  ];

  return (
    <>
      <header className="glass px-4 sm:px-6 md:px-8 py-3 sm:py-4 flex items-center justify-between relative">
        <h1 className="font-heading text-xl sm:text-2xl text-wedding-rose">
          Admin Panel
        </h1>
        
        {/* Desktop Navigation */}
        <nav className="hidden lg:flex space-x-4 xl:space-x-6 font-medium">
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
          >
            Logout
          </button>
        </nav>

        {/* Mobile Menu Button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="lg:hidden p-2 rounded-lg hover:bg-white/10 transition"
          aria-label="Toggle menu"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
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
        <div className="lg:hidden glass border-t border-white/10">
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