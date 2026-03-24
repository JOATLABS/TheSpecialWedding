'use client';

import React from 'react';
import Link from 'next/link';
import NextImage from 'next/image';
import {
  LayoutDashboard,
  Calendar,
  CreditCard,
  ClipboardList,
  Mail,
  Gift,
  HelpCircle,
  LogOut,
  ChevronLeft,
  X,
  type LucideIcon,
} from 'lucide-react';

export type CoupleSection =
  | 'dashboard'
  | 'timeline'
  | 'payments'
  | 'forms'
  | 'inbox'
  | 'registry'
  | 'faq';

interface NavItem {
  key: CoupleSection;
  name: string;
  icon: LucideIcon;
}

const navItems: NavItem[] = [
  { key: 'dashboard', name: 'Dashboard', icon: LayoutDashboard },
  { key: 'timeline', name: 'Timeline', icon: Calendar },
  { key: 'payments', name: 'Payments', icon: CreditCard },
  { key: 'forms', name: 'Forms', icon: ClipboardList },
  { key: 'inbox', name: 'Inbox', icon: Mail },
  { key: 'registry', name: 'Registry', icon: Gift },
  { key: 'faq', name: 'FAQ', icon: HelpCircle },
];

interface CoupleSidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  isMobile: boolean;
  activeSection: CoupleSection;
  onSectionChange: (section: CoupleSection) => void;
  onLogout: () => void;
  unreadInbox?: number;
  pendingForms?: number;
}

export default function CoupleSidebar({
  isOpen,
  setIsOpen,
  isMobile,
  activeSection,
  onSectionChange,
  onLogout,
  unreadInbox = 0,
  pendingForms = 0,
}: CoupleSidebarProps) {
  const getBadgeCount = (key: CoupleSection): number | undefined => {
    if (key === 'inbox' && unreadInbox > 0) return unreadInbox;
    if (key === 'forms' && pendingForms > 0) return pendingForms;
    return undefined;
  };

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
        aria-label="Wedding portal navigation"
        aria-expanded={isOpen}
      >
        {/* Logo Section */}
        <div className="flex items-center justify-between h-16 px-3 border-b border-slate-200/50 dark:border-slate-700/50">
          <Link href="/couple/dashboard" className="flex items-center flex-1 min-w-0 mr-2">
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
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1" aria-label="Portal sections">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeSection === item.key;
            const badge = getBadgeCount(item.key);

            return (
              <button
                key={item.key}
                onClick={() => {
                  onSectionChange(item.key);
                  if (isMobile) setIsOpen(false);
                }}
                className={`
                  w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
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
                  <span className="font-medium text-sm whitespace-nowrap overflow-hidden flex-1 text-left">
                    {item.name}
                  </span>
                )}
                {isOpen && badge !== undefined && (
                  <span className="min-w-[20px] h-5 flex items-center justify-center px-1.5 text-[10px] font-bold text-white bg-red-500 rounded-full">
                    {badge > 99 ? '99+' : badge}
                  </span>
                )}
                {!isOpen && badge !== undefined && (
                  <span className="absolute left-[3.2rem] top-0.5 w-2 h-2 bg-red-500 rounded-full" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-3 border-t border-slate-200/50 dark:border-slate-700/50">
          <button
            onClick={onLogout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 transition-colors"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut size={20} aria-hidden="true" />
            {isOpen && (
              <span className="font-medium text-sm">Sign Out</span>
            )}
          </button>
        </div>
      </aside>
    </>
  );
}
