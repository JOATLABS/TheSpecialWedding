'use client';

import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import Link from 'next/link';
import NextImage from 'next/image';
import {
  Bell,
  ChevronDown,
  ChevronLeft,
  LogOut,
  Menu,
  Moon,
  Sun,
  User,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { BrandLockup } from '@/components/brand/BrandLockup';

export interface WorkspaceNavItem {
  key: string;
  name: string;
  href: string;
  icon: LucideIcon;
  active: boolean;
  external?: boolean;
  tone?: 'default' | 'shortcut';
  badge?: string;
}

export interface WorkspaceMenuItem {
  key: string;
  label: string;
  icon: LucideIcon;
  href?: string;
  onSelect?: () => void;
  tone?: 'default' | 'danger';
}

export interface WorkspaceUserSummary {
  name?: string;
  email?: string;
  initials?: string;
  profileImageUrl?: string;
}

interface WorkspaceSidebarProps {
  brandHref: string;
  navigationLabel: string;
  isOpen: boolean;
  isMobile: boolean;
  onClose: () => void;
  onToggle: () => void;
  mainItems: WorkspaceNavItem[];
  secondaryItems?: WorkspaceNavItem[];
  secondarySectionLabel?: string;
  footerAction: {
    label: string;
    ariaLabel?: string;
    title?: string;
    icon?: LucideIcon;
    onClick: () => void;
  };
}

interface WorkspaceTopHeaderProps {
  onMenuClick: () => void;
  title?: string;
  notificationHref: string;
  notificationCount: number;
  user: WorkspaceUserSummary | null;
  menuItems: WorkspaceMenuItem[];
}

interface WorkspaceShellFrameProps {
  children: React.ReactNode;
  sidebar: React.ReactNode;
  header: React.ReactNode;
  isMobile: boolean;
  isSidebarOpen: boolean;
  banner?: React.ReactNode;
  afterShell?: React.ReactNode;
  mainClassName?: string;
}

export function WorkspaceBackground() {
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

export function useResponsiveWorkspaceSidebar(defaultDesktopOpen = true) {
  const [isMobile, setIsMobile] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(defaultDesktopOpen);
  const lastIsMobileRef = useRef<boolean | null>(null);

  useLayoutEffect(() => {
    const handleResize = () => {
      const nextIsMobile = window.innerWidth < 1024;
      setIsMobile(nextIsMobile);

      if (lastIsMobileRef.current === null || lastIsMobileRef.current !== nextIsMobile) {
        setIsSidebarOpen(nextIsMobile ? false : defaultDesktopOpen);
      }

      lastIsMobileRef.current = nextIsMobile;
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [defaultDesktopOpen]);

  return { isMobile, isSidebarOpen, setIsSidebarOpen };
}

export function WorkspaceShellFrame({
  children,
  sidebar,
  header,
  isMobile,
  isSidebarOpen,
  banner,
  afterShell,
  mainClassName,
}: WorkspaceShellFrameProps) {
  return (
    <div className="min-h-screen overflow-x-hidden bg-light-bg text-light-text font-sans transition-colors duration-300 dark:bg-dark-bg dark:text-dark-text">
      <WorkspaceBackground />
      {sidebar}

      <div
        className={`relative z-10 flex min-h-screen flex-col ${
          isMobile ? 'transition-none' : 'transition-[margin] duration-300 ease-out'
        }`}
        style={{ marginLeft: !isMobile ? (isSidebarOpen ? '18rem' : '5rem') : '0' }}
      >
        {banner}
        {header}

        <main
          className={`flex-1 overflow-x-hidden p-4 sm:p-6 lg:p-8 ${mainClassName || 'space-y-6'}`}
          id="main-content"
        >
          {children}
        </main>
      </div>

      {afterShell}
    </div>
  );
}

export function WorkspaceSidebar({
  brandHref,
  navigationLabel,
  isOpen,
  isMobile,
  onClose,
  onToggle,
  mainItems,
  secondaryItems = [],
  secondarySectionLabel = 'Shortcuts',
  footerAction,
}: WorkspaceSidebarProps) {
  const FooterIcon = footerAction.icon || LogOut;

  return (
    <>
      {isMobile && isOpen ? (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/50 transition-opacity duration-200 lg:hidden"
          aria-hidden="true"
        />
      ) : null}

      <aside
        id="workspace-sidebar"
        className={`
          fixed left-0 top-0 z-50 flex h-screen flex-col border-r border-slate-200/50 bg-white/80 backdrop-blur-xl dark:border-slate-700/50 dark:bg-slate-900/80
          ${isMobile && !isOpen ? 'transition-none' : 'transition-[width,transform] duration-300 ease-out'}
          ${isMobile ? (isOpen ? 'translate-x-0' : '-translate-x-full') : ''}
        `}
        style={{
          width: isMobile ? '18rem' : isOpen ? '18rem' : '5rem',
          transform: isMobile && !isOpen ? 'translateX(-100%)' : undefined,
        }}
        role="navigation"
        aria-label={navigationLabel}
      >
        <div className="flex h-24 items-center justify-between border-b border-slate-200/50 px-3 dark:border-slate-700/50">
          <Link href={brandHref} className="mr-2 flex min-w-0 flex-1 items-center" aria-label="The Special Wedding home">
            {isOpen ? (
              <>
                <span className="block dark:hidden">
                  <BrandLockup variant="full" surface="light" size="md" />
                </span>
                <span className="hidden dark:block">
                  <BrandLockup variant="full" surface="dark" size="md" />
                </span>
              </>
            ) : (
              <NextImage
                src="/favicon.svg"
                alt="The Special Wedding"
                width={44}
                height={44}
                className="h-11 w-11"
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

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label={navigationLabel}>
          {mainItems.map((item) => renderWorkspaceNavItem(item, isOpen, isMobile, onClose))}

          {secondaryItems.length > 0 ? (
            <>
              {isOpen ? (
                <p className="px-3 pt-4 pb-1 text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                  {secondarySectionLabel}
                </p>
              ) : null}
              {secondaryItems.map((item) => renderWorkspaceNavItem(item, isOpen, isMobile, onClose))}
            </>
          ) : null}
        </nav>

        <div className="border-t border-slate-200/50 p-3 dark:border-slate-700/50">
          <button
            onClick={footerAction.onClick}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-900/20 dark:hover:text-red-400"
            aria-label={footerAction.ariaLabel || footerAction.label}
            title={footerAction.title || footerAction.label}
          >
            <FooterIcon size={20} aria-hidden="true" />
            {isOpen ? <span className="text-sm font-medium">{footerAction.label}</span> : null}
          </button>
        </div>
      </aside>
    </>
  );
}

export function WorkspaceTopHeader({
  onMenuClick,
  title,
  notificationHref,
  notificationCount,
  user,
  menuItems,
}: WorkspaceTopHeaderProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const displayName = user?.name || user?.email?.split('@')[0] || 'User';
  const initials = user?.initials || deriveInitials(displayName);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/50 bg-white/80 backdrop-blur-xl dark:border-slate-700/50 dark:bg-slate-900/80" role="banner">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800 lg:hidden"
            aria-label="Toggle navigation menu"
            aria-controls="workspace-sidebar"
          >
            <Menu size={20} className="text-slate-600 dark:text-slate-400" aria-hidden="true" />
          </button>

          {title ? (
            <h1 className="text-xl font-heading font-semibold text-slate-800 dark:text-white">
              {title}
            </h1>
          ) : null}
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
            href={notificationHref}
            className="relative rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label={`Notifications${notificationCount > 0 ? ` (${notificationCount} unread)` : ''}`}
            title={`Notifications${notificationCount > 0 ? ` (${notificationCount} unread)` : ''}`}
          >
            <Bell size={20} className="text-slate-600 dark:text-slate-400" aria-hidden="true" />
            {notificationCount > 0 ? (
              <span className="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white shadow-sm">
                {notificationCount > 99 ? '99+' : notificationCount}
              </span>
            ) : null}
          </Link>

          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setShowDropdown((value) => !value)}
              className="flex items-center gap-2 rounded-lg p-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="User menu"
              aria-haspopup="true"
              aria-expanded={showDropdown}
              aria-controls="workspace-user-dropdown-menu"
            >
              <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-primary-400 to-secondary-400">
                {user?.profileImageUrl ? (
                  <img
                    src={user.profileImageUrl}
                    alt={`${displayName} profile`}
                    className="h-full w-full object-cover"
                  />
                ) : initials ? (
                  <span className="text-sm font-semibold text-white">
                    {initials}
                  </span>
                ) : (
                  <User size={16} className="text-white" aria-hidden="true" />
                )}
              </div>
              <span className="hidden text-sm font-medium text-slate-700 dark:text-slate-300 sm:block">
                {displayName}
              </span>
              <ChevronDown
                size={16}
                className={`hidden text-slate-400 transition-transform sm:block ${showDropdown ? 'rotate-180' : ''}`}
                aria-hidden="true"
              />
            </button>

            {showDropdown ? (
              <div
                className="absolute right-0 top-full z-50 mt-1 w-52 rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
                id="workspace-user-dropdown-menu"
                role="menu"
              >
                {menuItems.map((item, index) => {
                  const Icon = item.icon;
                  const isDanger = item.tone === 'danger';
                  const classes = `flex w-full items-center gap-3 px-4 py-2 text-sm transition-colors ${
                    isDanger
                      ? 'text-red-600 hover:bg-slate-100 dark:text-red-400 dark:hover:bg-slate-700'
                      : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700'
                  }`;

                  return (
                    <React.Fragment key={item.key}>
                      {item.href ? (
                        <Link
                          href={item.href}
                          onClick={() => setShowDropdown(false)}
                          className={classes}
                          role="menuitem"
                        >
                          <Icon size={16} aria-hidden="true" />
                          {item.label}
                        </Link>
                      ) : (
                        <button
                          onClick={() => {
                            setShowDropdown(false);
                            item.onSelect?.();
                          }}
                          className={classes}
                          role="menuitem"
                        >
                          <Icon size={16} aria-hidden="true" />
                          {item.label}
                        </button>
                      )}
                      {index < menuItems.length - 1 ? (
                        <hr className="my-1 border-slate-200 dark:border-slate-700" />
                      ) : null}
                    </React.Fragment>
                  );
                })}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}

function renderWorkspaceNavItem(
  item: WorkspaceNavItem,
  isOpen: boolean,
  isMobile: boolean,
  onClose: () => void,
) {
  const Icon = item.icon;
  const isShortcut = item.tone === 'shortcut';
  const classes = isShortcut
    ? 'text-wedding-gold hover:bg-amber-50 dark:hover:bg-amber-900/10'
    : item.active
      ? 'bg-primary-50 text-primary-600 dark:bg-primary-900/20 dark:text-primary-400'
      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800';

  return (
    <Link
      key={item.key}
      href={item.href}
      onClick={() => {
        if (isMobile) {
          onClose();
        }
      }}
      {...(item.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      className={`flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors duration-200 ${classes}`}
      aria-current={item.active ? 'page' : undefined}
      title={!isOpen ? item.name : undefined}
    >
      <Icon size={20} className={isShortcut ? 'text-wedding-gold' : item.active ? 'text-primary-500' : ''} aria-hidden="true" />
      {isOpen ? (
        <>
          <span className="flex-1 overflow-hidden whitespace-nowrap text-left text-sm font-medium">
            {item.name}
          </span>
          {item.badge ? (
            <span className="ml-auto rounded bg-wedding-gold px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wide text-slate-900">
              {item.badge}
            </span>
          ) : null}
        </>
      ) : null}
    </Link>
  );
}

function deriveInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);

  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }

  return name.slice(0, 2).toUpperCase();
}
