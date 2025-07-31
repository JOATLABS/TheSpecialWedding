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

  // Deep parallax effect - background moves slower than scroll
  const parallaxOffset = scrollY * 0.5;
  
  return (
    <>
      {/* Fixed background container */}
      <div className="fixed inset-0 -z-10 overflow-hidden">
        {/* Parallax image layer */}
        <div 
          className="absolute inset-0 scale-110"
          style={{
            transform: `translateY(${parallaxOffset}px) scale(1.1)`,
            willChange: 'transform'
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
            <div className="absolute inset-0 bg-black/30" />
            
            {/* Blur overlay for depth */}
            <div className="absolute inset-0 backdrop-blur-[2px]" />
          </>
        )}
        
        {/* Depth gradient - darker at bottom for valley effect */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/50" />
      </div>

      {/* Spacer for content */}
      <div className="relative z-0" />
    </>
  );
};