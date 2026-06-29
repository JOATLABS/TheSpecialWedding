'use client';

import Clock3 from 'lucide-react/dist/esm/icons/clock-3';
import Film from 'lucide-react/dist/esm/icons/film';
import MapPinned from 'lucide-react/dist/esm/icons/map-pinned';
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
                {demo.status === 'published' && demo.assetUrl ? (
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
                    <p className="mt-5 text-lg font-semibold text-white">Recording script approved</p>
                    <p className="mt-2 max-w-md text-sm leading-6 text-slate-300">
                      This clip is ready for local browser capture. The modal shows the exact human walkthrough script until the final recording is attached.
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
                  <Clock3 className="h-4 w-4 text-wedding-rose" aria-hidden="true" />
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">Target length</p>
                  <p className="mt-1 text-sm font-semibold text-white">{durationMinutes} min</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
                  <Film className="h-4 w-4 text-wedding-rose" aria-hidden="true" />
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">Production</p>
                  <p className="mt-1 text-sm font-semibold text-white">{demo.priority.replace('-', ' ')}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
                  <MapPinned className="h-4 w-4 text-wedding-rose" aria-hidden="true" />
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">Routes</p>
                  <p className="mt-1 text-sm font-semibold text-white">{demo.routePlan.length}</p>
                </div>
              </div>
            </div>

            <div className="space-y-5">
              <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-300">Human script</h3>
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
                <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-300">Capture routes</h3>
                <ul className="mt-4 space-y-2">
                  {demo.routePlan.map((route) => (
                    <li key={route} className="rounded-lg bg-slate-900/70 px-3 py-2 font-mono text-xs text-slate-200">
                      {route}
                    </li>
                  ))}
                </ul>
              </section>

              <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-300">Recording checklist</h3>
                <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-300">
                  {demo.recordingChecklist.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-wedding-rose" aria-hidden="true" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 rounded-xl border border-white/10 bg-slate-900/70 p-3 text-xs leading-5 text-slate-400">
                  {demo.captureNotes}
                </p>
              </section>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
