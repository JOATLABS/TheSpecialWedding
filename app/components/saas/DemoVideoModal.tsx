'use client';

import X from 'lucide-react/dist/esm/icons/x';
import { useEffect } from 'react';

import type { PublicDemoVideo } from '@/data/publicDemoVideos';

interface DemoVideoModalProps {
  demo: PublicDemoVideo;
  open: boolean;
  onClose: () => void;
}

function isEmbeddableVideoUrl(url: string): boolean {
  return /youtube\.com|youtu\.be|vimeo\.com/.test(url);
}

export default function DemoVideoModal({ demo, open, onClose }: DemoVideoModalProps) {
  useEffect(() => {
    if (!open) return undefined;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  const hasPlayableAsset = Boolean(demo.assetUrl);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 px-4 py-6 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={demo.title}
      data-testid="demo-video-modal"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-5xl overflow-hidden rounded-2xl border border-white/10 bg-black shadow-2xl shadow-black/60">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 z-10 inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-slate-950/80 text-slate-200 backdrop-blur transition hover:border-white/30 hover:text-white"
          aria-label="Close demo video"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>

        {hasPlayableAsset && demo.assetUrl ? (
          isEmbeddableVideoUrl(demo.assetUrl) ? (
            <iframe
              title={demo.title}
              src={demo.assetUrl}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="aspect-video w-full"
            />
          ) : (
            <video controls autoPlay playsInline className="aspect-video w-full bg-black" poster={demo.thumbnailUrl}>
              <source src={demo.assetUrl} />
            </video>
          )
        ) : (
          <div className="flex aspect-video items-center justify-center px-6 text-center">
            <p className="text-sm font-semibold text-white">Video temporarily unavailable.</p>
          </div>
        )}
      </div>
    </div>
  );
}
