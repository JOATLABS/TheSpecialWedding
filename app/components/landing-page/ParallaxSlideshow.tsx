'use client';

import React, { useEffect, useRef } from 'react';
import { GalleryImage } from '@/types/landing';

interface ParallaxSlideshowProps {
  images: GalleryImage[];
}

export const ParallaxSlideshow: React.FC<ParallaxSlideshowProps> = ({ images }) => {
  const layer0 = useRef<HTMLDivElement>(null);
  const layer1 = useRef<HTMLDivElement>(null);
  const layer2 = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY;

      if (layer0.current) {
        layer0.current.style.transform = `translateY(${scrollY * 0.1}px) scale(1.2)`;
      }
      if (layer1.current) {
        layer1.current.style.transform = `translateY(${scrollY * 0.3}px) scale(1.15)`;
      }
      if (layer2.current) {
        layer2.current.style.transform = `translateY(${scrollY * 0.5}px) scale(1.1)`;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // fallback gradient
  if (!images || images.length === 0) {
    return (
      <div className="fixed inset-0 -z-10 bg-gradient-to-br from-wedding-blush to-wedding-navy">
        <div className="absolute inset-0 bg-black/20" />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      {/* Deepest (slowest) */}
      {images[0] && (
        <div
          ref={layer0}
          className="absolute inset-0 bg-cover bg-center opacity-30"
          style={{ backgroundImage: `url(${images[0].url})`, willChange: 'transform' }}
          onError={(e) => (e.currentTarget.style.display = 'none')}
        />
      )}

      {/* Middle */}
      {images[1] && (
        <div
          ref={layer1}
          className="absolute inset-0 bg-cover bg-center opacity-40"
          style={{ backgroundImage: `url(${images[1].url})`, willChange: 'transform' }}
          onError={(e) => (e.currentTarget.style.display = 'none')}
        />
      )}

      {/* Front (fastest) */}
      {images[2] && (
        <div
          ref={layer2}
          className="absolute inset-0 bg-cover bg-center opacity-50"
          style={{ backgroundImage: `url(${images[2].url})`, willChange: 'transform' }}
          onError={(e) => (e.currentTarget.style.display = 'none')}
        />
      )}

      {/* Dark tint for readability */}
      <div className="absolute inset-0 bg-gradient-to-br from-black/20 via-transparent to-black/20" />
    </div>
  );
};
