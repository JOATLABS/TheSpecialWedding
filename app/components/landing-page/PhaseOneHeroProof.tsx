import { getMarketingCaptureAsset } from '@/data/marketingCaptureManifest';

import { ProductProofWindow } from './ProductProofWindow';

const heroProof = getMarketingCaptureAsset('dashboard', 'hero');

export function PhaseOneHeroProof() {
  return (
    <div
      className="relative mx-auto w-full max-w-3xl"
      data-testid="phase-one-hero-proof"
      aria-label="The Special Wedding planner command center"
    >
      <div className="absolute -inset-8 rounded-[3rem] bg-[radial-gradient(circle_at_50%_40%,rgba(212,165,165,0.24),transparent_66%)] blur-2xl" aria-hidden="true" />
      <ProductProofWindow
        asset={heroProof}
        alt="Populated Morning View for Marigold and Co. Weddings, showing the complete planner workspace"
        label="Marigold & Co. · Planner workspace"
        sizes="(min-width: 1280px) 680px, (min-width: 1024px) 52vw, calc(100vw - 40px)"
        priority
        variant="hero"
      />
    </div>
  );
}
