'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface DarkModeContextType {
  isDarkMode: boolean;
  toggleDarkMode: () => void;
}

const DarkModeContext = createContext<DarkModeContextType | null>(null);

export const DarkModeProvider = ({ children }: { children: ReactNode }) => {
  // Default to dark mode
  const [isDarkMode, setIsDarkMode] = useState(true);

  // Load saved preference from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('admin-dark-mode');
    if (savedTheme !== null) {
      setIsDarkMode(savedTheme === 'true');
    }
    // If no saved preference, keep default dark mode (true)
  }, []);

  // Apply theme class to document
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

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