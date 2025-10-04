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
  
  useEffect(() => {
    const handleScroll = () => {
      setScrollY(window.scrollY);
    };
    
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
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
  const parallaxOffset = scrollY * -0.3;
  
  return (
    <>
      {/* Fixed background container */}
      <div className="fixed inset-0 -z-10 overflow-hidden">
        {/* Parallax image layer */}
        <div 
          className="absolute inset-0"
          style={{
            transform: `translateY(${parallaxOffset}px)`,
            willChange: 'transform',
            height: '150%' // Extra height for parallax movement
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
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.28),rgba(255,255,255,0)_60%)] mix-blend-screen" />

        {/* Subtle vignette for depth perception */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(15,23,42,0),rgba(15,23,42,0.55))] opacity-70" />

        {/* Directional depth gradient - darker at base */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-slate-900/20 to-slate-950/60" />

        {/* Highlight streak to simulate light pass */}
        <div className="pointer-events-none absolute inset-x-0 top-[12%] h-2/5 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.45),rgba(255,255,255,0))] opacity-60" />
      </div>
    </>
  );
};