import Image from 'next/image';

import type { MarketingCaptureAsset } from '@/data/marketingCaptureManifest';

type ProductProofWindowProps = {
  asset: MarketingCaptureAsset;
  alt: string;
  label: string;
  sizes: string;
  priority?: boolean;
  variant: 'hero' | 'story' | 'card';
};

const WINDOW_CLASSES = {
  hero: 'overflow-hidden rounded-2xl border border-white/12 bg-[#071020] shadow-[0_32px_110px_rgba(0,0,0,0.58)] sm:rounded-[1.75rem]',
  story: 'overflow-hidden rounded-2xl border border-white/10 bg-[#071020] shadow-2xl shadow-black/30 sm:rounded-[1.75rem]',
  card: 'overflow-hidden border-b border-white/10 bg-[#071020]',
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
  const preload = priority || variant === 'story';

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
      <div
        className="relative w-full bg-[#071020]"
        style={{ aspectRatio: frameAspectRatio }}
      >
        <Image
          src={asset.path}
          alt={alt}
          fill
          unoptimized
          loading={preload ? 'eager' : 'lazy'}
          priority={preload}
          quality={90}
          sizes={sizes}
          className="object-contain object-center"
          data-product-proof-image
        />
      </div>
    </div>
  );
}
