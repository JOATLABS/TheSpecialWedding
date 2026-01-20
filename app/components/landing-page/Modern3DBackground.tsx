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

  // Deep parallax effect - background moves slower and opposite to scroll
  const parallaxOffset = prefersReducedMotion ? 0 : scrollY * -0.22;

  return (
    <>
      {/* Fixed background container */}
      <div className="fixed inset-0 -z-10 overflow-hidden">
        {/* Parallax image layer */}
        <div
          className="absolute inset-0"
          style={{
            transform: `translate3d(0, ${parallaxOffset}px, 0) scale(1.08)`,
            willChange: 'transform',
            height: '155%',
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