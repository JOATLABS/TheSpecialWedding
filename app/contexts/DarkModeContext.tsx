'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface DarkModeContextType {
  isDarkMode: boolean;
  toggleDarkMode: () => void;
}

const DarkModeContext = createContext<DarkModeContextType | null>(null);

export const DarkModeProvider = ({ children }: { children: ReactNode }) => {
  // Default to dark mode - but prevent hydration mismatch
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);

  // Load saved preference from localStorage on mount
  useEffect(() => {
    setIsHydrated(true);
    const savedTheme = localStorage.getItem('admin-dark-mode');
    if (savedTheme !== null) {
      setIsDarkMode(savedTheme === 'true');
    } else {
      // Default to dark mode if no saved preference
      setIsDarkMode(true);
    }
  }, []);

  // Apply theme class to document
  useEffect(() => {
    if (!isHydrated) return;

    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode, isHydrated]);

  const toggleDarkMode = () => {
    const newTheme = !isDarkMode;
    setIsDarkMode(newTheme);
    localStorage.setItem('admin-dark-mode', newTheme.toString());
  };

  return (
    <DarkModeContext.Provider value={{ isDarkMode, toggleDarkMode }}>
      {children}
    </DarkModeContext.Provider>
  );
};

export const useDarkMode = () => {
  const context = useContext(DarkModeContext);
  if (!context) {
    throw new Error('useDarkMode must be used within a DarkModeProvider');
  }
  return context;
};