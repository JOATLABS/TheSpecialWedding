"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { PublicDemoVideo } from "@/data/publicDemoVideos";
import { MARKETING_FEATURES } from "@/data/marketingFeatures";
import DemoVideoLauncher from "@/components/saas/DemoVideoLauncher";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

type FeatureShowcaseProps = {
  demoVideosByFeatureId: Record<string, PublicDemoVideo>;
};

export function FeatureShowcase({ demoVideosByFeatureId }: FeatureShowcaseProps) {
  const features = MARKETING_FEATURES;
  const [activeIdx, setActiveIdx] = useState(0);
  const [shouldLoadMedia, setShouldLoadMedia] = useState(false);
  const sectionRef = useRef<HTMLDivElement | null>(null);
  const activeFeature = features[activeIdx];
  const nextFeature = features[(activeIdx + 1) % features.length];
  const activeDemo = demoVideosByFeatureId[activeFeature.id];

  const selectFeature = useCallback(
    (index: number) => {
      setActiveIdx((index + features.length) % features.length);
      setShouldLoadMedia(true);
    },
    [features.length],
  );

  const selectPreviousFeature = useCallback(() => {
    selectFeature(activeIdx - 1);
  }, [activeIdx, selectFeature]);

  const selectNextFeature = useCallback(() => {
    selectFeature(activeIdx + 1);
  }, [activeIdx, selectFeature]);

  useEffect(() => {
    if (!sectionRef.current) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldLoadMedia(true);
        }
      },
      { rootMargin: "180px 0px", threshold: 0.15 },
    );

    observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!shouldLoadMedia || !nextFeature?.image) {
      return undefined;
    }

    const win = window as IdleWindow;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let idleId: number | null = null;

    const preloadNextImage = () => {
      const preload = new window.Image();
      preload.decoding = "async";
      (preload as unknown as { fetchPriority?: string }).fetchPriority = "low";
      preload.src = nextFeature.image;
    };

    if (win.requestIdleCallback) {
      idleId = win.requestIdleCallback(preloadNextImage, { timeout: 3000 });
    } else {
      timeoutId = setTimeout(preloadNextImage, 1400);
    }

    return () => {
      if (idleId !== null && win.cancelIdleCallback) {
        win.cancelIdleCallback(idleId);
      }
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [shouldLoadMedia, nextFeature?.image]);

  return (
    <div
      ref={sectionRef}
      className="space-y-4 sm:space-y-5"
      role="region"
      aria-roledescription="carousel"
      aria-label="Product walkthrough carousel"
    >
      <div className="relative overflow-hidden rounded-xl border border-white/10 bg-white/[0.04] shadow-2xl shadow-black/30 sm:rounded-2xl">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="border-b border-white/10 bg-[#071020] p-1.5 sm:p-3 lg:border-b-0 lg:border-r lg:border-white/10">
            <div className="hidden items-center gap-2 border-b border-white/10 px-3 py-2 sm:flex" aria-hidden="true">
              <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-yellow-400/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-green-400/70" />
            </div>
            <div className="relative aspect-[16/9] rounded-lg bg-[#071020] sm:rounded-b-xl sm:rounded-t-none">
              {shouldLoadMedia ? (
                <picture>
                  <source srcSet={activeFeature.image.replace(/\.webp$/, ".avif")} type="image/avif" />
                  <source srcSet={activeFeature.image} type="image/webp" />
                  <img
                    key={activeFeature.id}
                    src={activeFeature.image}
                    alt={`${activeFeature.title}: ${activeFeature.tagline}`}
                    loading="lazy"
                    decoding="async"
                    className="absolute inset-0 h-full w-full object-contain object-top"
                  />
                </picture>
              ) : (
                <span
                  className="absolute inset-0 bg-[radial-gradient(circle_at_28%_18%,rgba(212,165,165,0.16),transparent_44%),linear-gradient(135deg,rgba(15,23,42,0.86),rgba(7,16,32,1))]"
                  aria-hidden="true"
                />
              )}
            </div>
          </div>

          <aside className="flex min-h-[260px] flex-col justify-center p-5 sm:p-7">
            <h3 className="text-3xl font-semibold leading-tight text-white sm:text-4xl">{activeFeature.title}</h3>
            <p className="mt-4 text-base font-semibold leading-7 text-slate-200">{activeFeature.tagline}</p>
            {activeDemo?.assetUrl ? (
              <div className="mt-6">
                <DemoVideoLauncher demo={activeDemo} />
              </div>
            ) : null}
          </aside>
        </div>

        <button
          type="button"
          onClick={selectPreviousFeature}
          className="absolute left-3 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-white/15 bg-slate-950/80 text-white shadow-lg shadow-black/30 backdrop-blur transition hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose sm:left-5"
          aria-label="Previous feature"
        >
          <ChevronLeft className="h-5 w-5" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={selectNextFeature}
          className="absolute right-3 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-white/15 bg-slate-950/80 text-white shadow-lg shadow-black/30 backdrop-blur transition hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose sm:right-5"
          aria-label="Next feature"
        >
          <ChevronRight className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2" aria-label="Choose a feature">
        {features.map((feature, index) => {
          const isActive = index === activeIdx;

          return (
            <button
              key={feature.id}
              type="button"
              onClick={() => selectFeature(index)}
              className={`h-2.5 rounded-full transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose ${
                isActive ? "w-8 bg-wedding-rose" : "w-2.5 bg-white/25 hover:bg-white/45"
              }`}
              aria-label={`Show ${feature.title}`}
              aria-current={isActive ? "true" : undefined}
            />
          );
        })}
      </div>
    </div>
  );
}
