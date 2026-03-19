'use client';

import React from 'react';
import Link from 'next/link';
import NextImage from 'next/image';
import { usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import {
  LayoutDashboard,
  Users,
  UserPlus,
  Wallet,
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
  LayoutGrid,
  Mail,
  Megaphone,
  ShieldCheck,
  BarChart3,
  Trophy,
  Settings,
  Target,
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
  // Advertising section -- each is a standalone page per mockup
  { name: 'Creative Review', href: '/admin/ads/creative-review', icon: ShieldCheck },
  { name: 'All Campaigns', href: '/admin/advertising', icon: Megaphone },
  { name: 'Performance', href: '/admin/ads/performance', icon: BarChart3 },
  { name: 'Ad Config', href: '/admin/ads/config', icon: Settings },
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
  { name: 'Inbox', href: '/admin/inbox', icon: Mail },
  { name: 'Gallery', href: '/admin/gallery/upload', icon: Image },
  { name: 'Budget', href: '/admin/budget', icon: Wallet },
  { name: 'Money', href: '/admin/money', icon: CreditCard },
  { name: 'Forms', href: '/admin/forms', icon: FileText },
  { name: 'Vendors', href: '/admin/vendors', icon: Store },
  { name: 'Reminders', href: '/admin/reminders', icon: Bell },
  { name: 'Notifications', href: '/admin/notifications', icon: Bell },
  { name: 'Seating', href: '/admin/seating', icon: LayoutGrid },
  { name: 'Team', href: '/admin/planner/team', icon: UserPlus, plannerOnly: true },
  { name: 'Support', href: '/admin/support', icon: HelpCircle },
];

export default function Sidebar({ isOpen, setIsOpen, isMobile }: SidebarProps) {
  const pathname = usePathname();
  const { userProfile, logout } = useAdmin();

  const isActive = (href: string) => {
    // Exact match for root admin and planner dashboard
    if (href === '/admin' || href === '/admin/planner') return pathname === href;
    // Prefix match for all other pages
    if (pathname.startsWith(href)) return true;
    return false;
  };

  // Map permissions to nav item names for team member filtering
  const permissionNavMap: Record<string, string[]> = {
    manage_guests: ['Guests'],
    manage_budget: ['Budget'],
    manage_gallery: ['Gallery'],
    manage_seating: ['Seating'],
    manage_vendors: ['Vendors'],
    manage_forms: ['Forms'],
    manage_contracts: ['Vendors'],
    manage_packages: ['Packages'],
    send_rsvp: ['Guests'],
    send_reminders: ['Reminders'],
    view_analytics: [],
    manage_wedding_settings: ['Weddings'],
  };

  // Determine which navigation items to show based on user role
  const getNavItems = (): NavItem[] => {
    if (!userProfile) return [];

    // Root admin/developer gets admin navigation
    if (userProfile.is_root_admin) {
      return adminNavItems;
    }

    // Wedding planner gets full planner navigation
    if (userProfile.is_wedding_planner) {
      return plannerNavItems;
    }

    // Team members get filtered navigation based on their permissions
    if (userProfile.is_team_member && userProfile.team_permissions) {
      const allowedNavNames = new Set(['Dashboard', 'Calendar', 'Notifications', 'Inbox', 'Support']);
      const perms = userProfile.team_permissions;

      for (const [permKey, navNames] of Object.entries(permissionNavMap)) {
        if (perms[permKey]) {
          navNames.forEach((name) => allowedNavNames.add(name));
        }
      }

      return plannerNavItems.filter(
        (item) => !item.plannerOnly && allowedNavNames.has(item.name)
      );
    }

    // Default to planner navigation for other roles
    return plannerNavItems;
  };

  const filteredNavItems = getNavItems();

  return (
    <>
      {/* Mobile overlay */}
      {isMobile && isOpen && (
        <div
          onClick={() => setIsOpen(false)}
          className="fixed inset-0 bg-black/50 z-40 lg:hidden transition-opacity duration-200"
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 z-50 h-screen
          bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl
          border-r border-slate-200/50 dark:border-slate-700/50
          flex flex-col
          transition-[width,transform] duration-300 ease-out
          ${isMobile ? (isOpen ? 'translate-x-0' : '-translate-x-full') : ''}
        `}
        style={{ width: isOpen ? '18rem' : '5rem' }}
        role="navigation"
        aria-label="Main navigation"
        aria-expanded={isOpen}
      >
        {/* Logo Section */}
        <div className="flex items-center justify-between h-16 px-3 border-b border-slate-200/50 dark:border-slate-700/50">
          <Link href={userProfile?.is_root_admin ? '/admin' : '/admin/planner'} className="flex items-center flex-1 min-w-0 mr-2">
            {isOpen ? (
              <NextImage
                src="/logo.svg"
                alt="The Special Wedding"
                width={140}
                height={36}
                className="h-9 w-auto"
                priority
              />
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
              onClick={() => setIsOpen(false)}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
              aria-label="Close sidebar"
            >
              <X size={20} />
            </button>
          ) : (
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              aria-label={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
              aria-expanded={isOpen}
            >
              <ChevronLeft className={`w-5 h-5 transition-transform ${!isOpen ? 'rotate-180' : ''}`} />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1" aria-label="Sidebar navigation menu">
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
                  transition-colors duration-200
                  ${active
                    ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }
                `}
                aria-current={active ? 'page' : undefined}
                title={!isOpen ? item.name : undefined}
              >
                <Icon size={20} className={active ? 'text-primary-500' : ''} aria-hidden="true" />
                {isOpen && (
                  <span className="font-medium text-sm whitespace-nowrap overflow-hidden">
                    {item.name}
                  </span>
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
            aria-label="Logout from account"
            title="Logout"
          >
            <LogOut size={20} aria-hidden="true" />
            {isOpen && (
              <span className="font-medium text-sm">
                Logout
              </span>
            )}
          </button>
        </div>
      </aside>
    </>
  );
}
