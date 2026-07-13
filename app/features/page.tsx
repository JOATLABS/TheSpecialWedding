import Link from 'next/link';

import { PhaseOneProductStories } from '@/components/landing-page/PhaseOneProductStories';
import { ProductProofWindow } from '@/components/landing-page/ProductProofWindow';
import DemoVideoLauncher from '@/components/saas/DemoVideoLauncher';
import SaasNav from '@/components/saas/SaasNav';
import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import { FEATURE_DEMO_VIDEOS, toPublicDemoVideo } from '@/data/demoVideos';
import { MARKETING_FEATURES } from '@/data/marketingFeatures';
import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';

const featureDemosByFeatureId = Object.fromEntries(
  FEATURE_DEMO_VIDEOS.map((demo) => [demo.featureId, toPublicDemoVideo(demo)]),
);

export default function FeaturesPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Features', href: '/features' },
        ]}
      />

      <section className="relative isolate overflow-hidden px-6 pb-20 pt-32 sm:px-10 sm:pt-36">
        <div
          className="absolute inset-0 -z-10 bg-[radial-gradient(800px_520px_at_18%_0%,rgba(212,165,165,0.26),transparent_70%),radial-gradient(1000px_620px_at_86%_0%,rgba(232,196,106,0.15),transparent_66%)]"
          aria-hidden="true"
        />
        <div className="mx-auto max-w-5xl text-center">
          <h1 className="text-4xl font-semibold leading-tight tracking-[-0.025em] text-white sm:text-5xl md:text-6xl">
            One connected operating system, built specifically for wedding planners.
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-base leading-8 text-slate-300 sm:text-lg">
            Protect planner time, give couples a calmer experience, and keep every wedding surface reading from one planner-owned record.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href="/#pricing"
              className="inline-flex min-h-12 items-center justify-center rounded-full bg-wedding-rose px-7 py-3 text-base font-semibold text-slate-950 shadow-lg shadow-wedding-rose/25 transition hover:bg-wedding-blush focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-wedding-rose"
            >
              View planner plans
            </a>
            <Link
              href="#showcase"
              className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/20 px-7 py-3 text-base font-semibold text-white transition hover:border-white/40 hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
            >
              See the product story
            </Link>
          </div>
        </div>
      </section>

      <section id="showcase" className="scroll-mt-24 border-y border-white/5 bg-white/[0.015] px-6 py-20 sm:px-10 sm:py-24">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-[0.26em] text-wedding-rose">
              Connected outcomes
            </p>
            <h2 className="mt-4 text-3xl font-semibold text-white sm:text-5xl">
              The four reasons the workspace matters.
            </h2>
          </div>
          <PhaseOneProductStories demoVideosByFeatureId={featureDemosByFeatureId} compact />
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20 sm:px-10 sm:py-24">
        <div className="mb-12 max-w-3xl">
          <p className="text-sm font-semibold uppercase tracking-[0.26em] text-wedding-rose">
            Detailed capabilities
          </p>
          <h2 className="mt-4 text-3xl font-semibold text-white sm:text-5xl">
            Explore every planning surface.
          </h2>
          <p className="mt-5 text-base leading-7 text-slate-300">
            The details are here for evaluation, but each surface earns its place by staying connected to the wedding record—not by adding another isolated tool.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {MARKETING_FEATURES.map((feature, index) => {
            const demo = featureDemosByFeatureId[feature.id];

            return (
              <article
                key={feature.id}
                className="group overflow-hidden rounded-2xl border border-white/10 bg-white/[0.035] transition hover:border-wedding-rose/35"
              >
                <ProductProofWindow
                  asset={feature.image}
                  alt={`${feature.title} full product window from the fictional Marigold and Co. planner workspace`}
                  label={feature.title}
                  sizes="(min-width: 1024px) 31vw, (min-width: 640px) 48vw, 100vw"
                  priority={index === 0}
                  variant="card"
                />
                <div className="p-6">
                  <div className="flex items-center gap-3">
                    <span className="text-xl" aria-hidden="true">{feature.icon}</span>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                      {feature.category}
                    </p>
                  </div>
                  <h3 className="mt-4 text-xl font-semibold text-white">{feature.title}</h3>
                  <p className="mt-3 text-sm font-medium leading-6 text-slate-300">{feature.tagline}</p>
                  {demo?.assetUrl ? (
                    <div className="mt-5">
                      <DemoVideoLauncher demo={demo} />
                    </div>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="border-y border-white/5 bg-white/[0.02] px-6 py-12 sm:px-10">
        <div className="mx-auto flex max-w-5xl flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-white">Need line-by-line product research?</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Keep the connected story here, and use the dedicated research pages when procurement needs detailed evidence.
            </p>
          </div>
          <Link
            href="/compare"
            className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-full border border-white/20 px-6 py-2.5 text-sm font-semibold text-white transition hover:border-white/40 hover:bg-white/5"
          >
            Review comparisons
          </Link>
        </div>
      </section>

      <section className="relative overflow-hidden px-6 py-20 text-center sm:px-10">
        <div className="absolute inset-0 bg-gradient-to-t from-transparent via-wedding-rose/[0.045] to-transparent" aria-hidden="true" />
        <div className="relative mx-auto max-w-3xl">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">
            Start one wedding. Connect the rest of the work.
          </h2>
          <p className="mt-4 text-base text-slate-300">Your first planner workspace is free.</p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href={PUBLIC_LOGIN_PATH}
              className="inline-flex min-h-12 items-center justify-center rounded-full bg-white px-7 py-3 text-base font-semibold text-slate-950 transition hover:bg-slate-100"
            >
              Start one wedding free
            </Link>
            <a
              href="mailto:hello@thespecialwedding.io?subject=Planner workspace walkthrough"
              className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/20 px-7 py-3 text-base font-semibold text-white transition hover:border-white/40"
            >
              Request a walkthrough
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/5 bg-slate-950">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-6 py-6 sm:flex-row sm:justify-between">
          <p className="text-xs text-slate-500">© {new Date().getFullYear()} The Special Wedding. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <a href="mailto:hello@thespecialwedding.io" className="text-xs text-slate-500 transition hover:text-slate-300">Contact</a>
            <p className="text-xs text-slate-500">
              Built by{' '}
              <a href="https://joatlabs.dev" target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
                JOATLABS LLC
              </a>
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
