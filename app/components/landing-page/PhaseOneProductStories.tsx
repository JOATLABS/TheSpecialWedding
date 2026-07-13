import Link from 'next/link';

import DemoVideoLauncher from '@/components/saas/DemoVideoLauncher';
import { PHASE_ONE_PRODUCT_STORIES } from '@/data/phaseOneProductProof';
import type { PublicDemoVideo } from '@/data/publicDemoVideos';

import { ProductProofWindow } from './ProductProofWindow';

type PhaseOneProductStoriesProps = {
  demoVideosByFeatureId?: Record<string, PublicDemoVideo>;
  compact?: boolean;
};

export function PhaseOneProductStories({
  demoVideosByFeatureId = {},
  compact = false,
}: PhaseOneProductStoriesProps) {
  return (
    <div className={compact ? 'space-y-16' : 'space-y-20 sm:space-y-28'}>
      {PHASE_ONE_PRODUCT_STORIES.map((story, index) => {
        const demo = story.featureIds.map((featureId) => demoVideosByFeatureId[featureId]).find((candidate) => candidate?.assetUrl);
        const mediaFirst = index % 2 === 1;

        return (
          <article
            key={story.id}
            className="grid items-center gap-8 lg:grid-cols-[minmax(0,1.12fr)_minmax(320px,0.88fr)] lg:gap-14"
          >
            <div className={mediaFirst ? 'lg:order-2' : undefined}>
              <ProductProofWindow
                asset={story.image}
                alt={story.imageAlt}
                label={`${story.pillar} · Full workspace`}
                sizes="(min-width: 1024px) 55vw, 100vw"
                variant="story"
              />
            </div>

            <div className={mediaFirst ? 'lg:order-1' : undefined}>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-wedding-rose">
                {story.pillar}
              </p>
              <h3 className="mt-4 text-3xl font-semibold leading-tight text-white sm:text-4xl">
                {story.headline}
              </h3>
              <p className="mt-5 text-base leading-8 text-slate-300">{story.description}</p>
              <p className="mt-5 border-l-2 border-wedding-rose/70 pl-4 text-sm font-semibold leading-6 text-slate-100">
                {story.proof}
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-4">
                <Link
                  href="/features"
                  className="text-sm font-semibold text-white underline decoration-wedding-rose/70 underline-offset-4 transition hover:text-wedding-rose"
                >
                  Explore the connected workflow
                </Link>
                {demo ? <DemoVideoLauncher demo={demo} /> : null}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
