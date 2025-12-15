'use client';

import React, { useState, useEffect, useCallback, useRef, memo } from 'react';
import Image from 'next/image';

interface GalleryImage {
  key: string;
  url: string;
}

interface GalleryGridProps {
  images: GalleryImage[];
  columns?: {
    sm?: number;
    md?: number;
    lg?: number;
  };
}

// Memoized Thumbnail Component to prevent re-rendering all thumbnails on selection change
const Thumbnail = memo(({
  img,
  index,
  isSelected,
  onClick
}: {
  img: GalleryImage;
  index: number;
  isSelected: boolean;
  onClick: (index: number, e: React.MouseEvent) => void;
}) => {
  return (
    <button
      onClick={(e) => onClick(index, e)}
      className={`relative w-16 h-16 rounded overflow-hidden transition-all ${
        isSelected
          ? 'ring-2 ring-white scale-110'
          : 'opacity-70 hover:opacity-100'
      }`}
    >
      <Image
        src={img.url}
        alt={`Thumbnail ${index + 1}`}
        fill
        sizes="64px"
        className="object-cover"
      />
    </button>
  );
});

Thumbnail.displayName = 'Thumbnail';

const GalleryGridComponent: React.FC<GalleryGridProps> = ({
  images, 
  columns = { sm: 2, md: 3, lg: 4 } 
}) => {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  // Optimization: Use useRef for loadedImages to prevent re-renders on background load
  const loadedImagesRef = useRef<Set<number>>(new Set());

  // Preload adjacent images for smooth navigation
  const preloadAdjacentImages = useCallback((index: number) => {
    const indicesToLoad = [
      index - 1, // Previous
      index,     // Current
      index + 1  // Next
    ].filter(i => i >= 0 && i < images.length);

    indicesToLoad.forEach(i => {
      if (!loadedImagesRef.current.has(i)) {
        const img = new window.Image();
        img.src = images[i].url;
        img.onload = () => {
          loadedImagesRef.current.add(i);
        };
      }
    });
  }, [images]);

  // Open lightbox
  const openLightbox = useCallback((index: number) => {
    setSelectedIndex(index);
    setIsLoading(true);
    preloadAdjacentImages(index);
    // Prevent body scroll when lightbox is open
    document.body.style.overflow = 'hidden';
  }, [preloadAdjacentImages]);

  // Close lightbox
  const closeLightbox = useCallback(() => {
    setSelectedIndex(null);
    document.body.style.overflow = 'unset';
  }, []);

  // Navigate to previous image
  const goToPrevious = useCallback(() => {
    setSelectedIndex((current) => {
      if (current === null || current <= 0) {
        return current;
      }
      const newIndex = current - 1;
      setIsLoading(true);
      preloadAdjacentImages(newIndex);
      return newIndex;
    });
  }, [preloadAdjacentImages]);

  // Navigate to next image
  const goToNext = useCallback(() => {
    setSelectedIndex((current) => {
      if (current === null || current >= images.length - 1) {
        return current;
      }
      const newIndex = current + 1;
      setIsLoading(true);
      preloadAdjacentImages(newIndex);
      return newIndex;
    });
  }, [images.length, preloadAdjacentImages]);

  // Handler for thumbnail click
  const handleThumbnailClick = useCallback((index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedIndex(index);
    setIsLoading(true);
    preloadAdjacentImages(index);
  }, [preloadAdjacentImages]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (selectedIndex === null) return;

      switch (e.key) {
        case 'Escape':
          closeLightbox();
          break;
        case 'ArrowLeft':
          goToPrevious();
          break;
        case 'ArrowRight':
          goToNext();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [closeLightbox, goToNext, goToPrevious, selectedIndex]);

  // Touch gesture handling for mobile
  const [touchStart, setTouchStart] = useState<number | null>(null);
  const [touchEnd, setTouchEnd] = useState<number | null>(null);

  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStart(e.targetTouches[0].clientX);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    
    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > 50;
    const isRightSwipe = distance < -50;

    if (isLeftSwipe) {
      goToNext();
    } else if (isRightSwipe) {
      goToPrevious();
    }

    setTouchStart(null);
    setTouchEnd(null);
  };

  const gridCols = `grid-cols-1 sm:grid-cols-${columns.sm} md:grid-cols-${columns.md} lg:grid-cols-${columns.lg}`;

  return (
    <>
      {/* Image Grid */}
      <div className={`grid ${gridCols} gap-6`}>
        {images.map((img, index) => (
          <div
            key={img.key}
            onClick={() => openLightbox(index)}
            className="relative w-full h-64 rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-all duration-300 group cursor-pointer"
          >
            <Image
              src={img.url}
              alt={`Wedding photo ${index + 1}`}
              fill
              sizes="(max-width: 640px) 100vw, (max-width: 768px) 50vw, (max-width: 1024px) 33vw, 25vw"
              className="object-cover group-hover:scale-105 transition-transform duration-500"
              loading="lazy"
            />
            <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-opacity duration-300 flex items-center justify-center">
              <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                <svg className="w-12 h-12 text-white drop-shadow-lg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                </svg>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Lightbox */}
      {selectedIndex !== null && (
        <div 
          className="fixed inset-0 z-50 bg-black bg-opacity-95 flex items-center justify-center"
          onClick={closeLightbox}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        >
          {/* Close button */}
          <button
            onClick={closeLightbox}
            className="absolute top-4 right-4 z-50 text-white hover:text-gray-300 transition-colors"
            aria-label="Close"
          >
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {/* Image counter */}
          <div className="absolute top-4 left-4 text-white text-lg">
            {selectedIndex + 1} / {images.length}
          </div>

          {/* Previous button */}
          {selectedIndex > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                goToPrevious();
              }}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-white hover:text-gray-300 transition-colors p-2"
              aria-label="Previous image"
            >
              <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          )}

          {/* Next button */}
          {selectedIndex < images.length - 1 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                goToNext();
              }}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-white hover:text-gray-300 transition-colors p-2"
              aria-label="Next image"
            >
              <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}

          {/* Main image */}
          <div 
            className="relative max-w-[90vw] max-h-[90vh] w-full h-full flex items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent"></div>
              </div>
            )}
            <Image
              src={images[selectedIndex].url}
              alt={`Wedding photo ${selectedIndex + 1}`}
              fill
              className="object-contain"
              sizes="90vw"
              priority
              quality={90}
              onLoad={() => setIsLoading(false)}
            />
          </div>

          {/* Thumbnail strip at bottom */}
          <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 p-4 overflow-x-auto">
            <div className="flex gap-2 justify-center">
              {images.map((img, index) => (
                <Thumbnail
                  key={img.key}
                  img={img}
                  index={index}
                  isSelected={index === selectedIndex}
                  onClick={handleThumbnailClick}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export const GalleryGrid = memo(GalleryGridComponent);
