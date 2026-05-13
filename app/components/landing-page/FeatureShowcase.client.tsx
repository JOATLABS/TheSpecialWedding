"use client";

import Image from "next/image";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { MARKETING_FEATURES } from "@/data/marketingFeatures";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

export function FeatureShowcase() {
  const features = MARKETING_FEATURES;
  const [activeIdx, setActiveIdx] = useState(0);
  const [isDescriptionOpen, setIsDescriptionOpen] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLDivElement | null>(null);
  const activeFeature = features[activeIdx];
  const nextFeature = features[(activeIdx + 1) % features.length];

  const selectFeature = useCallback((index: number) => {
    setActiveIdx(index);
    setIsDescriptionOpen(false);
  }, []);

  const selectPreviousFeature = useCallback(() => {
    setActiveIdx((index) => (index - 1 + features.length) % features.length);
    setIsDescriptionOpen(false);
  }, [features.length]);

  const selectNextFeature = useCallback(() => {
    setActiveIdx((index) => (index + 1) % features.length);
    setIsDescriptionOpen(false);
  }, [features.length]);

  useEffect(() => {
    if (!sectionRef.current) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      { rootMargin: "180px 0px", threshold: 0.15 },
    );

    observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isSmallScreen = window.matchMedia("(max-width: 639px)").matches;

    if (!isVisible || document.hidden || prefersReducedMotion || isSmallScreen) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setActiveIdx((index) => (index + 1) % features.length);
    }, 6500);

    return () => window.clearInterval(timer);
  }, [features.length, isVisible]);

  useEffect(() => {
    if (!nextFeature?.image) {
      return undefined;
    }

    const win = window as IdleWindow;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let idleId: number | null = null;

    // CONTRACT (preload):
    //   - ``nextFeature.image`` is a static path under ``/public`` ending
    //     in ``.webp`` (or any browser-renderable format).
    //   - The browser fetches this exact byte-for-byte URL — no Next.js
    //     image-optimizer transform.  When the slide rotates and the
    //     ``<picture>`` below requests this same URL, it comes from the
    //     HTTP cache instead of the network.
    //   - ``decoding=async`` and ``fetchPriority=low`` keep this from
    //     contending with above-the-fold work.
    //   - We deliberately do NOT preload the AVIF variant.  The browser
    //     selects the format from ``<picture>`` based on ``Accept``; the
    //     URL fetched here is the same as what the ``<img>`` fallback
    //     requests, which is the WebP — a safe, universal choice.
    //
    // Replaces the prior hand-built ``/_next/image?url=...&w=...&q=75``
    // URL, which was brittle to Next.js internals.
    const preloadNextImage = () => {
      const preload = new window.Image();
      preload.decoding = "async";
      // Some browsers expose ``fetchPriority`` on HTMLImageElement;
      // guarded write keeps strict TS checks happy without losing the
      // hint where supported.
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
  }, [nextFeature?.image]);

  return (
    <div ref={sectionRef} className="space-y-4 sm:space-y-6">
      <div className="grid overflow-hidden rounded-xl border border-white/10 bg-white/[0.04] shadow-2xl shadow-black/30 sm:rounded-2xl lg:grid-cols-[minmax(0,1fr)_390px]">
        <div className="border-b border-white/10 bg-[#071020] p-1.5 sm:p-3 lg:border-b-0 lg:border-r">
          <div className="hidden items-center gap-2 border-b border-white/10 px-3 py-2 sm:flex" aria-hidden="true">
            <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-yellow-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-green-400/70" />
          </div>
          <div className="relative aspect-[16/9] rounded-lg bg-[#071020] sm:rounded-b-xl sm:rounded-t-none">
            {/*
              Raw <picture> instead of <Image> here so browsers that
              support AVIF (Chrome 85+, Firefox 93+, Safari 16+) get the
              smallest pre-generated file directly from /public, with no
              Next.js image-optimizer transform on the request path.
              The thumbnail grid below stays on <Image> because each
              thumb is 96 px and the cumulative bandwidth is small.

              CONTRACT: every entry in MARKETING_FEATURES has both
              ``<name>.webp`` and ``<name>.avif`` siblings under
              /public.  The .avif source is derived by suffix swap.
            */}
            <picture>
              <source
                srcSet={activeFeature.image.replace(/\.webp$/, ".avif")}
                type="image/avif"
              />
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
          </div>
        </div>

        <aside className="flex flex-col justify-between p-4 sm:p-6">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-wedding-rose">
              {activeFeature.category}
            </p>
            <h3 className="mt-3 text-2xl font-semibold leading-tight text-white sm:text-3xl">{activeFeature.title}</h3>
            <p className="mt-3 text-sm font-semibold leading-6 text-slate-200 sm:mt-4">{activeFeature.tagline}</p>
            <p className={`mt-3 text-sm leading-6 text-slate-300 sm:mt-4 sm:leading-7 ${isDescriptionOpen ? "" : "line-clamp-2 sm:line-clamp-none"}`}>
              {activeFeature.description}
            </p>
            <button
              type="button"
              onClick={() => setIsDescriptionOpen((current) => !current)}
              className="mt-3 text-sm font-semibold text-wedding-rose transition hover:text-wedding-blush sm:hidden"
            >
              {isDescriptionOpen ? "Show less" : "Read more"}
            </button>
            {activeFeature.blogSlug ? (
              <Link
                href={`/resources/blog/${activeFeature.blogSlug}`}
                className="mt-5 inline-flex text-sm font-semibold text-wedding-rose transition hover:text-wedding-blush"
              >
                Read the story
              </Link>
            ) : null}
          </div>

          <div className="mt-4 space-y-3 border-t border-white/10 pt-4 sm:mt-6 sm:flex sm:items-center sm:justify-between sm:space-y-0 sm:pt-5">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                {String(activeIdx + 1).padStart(2, "0")} / {String(features.length).padStart(2, "0")}
              </p>
            </div>

            <div className="grid grid-cols-[42px_minmax(0,1fr)_42px] gap-2 sm:hidden">
              <button
                type="button"
                onClick={selectPreviousFeature}
                aria-label="Previous feature"
                className="flex h-11 items-center justify-center rounded-lg border border-white/10 bg-white/[0.05] text-slate-200 transition hover:border-wedding-rose/50 hover:text-white"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </button>
              <label className="sr-only" htmlFor="mobile-feature-select">
                Choose product surface
              </label>
              <select
                id="mobile-feature-select"
                value={activeIdx}
                onChange={(event) => selectFeature(Number(event.target.value))}
                className="h-11 min-w-0 rounded-lg border border-white/10 bg-slate-950 px-3 text-sm font-semibold text-white outline-none transition focus:border-wedding-rose/70"
              >
                {features.map((feature, index) => (
                  <option key={feature.id} value={index}>
                    {String(index + 1).padStart(2, "0")} - {feature.title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={selectNextFeature}
                aria-label="Next feature"
                className="flex h-11 items-center justify-center rounded-lg border border-white/10 bg-white/[0.05] text-slate-200 transition hover:border-wedding-rose/50 hover:text-white"
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <Link href="#pricing" className="hidden text-sm font-semibold text-wedding-rose transition hover:text-wedding-blush sm:inline-flex">
              {/* SYNC-WITH-SEED: trial_days */}
              Start 30-day trial
            </Link>
          </div>
        </aside>
      </div>

      <div className="hidden gap-3 sm:grid sm:grid-cols-2 lg:grid-cols-4">
        {features.map((feature, index) => {
          const isActive = index === activeIdx;

          return (
            <button
              key={feature.id}
              type="button"
              onClick={() => selectFeature(index)}
              className={`grid grid-cols-[84px_1fr] gap-3 rounded-xl border p-2 text-left transition sm:grid-cols-[96px_1fr] ${
                isActive
                  ? "border-wedding-rose/70 bg-wedding-rose/10 shadow-lg shadow-wedding-rose/10"
                  : "border-white/10 bg-white/[0.035] hover:border-white/25 hover:bg-white/[0.06]"
              }`}
            >
              <span className="relative block aspect-[16/10] overflow-hidden rounded-lg bg-[#071020]">
                <Image
                  src={feature.image}
                  alt=""
                  fill
                  sizes="96px"
                  className="object-cover object-top"
                  loading="lazy"
                />
              </span>
              <span className="min-w-0 self-center">
                <span className="block text-[9px] font-semibold uppercase tracking-[0.18em] text-wedding-rose">
                  {feature.category}
                </span>
                <span className="mt-1 block truncate text-sm font-semibold text-white">{feature.title}</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
