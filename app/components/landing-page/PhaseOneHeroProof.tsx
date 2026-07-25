import { getMarketingCaptureAsset } from '@/data/marketingCaptureManifest';
import type { PublicDemoVideo } from '@/data/publicDemoVideos';

import DemoVideoLauncher from '../saas/DemoVideoLauncher';
import { ProductProofWindow } from './ProductProofWindow';

const heroProof = getMarketingCaptureAsset('dashboard', 'hero');

type PhaseOneHeroProofProps = {
  demo: PublicDemoVideo;
};

export function PhaseOneHeroProof({ demo }: PhaseOneHeroProofProps) {
  return (
    <div
      className="relative mx-auto w-full max-w-5xl"
      data-testid="phase-one-hero-proof"
      aria-label="The Special Wedding planner command center"
    >
      <div className="absolute -inset-8 rounded-[3rem] bg-[radial-gradient(circle_at_50%_40%,rgba(212,165,165,0.24),transparent_66%)] blur-2xl" aria-hidden="true" />
      <ProductProofWindow
        asset={heroProof}
        alt="Populated Morning View for Marigold and Co. Weddings, showing the complete planner workspace"
        label="Marigold & Co. · Planner workspace"
        sizes="(min-width: 1280px) 1024px, calc(100vw - 40px)"
        priority
        variant="hero"
      />
      {demo.assetUrl ? (
        <div className="relative mt-6 flex justify-center">
          <DemoVideoLauncher
            demo={demo}
            label="Watch the walkthrough"
            variant="hero"
          />
        </div>
      ) : null}
    </div>
  );
}
