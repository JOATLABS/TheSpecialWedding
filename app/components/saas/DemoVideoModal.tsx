'use client';

import Clock3 from 'lucide-react/dist/esm/icons/clock-3';
import Film from 'lucide-react/dist/esm/icons/film';
import PlayCircle from 'lucide-react/dist/esm/icons/play-circle';
import X from 'lucide-react/dist/esm/icons/x';
import { useEffect } from 'react';

import type { DemoVideo } from '@/data/demoVideos';
import { getDemoVideoStatusLabel } from '@/data/demoVideos';

interface DemoVideoModalProps {
  demo: DemoVideo;
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

  const statusLabel = getDemoVideoStatusLabel(demo.status);
  const durationMinutes = Math.max(1, Math.round(demo.durationSeconds / 60));
  const hasPlayableAsset = Boolean(demo.assetUrl);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="demo-video-title"
      data-testid="demo-video-modal"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-950 shadow-2xl shadow-black/50">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 p-5 sm:p-6">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-wedding-rose">
              {statusLabel}
            </p>
            <h2 id="demo-video-title" className="mt-2 text-2xl font-semibold text-white sm:text-3xl">
              {demo.title}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{demo.audience}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-slate-200 transition hover:border-white/30 hover:text-white"
            aria-label="Close demo video"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="overflow-y-auto p-5 sm:p-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)]">
            <div>
              <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#071020]">
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
                    <video controls className="aspect-video w-full bg-black" poster={demo.thumbnailUrl}>
                      <source src={demo.assetUrl} />
                    </video>
                  )
                ) : (
                  <div className="flex aspect-video flex-col items-center justify-center px-6 text-center">
                    <div className="inline-flex h-16 w-16 items-center justify-center rounded-full border border-wedding-rose/30 bg-wedding-rose/10 text-wedding-rose">
                      <PlayCircle className="h-8 w-8" aria-hidden="true" />
                    </div>
                    <p className="mt-5 text-lg font-semibold text-white">Video temporarily unavailable</p>
                    <p className="mt-2 max-w-md text-sm leading-6 text-slate-300">
                      The walkthrough is being prepared for playback. Please check back shortly or start with the feature overview below.
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
                  <Clock3 className="h-4 w-4 text-wedding-rose" aria-hidden="true" />
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">Length</p>
                  <p className="mt-1 text-sm font-semibold text-white">{durationMinutes} min</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
                  <Film className="h-4 w-4 text-wedding-rose" aria-hidden="true" />
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">Format</p>
                  <p className="mt-1 text-sm font-semibold text-white">Web + social</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
                  <PlayCircle className="h-4 w-4 text-wedding-rose" aria-hidden="true" />
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">Moments</p>
                  <p className="mt-1 text-sm font-semibold text-white">{demo.script.length}</p>
                </div>
              </div>
            </div>

            <div className="space-y-5">
              <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-300">What you'll see</h3>
                <ol className="mt-4 space-y-4">
                  {demo.script.map((step) => (
                    <li key={`${step.timestamp}-${step.action}`} className="border-l border-wedding-rose/35 pl-4">
                      <p className="text-xs font-semibold text-wedding-rose">{step.timestamp}</p>
                      <p className="mt-1 text-sm font-semibold text-white">{step.action}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-300">{step.voiceover}</p>
                    </li>
                  ))}
                </ol>
              </section>

              <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-300">Built for</h3>
                <p className="mt-4 text-sm leading-6 text-slate-300">{demo.audience}</p>
              </section>

              {(demo.socialAssetUrl || demo.transcriptUrl) && (
                <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                  <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-300">More ways to watch</h3>
                  <div className="mt-4 flex flex-col gap-3">
                    {demo.socialAssetUrl && (
                      <a
                        href={demo.socialAssetUrl}
                        className="rounded-full border border-white/15 px-4 py-2 text-center text-sm font-semibold text-white transition hover:border-wedding-rose/50 hover:text-wedding-rose"
                      >
                        Open vertical social cut
                      </a>
                    )}
                    {demo.transcriptUrl && (
                      <a
                        href={demo.transcriptUrl}
                        className="rounded-full border border-white/15 px-4 py-2 text-center text-sm font-semibold text-white transition hover:border-wedding-rose/50 hover:text-wedding-rose"
                      >
                        Read transcript
                      </a>
                    )}
                  </div>
                </section>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
