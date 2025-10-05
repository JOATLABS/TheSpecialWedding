'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';
import { ThemeConfig } from '@/types/wedding';

interface Modern3DBackgroundProps {
  imageUrl?: string;
  fallbackImages?: string[];
  theme?: ThemeConfig;
}

export const Modern3DBackground: React.FC<Modern3DBackgroundProps> = ({
  imageUrl,
  fallbackImages = [],
  theme
}) => {
  const [scrollY, setScrollY] = useState(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [isCoarsePointer, setIsCoarsePointer] = useState(false);
  const rafRef = useRef<number | null>(null);
  const lastScrollRef = useRef(0);

  const parallaxActive = !(prefersReducedMotion || isCoarsePointer);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const coarseQuery = window.matchMedia('(hover: none) and (pointer: coarse)');
    const updatePointerMode = () => setIsCoarsePointer(coarseQuery.matches);

    updatePointerMode();
    coarseQuery.addEventListener('change', updatePointerMode);

    return () => coarseQuery.removeEventListener('change', updatePointerMode);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const syncPreference = () => setPrefersReducedMotion(motionQuery.matches);
    syncPreference();
    motionQuery.addEventListener('change', syncPreference);
    return () => motionQuery.removeEventListener('change', syncPreference);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !parallaxActive) {
      if (!parallaxActive) {
        setScrollY(0);
      }
      return;
    }

    const updateScroll = () => {
      lastScrollRef.current = window.scrollY;
      if (rafRef.current !== null) {
        return;
      }

      rafRef.current = window.requestAnimationFrame(() => {
        const next = lastScrollRef.current;
        rafRef.current = null;
        setScrollY((previous) => {
          if (Math.abs(previous - next) < 2) {
            return previous;
          }

          return next;
        });
      });
    };

    updateScroll();

    window.addEventListener('scroll', updateScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', updateScroll);
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [parallaxActive]);

  // Use featured image or first fallback image
  const backgroundImage = imageUrl || fallbackImages[0];

  // Deep parallax effect - background moves slower and opposite to scroll
  // Negative value makes it move down as you scroll down (stays visible longer)
  const { parallaxOffset, accentOffset, highlightOffset } = useMemo(() => {
    if (!parallaxActive) {
      return {
        parallaxOffset: 0,
        accentOffset: 0,
        highlightOffset: 0,
      };
    }

    const clampedScroll = Math.min(scrollY, 1200);
    return {
      parallaxOffset: clampedScroll * -0.22,
      accentOffset: clampedScroll * 0.12,
      highlightOffset: clampedScroll * -0.08,
    };
  }, [parallaxActive, scrollY]);

  if (!backgroundImage) {
    // Gradient fallback if no images
    return (
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-wedding-ivory via-rose-50 to-wedding-sage/20" />
      </div>
    );
  }

  return (
    <>
      {/* Fixed background container */}
      <div className="fixed inset-0 -z-10 overflow-hidden bg-slate-950">
        {/* Parallax image layer */}
        <div
          className="absolute inset-0"
          style={{
            transform: `translate3d(0, ${parallaxOffset}px, 0) scale(1.08)`,
            willChange: 'transform',
            height: '155%',
            perspective: '1200px'
          }}
        >
          <Image
            src={backgroundImage}
            alt="Wedding background"
            fill
            quality={90}
            priority
            className="object-cover"
            sizes="100vw"
          />
        </div>
        
        {/* Theme-based overlay */}
        {theme?.background_style === 'gradient' && (
          <div 
            className="absolute inset-0"
            style={{
              background: `linear-gradient(135deg, ${theme.primary_color}CC, ${theme.secondary_color}CC)`
            }}
          />
        )}
        
        {theme?.background_style === 'solid' && (
          <div 
            className="absolute inset-0"
            style={{
              backgroundColor: `${theme.primary_color}CC`
            }}
          />
        )}
        
        {/* Frost effect for glass style (default) */}
        {(!theme?.background_style || theme.background_style === 'gradient') && (
          <>
            {/* Dark overlay for better text contrast */}
            <div className="absolute inset-0 bg-slate-900/35" />

            {/* Blur overlay for depth */}
            <div className="absolute inset-0 backdrop-blur-[2px]" />
          </>
        )}

        {/* Central glow to lift foreground cards */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background: 'radial-gradient(circle at center, rgba(255,255,255,0.26), rgba(195,255,255,0) 62%)',
            transform: `translate3d(0, ${highlightOffset}px, 0)`
          }}
        />

        {/* Subtle vignette for depth perception */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(15,23,42,0),rgba(15,23,42,0.55))] opacity-70" />

        {/* Directional depth gradient - darker at base */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-slate-900/25 to-slate-950/70" />

        {/* Highlight streak to simulate light pass */}
        <div
          className="pointer-events-none absolute inset-x-0 top-[12%] h-2/5 opacity-70"
          style={{
            background: 'radial-gradient(circle at top, rgba(255,255,255,0.42), rgba(255,255,255,0))',
            transform: `translate3d(0, ${accentOffset}px, 0)`
          }}
        />

        {/* Floating glass orbs for added depth */}
        {!prefersReducedMotion && (
          <>
            <div
              className="pointer-events-none absolute -left-40 top-[18%] hidden h-72 w-72 rounded-full bg-white/12 blur-3xl md:block"
              style={{ transform: `translate3d(0, ${accentOffset * 0.6}px, 0)` }}
            />
            <div
              className="pointer-events-none absolute -right-32 bottom-[14%] hidden h-80 w-80 rounded-full bg-emerald-200/20 blur-3xl lg:block"
              style={{ transform: `translate3d(0, ${accentOffset * -0.4}px, 0)` }}
            />
            <div
              className="pointer-events-none absolute left-1/2 top-1/4 h-52 w-52 -translate-x-1/2 rounded-full border border-white/10 bg-white/8 shadow-[0_40px_120px_-60px_rgba(15,23,42,0.7)] backdrop-blur"
              style={{ transform: `translate3d(-50%, ${accentOffset * 0.3}px, 0)` }}
            />
          </>
        )}
      </div>
    </>
  );
};