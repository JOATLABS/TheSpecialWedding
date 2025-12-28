'use client';

import React, { useState, useEffect } from "react";

interface AnchorNavProps {
  sections: string[];
}

// Compact dark mode toggle for nav bar
const NavDarkModeToggle: React.FC = () => {
  const [isDark, setIsDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem('wedding-dark-mode');
    if (stored !== null) {
      setIsDark(stored === 'true');
    } else {
      setIsDark(window.matchMedia('(prefers-color-scheme: dark)').matches);
    }
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('wedding-dark-mode', String(isDark));
  }, [isDark, mounted]);

  if (!mounted) return <div className="w-8 h-8" />;

  return (
    <button
      onClick={() => setIsDark(!isDark)}
      className="w-8 h-8 flex items-center justify-center rounded-full bg-white/20 hover:bg-white/30 transition-all duration-200 hover:scale-110"
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? (
        <svg className="w-4 h-4 text-yellow-300" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
        </svg>
      ) : (
        <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
      )}
    </button>
  );
};

export const AnchorNav: React.FC<AnchorNavProps> = ({ sections }) => {
  // Split sections for mobile layout
  const firstRow = sections.slice(0, 3);
  const secondRow = sections.slice(3);

  const renderLink = (id: string) => (
    <a
      key={id}
      href={`#${id}`}
      className="text-sm sm:text-base md:text-lg hover:underline focus:outline-none focus:ring focus:ring-white px-2"
    >
      {id === 'venue' ? (
        <>
          <span className="sm:hidden">DETAILS</span>
          <span className="hidden sm:inline">WEDDING DETAILS</span>
        </>
      ) : id === 'story' ? (
        'OUR STORY'
      ) : (
        id.replace(/-/g, ' ').toUpperCase()
      )}
    </a>
  );

  return (
    <nav className="w-full px-4 py-3 sm:py-4 bg-black/40 dark:bg-gray-900/80 backdrop-blur-sm text-white fixed top-0 left-0 z-50 transition-colors duration-300">
      {/* Mobile: Two rows with toggle */}
      <div className="sm:hidden relative">
        <div className="flex justify-center space-x-3 mb-2">
          {firstRow.map(renderLink)}
        </div>
        <div className="flex justify-center space-x-3">
          {secondRow.map(renderLink)}
        </div>
        {/* Mobile toggle - absolute positioned top right */}
        <div className="absolute top-0 right-0">
          <NavDarkModeToggle />
        </div>
      </div>

      {/* Desktop: Single row with toggle on far right */}
      <div className="hidden sm:flex items-center justify-center">
        <div className="flex space-x-4 md:space-x-6 lg:space-x-8">
          {sections.map(renderLink)}
        </div>
        <div className="absolute right-4">
          <NavDarkModeToggle />
        </div>
      </div>
    </nav>
  );
};
