'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X } from 'lucide-react';

const NAV_LINKS = [
  { href: '/', label: 'Home' },
  { href: '/features', label: 'Features' },
  { href: '/resources', label: 'Resources' },
  { href: '/vendors', label: 'Vendors' },
];

export default function SaasNav() {
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setMobileOpen(false);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [pathname]);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-slate-950/85 backdrop-blur-lg border-b border-white/8 shadow-lg shadow-black/20'
          : 'bg-transparent'
      }`}
    >
      <div className="w-full px-4 sm:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo / Brand — left-aligned */}
          <Link href="/" className="flex items-center group flex-shrink-0">
            <Image
              src="/logo.svg"
              alt="The Special Wedding"
              width={160}
              height={40}
              className="block shrink-0"
              priority
            />
          </Link>

          {/* Nav + CTA — all right-aligned */}
          <div className="flex items-center gap-1">
            <nav className="hidden md:flex items-center gap-1">
              {NAV_LINKS.map((link) => {
                const isActive =
                  link.href === '/'
                    ? pathname === '/'
                    : pathname.startsWith(link.href);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`px-3.5 py-2 rounded-lg text-sm font-medium transition ${
                      isActive
                        ? 'text-white bg-white/10'
                        : 'text-slate-400 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>

            <div className="hidden md:block w-px h-5 bg-white/10 mx-2" />

            <Link
              href="/admin/login"
              className="hidden md:inline-flex text-sm font-medium text-slate-300 hover:text-white transition px-3 py-2"
            >
              Sign in
            </Link>
            <Link
              href="/#pricing"
              className="hidden md:inline-flex items-center rounded-full bg-wedding-rose px-4 py-2 text-sm font-semibold text-slate-900 shadow-md shadow-wedding-rose/30 transition hover:bg-wedding-blush"
            >
              Start Free Trial
            </Link>

            {/* Mobile hamburger */}
            <button
              type="button"
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition"
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden bg-slate-950/95 backdrop-blur-lg border-t border-white/8">
          <div className="px-6 py-4 space-y-1">
            {NAV_LINKS.map((link) => {
              const isActive =
                link.href === '/'
                  ? pathname === '/'
                  : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`block px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                    isActive
                      ? 'text-white bg-white/10'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
            <div className="pt-3 border-t border-white/5 mt-3 flex flex-col gap-2">
              <Link
                href="/admin/login"
                className="px-3 py-2.5 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-white/5 transition"
              >
                Sign in
              </Link>
              <Link
                href="/#pricing"
                className="flex items-center justify-center rounded-full bg-wedding-rose px-4 py-2.5 text-sm font-semibold text-slate-900 shadow-md shadow-wedding-rose/30 transition hover:bg-wedding-blush"
              >
                Start Free Trial
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
