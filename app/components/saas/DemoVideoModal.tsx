'use client';

import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react';
import X from 'lucide-react/dist/esm/icons/x.mjs';
import { useRef } from 'react';

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
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  if (!open) return null;

  const hasPlayableAsset = Boolean(demo.assetUrl);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      initialFocus={closeButtonRef}
      className="relative z-50"
      data-testid="demo-video-modal"
    >
      <DialogBackdrop
        className="fixed inset-0 bg-slate-950/85 backdrop-blur-sm"
        data-testid="demo-video-backdrop"
      />

      <div className="fixed inset-0 overflow-y-auto">
        <div className="flex min-h-full items-center justify-center px-4 py-6">
          <DialogPanel
            className="relative w-full max-w-5xl overflow-hidden rounded-2xl border border-white/10 bg-black shadow-2xl shadow-black/60"
            data-testid="demo-video-panel"
          >
            <DialogTitle className="sr-only">{demo.title}</DialogTitle>
            <button
              ref={closeButtonRef}
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
                  tabIndex={0}
                  className="aspect-video w-full"
                />
              ) : (
                <video
                  controls
                  autoPlay
                  playsInline
                  tabIndex={0}
                  className="aspect-video w-full bg-black"
                  poster={demo.thumbnailUrl}
                >
                  <source src={demo.assetUrl} />
                  {demo.captionUrl ? (
                    <track
                      kind="captions"
                      src={demo.captionUrl}
                      srcLang="en"
                      label="English"
                      default
                    />
                  ) : null}
                </video>
              )
            ) : (
              <div className="flex aspect-video items-center justify-center bg-[radial-gradient(circle_at_30%_20%,rgba(212,165,165,0.22),transparent_36%),linear-gradient(135deg,#0f172a,#020617)] px-6 text-center">
                <div className="max-w-xl">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-rose-200">Walkthrough being refreshed</p>
                  <p className="mt-4 text-2xl font-semibold text-white">{demo.title}</p>
                  <p className="mt-3 text-sm leading-6 text-slate-300">{demo.audience}</p>
                </div>
              </div>
            )}
          </DialogPanel>
        </div>
      </div>
    </Dialog>
  );
}
