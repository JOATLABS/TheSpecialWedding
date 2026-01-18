'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';

// Theme color mapping for wedding themes
const THEME_COLORS: Record<string, { primary: string; secondary: string }> = {
  rose: { primary: '#E91E63', secondary: '#F8BBD9' },
  sage: { primary: '#7CB342', secondary: '#C5E1A5' },
  gold: { primary: '#FFB300', secondary: '#FFE082' },
  navy: { primary: '#1565C0', secondary: '#90CAF9' },
  blush: { primary: '#EC407A', secondary: '#F8BBD9' },
  terracotta: { primary: '#D84315', secondary: '#FFAB91' },
  lavender: { primary: '#7E57C2', secondary: '#D1C4E9' },
  emerald: { primary: '#2E7D32', secondary: '#A5D6A7' },
  burgundy: { primary: '#880E4F', secondary: '#F48FB1' },
  dustyblue: { primary: '#5C6BC0', secondary: '#C5CAE9' },
};

interface WeddingDarkModeToggleProps {
  className?: string;
  themeColor?: string;
}

export const WeddingDarkModeToggle: React.FC<WeddingDarkModeToggleProps> = ({
  className = '',
  themeColor = 'rose'
}) => {
  const [isDark, setIsDark] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const [mounted, setMounted] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [ripplePos, setRipplePos] = useState({ x: 0, y: 0 });

  const colors = THEME_COLORS[themeColor] || THEME_COLORS.rose;

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

    // Switch at midpoint
    setTimeout(() => setIsDark(prev => !prev), 500);

    // End animation
    setTimeout(() => setIsAnimating(false), 1000);
  }, [isAnimating]);

  if (!mounted) {
    return <div className={`w-14 h-14 ${className}`} />;
  }

  return (
    <div className={`relative ${className}`}>
      {/* Animation 1: Veil Sweep - elegant curtain reveal */}
      {isAnimating && (
        <div className="fixed inset-0 pointer-events-none z-[9998] overflow-hidden">
          {/* The sweeping veil */}
          <div
            className="absolute inset-0 animate-veil-sweep"
            style={{
              background: isDark
                ? `linear-gradient(135deg,
                    ${colors.primary}15 0%,
                    rgba(17, 24, 39, 0.97) 15%,
                    rgba(17, 24, 39, 0.97) 85%,
                    ${colors.primary}15 100%)`
                : `linear-gradient(135deg,
                    ${colors.secondary}40 0%,
                    rgba(255, 255, 255, 0.97) 15%,
                    rgba(255, 255, 255, 0.97) 85%,
                    ${colors.secondary}40 100%)`,
            }}
          />

          {/* Elegant shimmer line at the edge */}
          <div
            className="absolute inset-y-0 w-1 animate-shimmer-line"
            style={{
              background: `linear-gradient(180deg,
                transparent 0%,
                ${colors.primary} 20%,
                ${colors.secondary} 50%,
                ${colors.primary} 80%,
                transparent 100%)`,
              boxShadow: `0 0 20px ${colors.primary}, 0 0 40px ${colors.secondary}`,
            }}
          />
        </div>
      )}

      {/* Animation 2: Ring Ripple - expanding rings from button */}
      {isAnimating && (
        <div className="fixed inset-0 pointer-events-none z-[9997] overflow-hidden">
          {/* First ring */}
          <div
            className="absolute rounded-full animate-ring-ripple"
            style={{
              left: ripplePos.x,
              top: ripplePos.y,
              width: 60,
              height: 60,
              marginLeft: -30,
              marginTop: -30,
              border: `2px solid ${colors.primary}`,
              boxShadow: `0 0 15px ${colors.primary}60`,
            }}
          />
          {/* Second ring - delayed */}
          <div
            className="absolute rounded-full animate-ring-ripple-delayed"
            style={{
              left: ripplePos.x,
              top: ripplePos.y,
              width: 60,
              height: 60,
              marginLeft: -30,
              marginTop: -30,
              border: `2px solid ${colors.secondary}`,
              boxShadow: `0 0 15px ${colors.secondary}60`,
            }}
          />
          {/* Third ring - more delayed */}
          <div
            className="absolute rounded-full animate-ring-ripple-delayed-2"
            style={{
              left: ripplePos.x,
              top: ripplePos.y,
              width: 60,
              height: 60,
              marginLeft: -30,
              marginTop: -30,
              border: `1px solid ${colors.primary}80`,
              boxShadow: `0 0 10px ${colors.primary}40`,
            }}
          />
        </div>
      )}

      {/* Toggle button with label */}
      <div className="flex items-center gap-3">
        {/* Label */}
        <span
          className="
            hidden sm:block
            text-sm font-medium
            bg-white/90 dark:bg-gray-800/90
            backdrop-blur-md
            px-3 py-2 rounded-full
            shadow-lg border-2
            transition-all duration-300
          "
          style={{ borderColor: colors.primary }}
        >
          {isDark ? '☀️ Light' : '🌙 Dark'}
        </span>
        <button
          ref={buttonRef}
          onClick={toggleDarkMode}
          disabled={isAnimating}
          className={`
            relative w-14 h-14 rounded-full
            bg-white/90 dark:bg-gray-800/90
            backdrop-blur-md shadow-lg
            border-2 transition-all duration-300
            hover:scale-110 hover:shadow-xl
            active:scale-95
            disabled:cursor-wait
            overflow-hidden
            ring-4 ring-white/50 dark:ring-gray-700/50
          `}
          style={{
            borderColor: colors.primary,
            boxShadow: isAnimating
              ? `0 0 30px ${colors.primary}80`
              : `0 4px 20px rgba(0,0,0,0.25), 0 0 0 4px ${colors.primary}20`,
          }}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
        {/* Sun icon */}
        <div
          className={`
            absolute inset-0 flex items-center justify-center
            transition-all duration-500 ease-out
            ${isDark ? 'opacity-0 rotate-180 scale-0' : 'opacity-100 rotate-0 scale-100'}
          `}
        >
          <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="4" fill={colors.primary} />
            <g stroke={colors.primary} strokeWidth="2" strokeLinecap="round">
              <line x1="12" y1="2" x2="12" y2="4" />
              <line x1="12" y1="20" x2="12" y2="22" />
              <line x1="4.93" y1="4.93" x2="6.34" y2="6.34" />
              <line x1="17.66" y1="17.66" x2="19.07" y2="19.07" />
              <line x1="2" y1="12" x2="4" y2="12" />
              <line x1="20" y1="12" x2="22" y2="12" />
              <line x1="4.93" y1="19.07" x2="6.34" y2="17.66" />
              <line x1="17.66" y1="6.34" x2="19.07" y2="4.93" />
            </g>
          </svg>
        </div>

        {/* Moon icon */}
        <div
          className={`
            absolute inset-0 flex items-center justify-center
            transition-all duration-500 ease-out
            ${isDark ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-180 scale-0'}
          `}
        >
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill={colors.secondary}>
            <path d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
          </svg>
        </div>
      </button>
      </div>
    </div>
  );
};

// Styles for the animations
export const WeddingDarkModeStyles = () => (
  <style jsx global>{`
    /* Animation 1: Veil Sweep */
    @keyframes veil-sweep {
      0% {
        transform: translateX(-100%);
      }
      100% {
        transform: translateX(100%);
      }
    }

    @keyframes shimmer-line {
      0% {
        left: -2px;
      }
      100% {
        left: calc(100% + 2px);
      }
    }

    .animate-veil-sweep {
      animation: veil-sweep 1s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }

    .animate-shimmer-line {
      animation: shimmer-line 1s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }

    /* Animation 2: Ring Ripple */
    @keyframes ring-ripple {
      0% {
        transform: scale(1);
        opacity: 1;
      }
      100% {
        transform: scale(25);
        opacity: 0;
      }
    }

    .animate-ring-ripple {
      animation: ring-ripple 1s cubic-bezier(0.4, 0, 0.6, 1) forwards;
    }

    .animate-ring-ripple-delayed {
      animation: ring-ripple 1s cubic-bezier(0.4, 0, 0.6, 1) forwards;
      animation-delay: 0.15s;
    }

    .animate-ring-ripple-delayed-2 {
      animation: ring-ripple 1s cubic-bezier(0.4, 0, 0.6, 1) forwards;
      animation-delay: 0.3s;
    }

    /* Smooth page transitions */
    html {
      transition: background-color 0.5s ease;
    }

    html.dark {
      color-scheme: dark;
    }
  `}</style>
);

export default WeddingDarkModeToggle;
