"use client";

import Link from 'next/link';

import DemoVideoLauncher from '@/components/saas/DemoVideoLauncher';
import { PHASE_ONE_PRODUCT_STORIES } from '@/data/phaseOneProductProof';
import type { PublicDemoVideo } from '@/data/publicDemoVideos';

import { ProductProofWindow } from './ProductProofWindow';

type FeatureShowcaseProps = {
  demoVideosByFeatureId: Record<string, PublicDemoVideo>;
};

/**
 * Landing-page showcase: one lead outcome shown large, the remaining three named
 * as quiet teasers that hand off to /features.
 *
 * The landing pitches; /features explains. The full four-story treatment (each with
 * its supporting product windows) still lives on /features via PhaseOneProductStories,
 * so this surface stays a single focal point instead of a twelve-window tour.
 */
export function FeatureShowcase({ demoVideosByFeatureId }: FeatureShowcaseProps) {
  const [lead, ...rest] = PHASE_ONE_PRODUCT_STORIES;
  const leadDemo = lead.featureIds
    .map((featureId) => demoVideosByFeatureId[featureId])
    .find((candidate) => candidate?.assetUrl);

  return (
    <div className="space-y-16 sm:space-y-20">
      <article className="mx-auto flex min-w-0 max-w-3xl flex-col items-center text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-wedding-rose">
          {lead.pillar}
        </p>
        <h3 className="mt-5 text-4xl font-semibold leading-[1.05] tracking-[-0.02em] text-white sm:text-5xl">
          One plan. Three clear views.
        </h3>
        <p className="mt-6 text-lg leading-8 text-slate-300">
          Planner, couple, and guests follow the same wedding record — each seeing only
          what it should.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-5">
          <Link
            href="/features"
            className="text-sm font-semibold text-white underline decoration-wedding-rose/70 underline-offset-4 transition hover:text-wedding-rose"
          >
            See every workflow ›
          </Link>
          {leadDemo ? <DemoVideoLauncher demo={leadDemo} /> : null}
        </div>
      </article>

      <div className="mx-auto min-w-0 max-w-5xl">
        <ProductProofWindow
          asset={lead.image}
          alt={lead.imageAlt}
          label={`${lead.pillar} · Full workspace`}
          sizes="(min-width: 1024px) 70vw, 100vw"
          priority
          variant="story"
        />
      </div>

      <div className="mx-auto grid min-w-0 max-w-5xl gap-10 border-t border-white/10 pt-14 sm:grid-cols-3 sm:gap-8">
        {rest.map((story) => (
          <div key={story.id} className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-wedding-rose">
              {story.pillar}
            </p>
            <p className="mt-3 text-lg font-semibold leading-snug text-white">
              {story.headline}
            </p>
            <Link
              href="/features"
              className="mt-4 inline-block text-sm font-semibold text-slate-300 underline decoration-white/20 underline-offset-4 transition hover:text-white"
            >
              See how it works ›
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
