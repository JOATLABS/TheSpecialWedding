'use client';

import React, { useEffect, useState } from 'react';
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

  useEffect(() => {
    const handleScroll = () => {
      setScrollY(window.scrollY);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
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

  // Use featured image or first fallback image
  const backgroundImage = imageUrl || fallbackImages[0];
  
  if (!backgroundImage) {
    // Gradient fallback if no images
    return (
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-wedding-ivory via-rose-50 to-wedding-sage/20" />
      </div>
    );
  }

  // Deep parallax effect - background moves slower and opposite to scroll
  // Negative value makes it move down as you scroll down (stays visible longer)
  const parallaxOffset = prefersReducedMotion ? 0 : scrollY * -0.22;
  const accentOffset = prefersReducedMotion ? 0 : scrollY * 0.12;
  const highlightOffset = prefersReducedMotion ? 0 : scrollY * -0.08;

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
        
        {/* Theme-based overlay - lighter to preserve 3D parallax effect */}
        {theme?.background_style === 'gradient' && (
          <div
            className="absolute inset-0"
            style={{
              background: `linear-gradient(135deg, ${theme.primary_color}66, ${theme.secondary_color}66)`
            }}
          />
        )}

        {theme?.background_style === 'solid' && (
          <div
            className="absolute inset-0"
            style={{
              backgroundColor: `${theme.primary_color}66`
            }}
          />
        )}

        {/* For image mode - minimal overlay to keep image visible */}
        {theme?.background_style === 'image' && (
          <div className="absolute inset-0 bg-black/10" />
        )}

        {/* Frost effect for default style (when not explicitly set) */}
        {!theme?.background_style && (
          <>
            {/* Light overlay for text contrast - reduced opacity */}
            <div className="absolute inset-0 bg-slate-900/20" />
          </>
        )}

        {/* Central glow to lift foreground cards - subtle */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background: 'radial-gradient(circle at center, rgba(255,255,255,0.15), rgba(195,255,255,0) 62%)',
            transform: `translate3d(0, ${highlightOffset}px, 0)`
          }}
        />

        {/* Subtle vignette for depth perception - reduced */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(15,23,42,0),rgba(15,23,42,0.35))] opacity-60" />

        {/* Directional depth gradient - lighter at base for better image visibility */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-slate-900/10 to-slate-950/40" />

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