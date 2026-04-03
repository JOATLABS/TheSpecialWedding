'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useTheme } from '@/contexts/ThemeContext';
import { Menu, Sun, Moon, LogOut, Heart, Settings, ChevronDown } from 'lucide-react';

interface CoupleTopHeaderProps {
  onMenuClick: () => void;
  coupleName?: string;
  onLogout: () => void;
}

export default function CoupleTopHeader({ onMenuClick, coupleName, onLogout }: CoupleTopHeaderProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Initials from couple name
  const getInitials = (name?: string) => {
    if (!name) return '♥';
    const parts = name.split(/\s*&\s*|\s+and\s+/i);
    if (parts.length >= 2) {
      return `${parts[0].charAt(0)}${parts[1].trim().charAt(0)}`.toUpperCase();
    }
    return name.charAt(0).toUpperCase();
  };

  return (
    <header
      className="sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-slate-200/50 dark:border-slate-700/50"
      role="banner"
    >
      <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
        {/* Left: Mobile menu toggle + couple name */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors lg:hidden"
            aria-label="Toggle navigation menu"
          >
            <Menu size={20} className="text-slate-600 dark:text-slate-400" aria-hidden="true" />
          </button>

          {coupleName && (
            <div className="flex items-center gap-2">
              <Heart size={18} className="text-primary-500 hidden sm:block" aria-hidden="true" />
              <h1 className="text-xl font-heading font-semibold text-slate-800 dark:text-white truncate max-w-[200px] sm:max-w-none">
                {coupleName}
              </h1>
            </div>
          )}
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {resolvedTheme === 'dark' ? (
              <Sun size={20} className="text-amber-500" aria-hidden="true" />
            ) : (
              <Moon size={20} className="text-slate-600" aria-hidden="true" />
            )}
          </button>

          {/* User Avatar + Dropdown (matches admin TopHeader pattern) */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="User menu"
              aria-expanded={dropdownOpen}
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-secondary-400 flex items-center justify-center">
                <span className="text-sm font-semibold text-white">{getInitials(coupleName)}</span>
              </div>
              <ChevronDown
                size={14}
                className={`text-slate-400 transition-transform hidden sm:block ${dropdownOpen ? 'rotate-180' : ''}`}
              />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-50">
                {coupleName && (
                  <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-700">
                    <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{coupleName}</p>
                  </div>
                )}
                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                >
                  <LogOut size={16} />
                  Sign Out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
