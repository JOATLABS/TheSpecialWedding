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
  theme,
}) => {
  const [scrollY, setScrollY] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrollY(window.scrollY);
    };

    const handleResize = () => {
      setViewportHeight(window.innerHeight);
    };

    handleResize(); // set initial value
    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleResize, { passive: true });
    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
    };
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

  // Deep parallax effect - background moves slower and opposite to scroll.
  // The image is 180% tall, scaled 1.08 → effective ~194% of viewport.
  // Extra space below center ≈ 0.94 * vh. Clamp so bottom edge never
  // rises above the viewport, preventing the white-gap glitch.
  const IMAGE_HEIGHT_PCT = 1.80;
  const SCALE = 1.08;
  const PARALLAX_RATE = 0.15;
  const maxUp = viewportHeight > 0
    ? (IMAGE_HEIGHT_PCT * SCALE - 1) * viewportHeight * 0.5
    : 9999;
  const rawOffset = prefersReducedMotion ? 0 : scrollY * -PARALLAX_RATE;
  const parallaxOffset = Math.max(rawOffset, -maxUp);

  const primaryColor = theme?.primary_color || '#1e3a5f';

  return (
    <>
      {/* Fixed background container */}
      <div
        className="fixed inset-0 -z-10 overflow-hidden dark:bg-gray-950"
        style={{ backgroundColor: `${primaryColor}10` }}
      >
        {/* Parallax image layer */}
        <div
          className="absolute inset-0"
          style={{
            transform: `translate3d(0, ${parallaxOffset}px, 0) scale(${SCALE})`,
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