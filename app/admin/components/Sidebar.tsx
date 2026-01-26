'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAdmin } from '@/contexts/AdminContext';
import {
  LayoutDashboard,
  Users,
  Wallet,
  Settings,
  LogOut,
  ChevronLeft,
  Heart,
  Bell,
  FileText,
  Store,
  HelpCircle,
  X,
  CreditCard,
  Layers,
  TrendingUp,
  Server,
  Calendar,
  Image,
  Package,
  type LucideIcon
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  isMobile: boolean;
}

interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  adminOnly?: boolean;
  plannerOnly?: boolean;
}

// Navigation items for Root Admin/Developer (platform-level management only)
const adminNavItems: NavItem[] = [
  { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
  { name: 'Business Analytics', href: '/admin/metrics', icon: TrendingUp },
  { name: 'Platform', href: '/admin/platform', icon: Server },
  { name: 'SaaS Management', href: '/admin/saas', icon: Layers },
  { name: 'Planners', href: '/admin/users', icon: Users },
  { name: 'Billing', href: '/admin/billing', icon: CreditCard },
  { name: 'Notifications', href: '/admin/notifications', icon: Bell },
  { name: 'Support', href: '/admin/support', icon: HelpCircle },
];

// Navigation items for Wedding Planners
const plannerNavItems: NavItem[] = [
  { name: 'Dashboard', href: '/admin/planner', icon: LayoutDashboard },
  { name: 'Calendar', href: '/admin/planner/calendar', icon: Calendar },
  { name: 'Weddings', href: '/admin/weddings', icon: Heart },
  { name: 'Packages', href: '/admin/packages', icon: Package },
  { name: 'Guests', href: '/admin/guests', icon: Users },
  { name: 'Gallery', href: '/admin/gallery/upload', icon: Image },
  { name: 'Budget', href: '/admin/budget', icon: Wallet },
  { name: 'Money', href: '/admin/money', icon: CreditCard },
  { name: 'Forms', href: '/admin/forms', icon: FileText },
  { name: 'Vendors', href: '/admin/vendors', icon: Store },
  { name: 'Reminders', href: '/admin/reminders', icon: Bell },
  { name: 'Notifications', href: '/admin/notifications', icon: Bell },
  { name: 'Settings', href: '/admin/profile', icon: Settings },
  { name: 'Support', href: '/admin/support', icon: HelpCircle },
];

export default function Sidebar({ isOpen, setIsOpen, isMobile }: SidebarProps) {
  const pathname = usePathname();
  const { userProfile, logout } = useAdmin();

  const isActive = (href: string) => {
    if (href === '/admin' && pathname === '/admin') return true;
    if (href !== '/admin' && pathname.startsWith(href)) return true;
    return false;
  };

  // Determine which navigation items to show based on user role
  const getNavItems = (): NavItem[] => {
    if (!userProfile) return [];

    // Root admin/developer gets admin navigation
    if (userProfile.is_root_admin) {
      return adminNavItems;
    }

    // Wedding planner gets planner navigation
    if (userProfile.is_wedding_planner) {
      return plannerNavItems;
    }

    // Default to planner navigation for other roles
    return plannerNavItems;
  };

  const filteredNavItems = getNavItems();

  const sidebarVariants = {
    open: { width: '18rem' },
    closed: { width: '5rem' }
  };

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isMobile && isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={isOpen ? 'open' : 'closed'}
        variants={sidebarVariants}
        className={`
          fixed top-0 left-0 z-50 h-screen
          bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl
          border-r border-slate-200/50 dark:border-slate-700/50
          flex flex-col
          transition-all duration-300 ease-[cubic-bezier(0.25,0.1,0.25,1)]
          ${isMobile ? (isOpen ? 'translate-x-0' : '-translate-x-full') : ''}
        `}
      >
        {/* Logo Section */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-slate-200/50 dark:border-slate-700/50">
          <Link href="/admin/planner" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-secondary-500 flex items-center justify-center">
              <Heart className="w-5 h-5 text-white" />
            </div>
            {isOpen && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="font-heading font-bold text-lg text-slate-800 dark:text-white"
              >
                WeddingApp
              </motion.span>
            )}
          </Link>

          {isMobile ? (
            <button onClick={() => setIsOpen(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg">
              <X size={20} />
            </button>
          ) : (
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            >
              <ChevronLeft className={`w-5 h-5 transition-transform ${!isOpen ? 'rotate-180' : ''}`} />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {filteredNavItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => isMobile && setIsOpen(false)}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-xl
                  transition-all duration-200
                  ${active
                    ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }
                `}
              >
                <Icon size={20} className={active ? 'text-primary-500' : ''} />
                {isOpen && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="font-medium text-sm whitespace-nowrap"
                  >
                    {item.name}
                  </motion.span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* User Section */}
        <div className="p-3 border-t border-slate-200/50 dark:border-slate-700/50">
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 transition-colors"
          >
            <LogOut size={20} />
            {isOpen && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="font-medium text-sm"
              >
                Logout
              </motion.span>
            )}
          </button>
        </div>
      </motion.aside>
    </>
  );
}
