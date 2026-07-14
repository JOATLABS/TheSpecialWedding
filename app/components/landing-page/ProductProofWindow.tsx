import Image from 'next/image';

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
    </div>
  );
}
