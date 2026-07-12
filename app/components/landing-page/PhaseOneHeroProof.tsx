import Image from 'next/image';

import { getMarketingCaptureAsset } from '@/data/marketingCaptureManifest';

const heroProof = getMarketingCaptureAsset('dashboard', 'hero');

export function PhaseOneHeroProof() {
  return (
    <div
      className="relative mx-auto w-full max-w-3xl"
      data-testid="phase-one-hero-proof"
      aria-label="The Special Wedding planner command center"
    >
      <div className="absolute -inset-8 rounded-[3rem] bg-[radial-gradient(circle_at_50%_40%,rgba(212,165,165,0.24),transparent_66%)] blur-2xl" aria-hidden="true" />
      <div className="relative overflow-hidden rounded-2xl border border-white/12 bg-[#071020] shadow-[0_32px_110px_rgba(0,0,0,0.58)] sm:rounded-[1.75rem]">
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3" aria-hidden="true">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-300/75" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-200/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-300/70" />
        </div>
        <div className="relative aspect-[10/7]">
          <Image
            src={heroProof.path}
            alt="Populated Morning View for Marigold and Co. Weddings, showing active weddings and prioritized planner work"
            fill
            priority
            sizes="(min-width: 1280px) 680px, (min-width: 1024px) 52vw, calc(100vw - 40px)"
            className="object-cover object-top"
          />
        </div>
      </div>
    </div>
  );
}

