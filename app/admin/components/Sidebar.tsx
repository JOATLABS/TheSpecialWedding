'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { getAllowedTeamNavNames } from '@/admin/utils/teamAccess';
import {
  COUPLE_PLAN_HIDDEN_NAV_NAMES,
  isCouplePlan,
} from '@/admin/utils/planAccess';
import {
  WorkspaceSidebar,
  type WorkspaceNavItem,
} from '@/components/layout/WorkspaceChrome';
import {
  Bell,
  Calendar,
  CreditCard,
  ExternalLink,
  FileText,
  Heart,
  HelpCircle,
  Image,
  Layers,
  LayoutDashboard,
  LayoutGrid,
  Mail,
  Megaphone,
  Package,
  PlusCircle,
  Server,
  Sparkles,
  Store,
  Monitor,
  UserPlus,
  Users,
  Wallet,
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  isMobile: boolean;
}

type LucideIcon = React.ForwardRefExoticComponent<
  Omit<React.SVGProps<SVGSVGElement>, 'ref'> & { size?: number | string } & React.RefAttributes<SVGSVGElement>
>;

interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  adminOnly?: boolean;
  plannerOnly?: boolean;
  shortcut?: boolean;
  external?: boolean;
}

// Navigation items for Root Admin/Developer (platform-level management only)
const adminNavItems: NavItem[] = [
  { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
  { name: 'Platform', href: '/admin/platform', icon: Server },
  { name: 'SaaS Management', href: '/admin/saas', icon: Layers },
  { name: 'Accounts', href: '/admin/users', icon: Users },
  { name: 'Billing', href: '/admin/billing', icon: CreditCard },
  { name: 'Ad Platform', href: '/admin/ads', icon: Megaphone },
  { name: 'Notifications', href: '/admin/notifications', icon: Bell },
  { name: 'Communications', href: '/admin/communications/inbox', icon: Mail },
  { name: 'Support', href: '/admin/support', icon: HelpCircle },
  // Shortcuts: quick access for ad platform workflows (after all main nav items)
  { name: 'Create Vendor', href: '/portal/ads/campaigns/new', icon: PlusCircle, shortcut: true },
  { name: 'Vendor Portal', href: '/portal/ads', icon: ExternalLink, shortcut: true, external: true },
];

// Navigation items for Wedding Planners
const plannerNavItems: NavItem[] = [
  { name: 'Dashboard', href: '/admin/planner', icon: LayoutDashboard },
  { name: 'Calendar', href: '/admin/planner/calendar', icon: Calendar },
  { name: 'Weddings', href: '/admin/weddings', icon: Heart },
  { name: 'Packages', href: '/admin/packages', icon: Package },
  { name: 'Guests', href: '/admin/guests', icon: Users },
  { name: 'Communications', href: '/admin/communications', icon: Mail },
  { name: 'Gallery', href: '/admin/gallery/upload', icon: Image },
  { name: 'Budget', href: '/admin/budget', icon: Wallet },
  { name: 'Money', href: '/admin/money', icon: CreditCard },
  { name: 'Forms', href: '/admin/forms', icon: FileText },
  { name: 'Vendors', href: '/admin/vendors', icon: Store },
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

  // Determine which navigation items to show based on user role
  const getNavItems = (): NavItem[] => {
    if (!userProfile) return [];

    // Root admin/developer gets admin navigation
    if (userProfile.is_root_admin) {
      return adminNavItems;
    }

    // Wedding planner gets full planner navigation. Couple-plan workspaces
    // (self-serve couples on the planner dashboard) never see Packages or
    // Team — those are planner-business features, and the backend rejects
    // them anyway; no dead menu items.
    if (userProfile.is_wedding_planner) {
      if (isCouplePlan(userProfile)) {
        return plannerNavItems.filter(
          (item) => !COUPLE_PLAN_HIDDEN_NAV_NAMES.has(item.name)
        );
      }
      return plannerNavItems;
    }

    // Team members get filtered navigation based on their permissions
    if (userProfile.is_team_member && userProfile.team_permissions) {
      const allowedNavNames = getAllowedTeamNavNames(userProfile);

      return plannerNavItems.filter(
        (item) => !item.plannerOnly && allowedNavNames.has(item.name)
      );
    }

    // Default to planner navigation for other roles
    return plannerNavItems;
  };

  const filteredNavItems = getNavItems();
  const mainItems: WorkspaceNavItem[] = filteredNavItems
    .filter((item) => !item.shortcut)
    .map((item) => ({
      key: item.name,
      name: item.name,
      href: item.href,
      icon: item.icon,
      active: isActive(item.href),
      external: item.external,
    }));

  const secondaryItems: WorkspaceNavItem[] = filteredNavItems
    .filter((item) => item.shortcut)
    .map((item) => ({
      key: item.name,
      name: item.name,
      href: item.href,
      icon: item.icon,
      active: false,
      external: item.external,
      tone: 'shortcut',
      badge: 'shortcut',
    }));

  return (
    <WorkspaceSidebar
      brandHref={userProfile?.is_root_admin ? '/admin' : '/admin/planner'}
      navigationLabel="Main navigation"
      isOpen={isOpen}
      isMobile={isMobile}
      onClose={() => setIsOpen(false)}
      onToggle={() => setIsOpen(!isOpen)}
      mainItems={mainItems}
      secondaryItems={secondaryItems}
      secondarySectionLabel="Shortcuts"
      footerAction={{
        label: 'Logout',
        ariaLabel: 'Logout from account',
        title: 'Logout',
        onClick: () => logout(),
      }}
    />
  );
}
