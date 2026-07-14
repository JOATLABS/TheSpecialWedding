'use client';

import Image from 'next/image';
import { useEffect, useState } from 'react';
import type { GalleryImage } from '@/types/landing';

interface LandingGalleryPreviewProps {
  images: GalleryImage[];
  loading: boolean;
  error?: boolean;
  onRetry?: () => void;
}

export function LandingGalleryPreview({
  images,
  loading,
  error = false,
  onRetry,
}: LandingGalleryPreviewProps) {
  const [failedImageUrls, setFailedImageUrls] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setFailedImageUrls(new Set());
  }, [images]);

  const retryGallery = () => {
    setFailedImageUrls(new Set());
    onRetry?.();
  };

  if (loading) {
    return (
      <div className="mb-6" role="status" aria-live="polite">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4" aria-hidden="true">
          {Array.from({ length: 4 }, (_, index) => (
            <div
              key={index}
              className="h-48 animate-pulse rounded-lg bg-white/45 shadow-lg dark:bg-slate-800/55"
            />
          ))}
        </div>
        <p className="mt-4 text-center text-sm text-gray-600 dark:text-gray-300">
          Loading gallery…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="mb-6 rounded-lg border border-amber-200 bg-amber-50/90 px-5 py-6 text-center dark:border-amber-900/60 dark:bg-amber-950/45"
        role="alert"
      >
        <h3 className="font-semibold text-amber-950 dark:text-amber-100">
          Gallery temporarily unavailable
        </h3>
        <p className="mt-1 text-sm text-amber-800 dark:text-amber-200">
          We couldn&apos;t load these photos. Please try again.
        </p>
        {onRetry ? (
          <button
            type="button"
            onClick={retryGallery}
            className="mt-4 rounded-lg border border-amber-700 px-4 py-2 text-sm font-semibold text-amber-900 transition-colors hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-700 focus:ring-offset-2 dark:border-amber-300 dark:text-amber-100 dark:hover:bg-amber-900/50"
          >
            Try gallery again
          </button>
        ) : null}
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <p className="mb-6 text-center text-gray-600 dark:text-gray-300">
        Photos will be added soon!
      </p>
    );
  }

  const previewImages = images.slice(0, 8);
  const visibleImages = previewImages
    .map((image, index) => ({ image, index }))
    .filter(({ image }) => !failedImageUrls.has(image.url));

  if (visibleImages.length === 0) {
    return (
      <div
        className="mb-6 rounded-lg bg-white/65 px-5 py-6 text-center shadow-sm dark:bg-slate-900/65"
        role="alert"
      >
        <h3 className="font-semibold text-gray-800 dark:text-gray-100">
          Gallery photos could not be displayed
        </h3>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
          Try loading the gallery again.
        </p>
        {onRetry ? (
          <button
            type="button"
            onClick={retryGallery}
            className="mt-4 rounded-lg border border-gray-500 px-4 py-2 text-sm font-semibold text-gray-800 transition-colors hover:bg-white focus:outline-none focus:ring-2 focus:ring-gray-600 focus:ring-offset-2 dark:border-gray-300 dark:text-gray-100 dark:hover:bg-slate-800"
          >
            Try gallery again
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
      {visibleImages.map(({ image, index }) => (
        <div key={image.key} className="relative h-48 w-full overflow-hidden rounded-lg shadow-lg">
          <Image
            src={image.url}
            alt={image.alt || `Wedding gallery photo ${index + 1}`}
            fill
            className="object-cover"
            sizes="(max-width: 768px) 50vw, 25vw"
            onError={() => {
              setFailedImageUrls((currentUrls) => {
                const nextUrls = new Set(currentUrls);
                nextUrls.add(image.url);
                return nextUrls;
              });
            }}
          />
        </div>
      ))}
    </div>
  );
}
