'use client';

import React, { useEffect, useState, useRef } from 'react';
import Image from 'next/image';
import { ThemeConfig } from '@/types/wedding';

interface Modern3DBackgroundProps {
  imageUrl?: string;
  fallbackImages?: string[];
  theme?: ThemeConfig;
  /** Height of one full "page" in the infinite scroll.
   *  When provided, scrollY is normalised with modulo so the
   *  parallax position matches at every loop point — eliminating
   *  the visible jump when InfiniteScrollWrapper resets. */
  loopHeight?: number;
  /** Shared ref holding the already-normalised scroll position written
   *  by InfiniteScrollWrapper on every scroll event.  When provided the
   *  parallax rAF reads from this ref instead of window.scrollY, which
   *  eliminates any possible 1-frame desync at the loop boundary. */
  normalizedScrollRef?: React.RefObject<number>;
}

export const Modern3DBackground: React.FC<Modern3DBackgroundProps> = ({
  imageUrl,
  fallbackImages = [],
  theme,
  loopHeight = 0,
  normalizedScrollRef,
}) => {
  const [viewportHeight, setViewportHeight] = useState(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  // Use a ref for scroll position and rAF for smooth updates —
  // avoids a full React re-render on every scroll event.
  const scrollRef = useRef(0);
  const parallaxLayerRef = useRef<HTMLDivElement>(null);
  const rafId = useRef(0);

  useEffect(() => {
    const handleResize = () => {
      setViewportHeight(window.innerHeight);
    };
    handleResize();
    window.addEventListener('resize', handleResize, { passive: true });
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const syncPreference = () => setPrefersReducedMotion(motionQuery.matches);
    syncPreference();
    motionQuery.addEventListener('change', syncPreference);
    return () => motionQuery.removeEventListener('change', syncPreference);
  }, []);

  // ── Parallax constants ──
  const IMAGE_HEIGHT_PCT = 1.80;
  const SCALE = 1.08;
  const PARALLAX_RATE = 0.15;

  // Drive parallax via rAF so it stays buttery-smooth and
  // perfectly in sync with the browser's own composite step.
  useEffect(() => {
    if (prefersReducedMotion) return;

    const maxUp = viewportHeight > 0
      ? (IMAGE_HEIGHT_PCT * SCALE - 1) * viewportHeight * 0.5
      : 9999;

    const tick = () => {
      // Prefer the shared normalised ref (written synchronously by
      // InfiniteScrollWrapper on every scroll event) to avoid any
      // 1-frame desync at the loop boundary.  Fall back to computing
      // the modulo ourselves when the ref isn't wired up.
      let y: number;
      if (normalizedScrollRef && loopHeight > 0) {
        y = normalizedScrollRef.current;
      } else {
        y = window.scrollY;
        if (loopHeight > 0) {
          y = y % loopHeight;
        }
      }

      scrollRef.current = y;

      const rawOffset = y * -PARALLAX_RATE;
      const clamped = Math.max(rawOffset, -maxUp);

      if (parallaxLayerRef.current) {
        parallaxLayerRef.current.style.transform =
          `translate3d(0, ${clamped}px, 0) scale(${SCALE})`;
      }

      rafId.current = requestAnimationFrame(tick);
    };

    rafId.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId.current);
  }, [loopHeight, viewportHeight, prefersReducedMotion, normalizedScrollRef]);

  // Use featured image or first fallback image
  const backgroundImage = imageUrl || fallbackImages[0];

  if (!backgroundImage) {
    // Gradient fallback using theme colors if no images
    const primaryColor = theme?.primary_color || '#1e3a5f';
    const secondaryColor = theme?.secondary_color || '#d4af37';
    const accentColor = theme?.accent_color || '#c8847e';

    return (
      <div className="fixed inset-0 -z-10">
        <div
          className="absolute inset-0 transition-colors duration-500"
          style={{
            background: `linear-gradient(135deg, ${primaryColor}15, ${secondaryColor}20, ${accentColor}15)`,
          }}
        />
        {/* Dark mode base background */}
        <div className="absolute inset-0 bg-transparent dark:bg-gray-900/80 transition-colors duration-500" />
      </div>
    );
  }

  const primaryColor = theme?.primary_color || '#1e3a5f';

  return (
    <>
      {/* Fixed background container */}
      <div
        className="fixed inset-0 -z-10 overflow-hidden dark:bg-gray-950"
        style={{ backgroundColor: `${primaryColor}10` }}
      >
        {/* Parallax image layer — driven by rAF, not React state */}
        <div
          ref={parallaxLayerRef}
          className="absolute inset-0"
          style={{
            transform: `translate3d(0, 0px, 0) scale(${SCALE})`,
            willChange: 'transform',
            height: `${IMAGE_HEIGHT_PCT * 100}%`,
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

      </div>
    </>
  );
};
