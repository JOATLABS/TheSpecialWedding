'use client';

import React, { useState, useEffect, useCallback, useRef } from "react";

interface AnchorNavProps {
  sections: string[];
}

// Compact dark mode toggle with veil sweep & ring ripple animations
const NavDarkModeToggle: React.FC = () => {
  const [isDark, setIsDark] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [ripplePos, setRipplePos] = useState({ x: 0, y: 0 });

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

  const toggleDarkMode = useCallback(() => {
    if (isAnimating) return;

    // Get button position for ripple origin
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setRipplePos({
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
      });
    }

    setIsAnimating(true);
    // Switch at midpoint of animation
    setTimeout(() => setIsDark(prev => !prev), 500);
    // End animation
    setTimeout(() => setIsAnimating(false), 1000);
  }, [isAnimating]);

  if (!mounted) return <div className="w-8 h-8" />;

  // Read CSS variable for theme primary color (set by useTheme hook)
  const themePrimary = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--theme-primary').trim() || '#E91E63'
    : '#E91E63';
  const themeSecondary = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--theme-secondary').trim() || '#F8BBD9'
    : '#F8BBD9';

  return (
    <>
      {/* Veil Sweep animation */}
      {isAnimating && (
        <div className="fixed inset-0 pointer-events-none z-[9998] overflow-hidden">
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: isDark
                ? `linear-gradient(135deg, ${themePrimary}15 0%, rgba(17, 24, 39, 0.97) 15%, rgba(17, 24, 39, 0.97) 85%, ${themePrimary}15 100%)`
                : `linear-gradient(135deg, ${themeSecondary}40 0%, rgba(255, 255, 255, 0.97) 15%, rgba(255, 255, 255, 0.97) 85%, ${themeSecondary}40 100%)`,
              animation: 'navVeilSweep 1s cubic-bezier(0.4, 0, 0.2, 1) forwards',
            }}
          />
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              width: '2px',
              background: `linear-gradient(180deg, transparent 0%, ${themePrimary} 20%, ${themeSecondary} 50%, ${themePrimary} 80%, transparent 100%)`,
              boxShadow: `0 0 20px ${themePrimary}, 0 0 40px ${themeSecondary}`,
              animation: 'navShimmerLine 1s cubic-bezier(0.4, 0, 0.2, 1) forwards',
            }}
          />
        </div>
      )}

      {/* Ring Ripple animation */}
      {isAnimating && (
        <div className="fixed inset-0 pointer-events-none z-[9997] overflow-hidden">
          {[0, 0.15, 0.3].map((delay, i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: ripplePos.x,
                top: ripplePos.y,
                width: 40,
                height: 40,
                marginLeft: -20,
                marginTop: -20,
                borderRadius: '50%',
                border: `${i === 2 ? 1 : 2}px solid ${i === 1 ? themeSecondary : themePrimary}${i === 2 ? '80' : ''}`,
                boxShadow: `0 0 ${i === 2 ? 10 : 15}px ${i === 1 ? themeSecondary : themePrimary}${i === 2 ? '40' : '60'}`,
                animation: `navRingRipple 1s cubic-bezier(0.4, 0, 0.6, 1) ${delay}s forwards`,
                opacity: 0,
              }}
            />
          ))}
        </div>
      )}

      <button
        ref={buttonRef}
        onClick={toggleDarkMode}
        disabled={isAnimating}
        className="w-8 h-8 flex items-center justify-center rounded-full bg-white/20 hover:bg-white/30 transition-all duration-200 hover:scale-110 disabled:cursor-wait"
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
    </>
  );
};

// Keyframe styles injected once
const AnimationStyles: React.FC = () => (
  <style jsx global>{`
    @keyframes navVeilSweep {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    @keyframes navShimmerLine {
      0% { left: -2px; }
      100% { left: calc(100% + 2px); }
    }
    @keyframes navRingRipple {
      0% { transform: scale(1); opacity: 1; }
      100% { transform: scale(30); opacity: 0; }
    }
    html {
      transition: background-color 0.5s ease;
    }
    html.dark {
      color-scheme: dark;
    }
  `}</style>
);

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
    <>
      <AnimationStyles />
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
    </>
  );
};
