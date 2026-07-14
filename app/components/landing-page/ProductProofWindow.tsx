'use client';

import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from '@headlessui/react';
import Maximize2 from 'lucide-react/dist/esm/icons/maximize-2.mjs';
import X from 'lucide-react/dist/esm/icons/x.mjs';
import Image from 'next/image';
import { useRef, useState } from 'react';

import {
  isMarketingCaptureAssetApproved,
  type MarketingCaptureAsset,
} from '@/data/marketingCaptureManifest';

type ProductProofWindowProps = {
  asset: MarketingCaptureAsset;
  alt: string;
  label: string;
  sizes: string;
  priority?: boolean;
  variant: 'hero' | 'story' | 'supporting' | 'card';
};

const WINDOW_CLASSES = {
  hero: 'min-w-0 overflow-hidden rounded-2xl border border-white/12 bg-[#071020] shadow-[0_32px_110px_rgba(0,0,0,0.58)] sm:rounded-[1.75rem]',
  story: 'min-w-0 overflow-hidden rounded-2xl border border-white/10 bg-[#071020] shadow-2xl shadow-black/30 sm:rounded-[1.75rem]',
  supporting: 'min-w-0 overflow-hidden rounded-xl border border-white/10 bg-[#071020] shadow-lg shadow-black/20',
  card: 'min-w-0 overflow-hidden border-b border-white/10 bg-[#071020]',
} as const;

const MATTE_CLASSES = {
  hero: 'p-2 sm:p-3',
  story: 'p-2 sm:p-3',
  supporting: 'p-1.5 sm:p-2',
  card: 'p-2',
} as const;

export function ProductProofWindow({
  asset,
  alt,
  label,
  sizes,
  priority = false,
  variant,
}: ProductProofWindowProps) {
  const [expanded, setExpanded] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const frameAspectRatio = asset.render.frameAspectRatio.replace(':', ' / ');
  const preload = priority;
  const isApprovedForPublication = isMarketingCaptureAssetApproved(asset);

  return (
    <div
      className={WINDOW_CLASSES[variant]}
      data-product-proof={variant}
      data-proof-context="full-window"
      data-proof-fit={asset.render.fit}
      data-proof-zoom={String(asset.render.zoom)}
    >
      <div
        className="flex h-8 items-center gap-2 border-b border-white/10 bg-white/[0.035] px-3 text-[10px] font-medium tracking-[0.12em] text-slate-400 sm:h-9 sm:px-4"
        aria-hidden="true"
      >
        <span className="h-2 w-2 rounded-full bg-rose-300/75" />
        <span className="h-2 w-2 rounded-full bg-amber-200/70" />
        <span className="h-2 w-2 rounded-full bg-emerald-300/70" />
        <span className="ml-2 truncate uppercase">{label}</span>
      </div>
      <div className={`bg-[#071020] ${MATTE_CLASSES[variant]}`} data-proof-matte>
        <div
          className="relative w-full"
          style={{ aspectRatio: frameAspectRatio }}
          data-proof-frame
        >
          {isApprovedForPublication ? (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              aria-haspopup="dialog"
              aria-label={`Expand ${label} product image`}
              className="group relative block h-full w-full cursor-zoom-in focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose"
              data-product-proof-expand
            >
              <Image
                src={asset.path}
                alt={alt}
                fill
                unoptimized
                loading={preload ? 'eager' : 'lazy'}
                priority={preload}
                sizes={sizes}
                className="object-contain object-center"
                data-product-proof-image
              />
              <span className="pointer-events-none absolute bottom-2 right-2 inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-slate-950/85 px-2.5 py-1.5 text-[11px] font-semibold tracking-wide text-white shadow-lg backdrop-blur-sm transition group-hover:border-white/40 group-hover:bg-slate-950 group-focus-visible:border-white/50">
                <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
                Expand
              </span>
            </button>
          ) : (
            <div
              className="flex h-full w-full items-center justify-center rounded-lg border border-white/8 bg-[radial-gradient(circle_at_50%_20%,rgba(99,102,241,0.16),transparent_58%)] px-6 text-center"
              role="status"
              data-product-proof-refreshing
            >
              <p className="max-w-sm text-sm font-medium leading-6 text-slate-300">
                Current product image is being refreshed
              </p>
            </div>
          )}
        </div>
      </div>

      {isApprovedForPublication ? (
        <Dialog
          open={expanded}
          onClose={setExpanded}
          initialFocus={closeButtonRef}
          className="relative z-[70]"
          data-testid="product-proof-lightbox"
        >
          <DialogBackdrop className="fixed inset-0 bg-slate-950/90 backdrop-blur-md" />
          <div className="fixed inset-0 overflow-y-auto p-4 sm:p-6">
            <div className="flex min-h-full items-center justify-center">
              <DialogPanel className="relative flex w-fit max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-white/15 bg-[#071020] shadow-2xl shadow-black/70 sm:max-w-[calc(100vw-3rem)]">
                <div className="flex min-h-12 items-center justify-between gap-4 border-b border-white/10 bg-white/[0.04] px-4 py-2 text-white">
                  <DialogTitle className="min-w-0 truncate text-sm font-semibold">
                    {label} full-size product image
                  </DialogTitle>
                  <button
                    ref={closeButtonRef}
                    type="button"
                    onClick={() => setExpanded(false)}
                    aria-label="Close full-size product image"
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/15 bg-slate-950/70 text-slate-200 transition hover:border-white/30 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
                <div className="flex min-h-0 items-center justify-center bg-[#071020] p-2 sm:p-3">
                  <Image
                    src={asset.path}
                    alt={`${alt}, full-size view`}
                    width={asset.width}
                    height={asset.height}
                    unoptimized
                    priority
                    sizes="(min-width: 1024px) 90vw, calc(100vw - 32px)"
                    className="block h-auto max-h-[calc(100vh-6.5rem)] w-auto max-w-full object-contain object-center"
                    data-product-proof-expanded-image
                  />
                </div>
              </DialogPanel>
            </div>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}
