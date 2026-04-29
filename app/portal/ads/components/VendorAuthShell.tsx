'use client';

import type { ReactNode } from 'react';
import { Sparkles } from 'lucide-react';

import { vendorSurfaceClass } from './styles';
import { BrandLockup } from '@/components/brand/BrandLockup';

export interface VendorAuthShowcaseHighlight {
  label: string;
  description: string;
}

export interface VendorAuthShowcaseStat {
  value: string;
  caption: string;
}

export function VendorAuthShowcase({
  eyebrow,
  title,
  description,
  highlights,
  stats,
}: {
  eyebrow: string;
  title: string;
  description: string;
  highlights: VendorAuthShowcaseHighlight[];
  stats: VendorAuthShowcaseStat[];
}) {
  return (
    <div className="relative w-full max-w-xl overflow-hidden rounded-[2.5rem] border border-white/45 bg-gradient-to-br from-white/65 via-white/30 to-white/10 p-6 shadow-[0_40px_120px_-40px_rgba(29,53,87,0.35)] backdrop-blur-2xl sm:p-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.65),transparent_55%),radial-gradient(circle_at_bottom_left,rgba(200,132,126,0.35),transparent_60%)]"
      />
      <div className="relative z-10 flex flex-col gap-6 text-wedding-navy">
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="rounded-full border border-white/55 bg-white/65 px-3 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.28em] text-wedding-rose shadow-sm">
              {eyebrow}
            </div>
            <div className="rounded-full border border-wedding-sage/20 bg-wedding-sage/10 p-2 text-wedding-sage">
              <Sparkles className="h-4 w-4" />
            </div>
          </div>
          <div className="space-y-3">
            <BrandLockup variant="full" surface="light" size="md" />
            <h1 className="text-[1.95rem] font-semibold leading-tight sm:text-[2.25rem]">{title}</h1>
            <p className="max-w-lg text-[0.95rem] leading-relaxed text-wedding-navy/75 sm:text-base">
              {description}
            </p>
          </div>
        </header>

        <dl className="grid gap-3">
          {highlights.map((highlight) => (
            <div
              key={highlight.label}
              className="relative overflow-hidden rounded-[1.8rem] border border-white/50 bg-white/60 p-4 shadow-lg backdrop-blur"
            >
              <div className="pointer-events-none absolute -right-6 -top-6 h-16 w-16 rounded-full bg-wedding-rose/20 blur-xl" aria-hidden="true" />
              <div className="pointer-events-none absolute -bottom-10 left-3 h-20 w-20 rounded-full bg-wedding-sage/20 blur-2xl" aria-hidden="true" />
              <div className="relative z-10 space-y-1.5">
                <dt className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-wedding-navy/60">{highlight.label}</dt>
                <dd className="text-[0.88rem] leading-relaxed text-wedding-navy/75">{highlight.description}</dd>
              </div>
            </div>
          ))}
        </dl>

        <div className="grid grid-cols-2 gap-3">
          {stats.map((stat) => (
            <div
              key={stat.caption}
              className="rounded-[1.6rem] border border-white/45 bg-white/55 px-4 py-3 text-center shadow-inner backdrop-blur"
            >
              <div className="text-lg font-semibold text-wedding-navy">{stat.value}</div>
              <p className="mt-1 text-[0.72rem] text-wedding-navy/65">{stat.caption}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function VendorAuthShell({
  showcase,
  children,
}: {
  showcase: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f9f1f6] to-[#eef6ff] dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-[-6rem] left-[-6rem] h-[22rem] w-[22rem] rounded-full bg-wedding-navy/10 blur-3xl"
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1600px] items-center px-4 py-12 sm:px-6 lg:px-12">
        <div className="relative isolate w-full overflow-hidden rounded-[3rem] border border-white/40 bg-white/25 p-6 shadow-2xl backdrop-blur-2xl sm:p-8">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0">
            <div className="absolute -left-16 top-12 h-32 w-32 rounded-full bg-white/50 blur-3xl" />
            <div className="absolute -right-20 bottom-10 h-28 w-40 rounded-full bg-wedding-rose/20 blur-3xl" />
            <div className="absolute inset-y-12 left-1/2 hidden w-px -translate-x-1/2 bg-gradient-to-b from-white/5 via-white/50 to-white/5 opacity-70 blur-sm md:block" />
          </div>
          <div className="relative grid items-stretch gap-10 md:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-12">
            <section className="order-2 flex justify-center md:order-1 md:pr-6 lg:pr-10">
              <div className="w-full">{showcase}</div>
            </section>

            <section className="order-1 md:order-2 md:pl-6 lg:pl-10">
              <div className={`${vendorSurfaceClass} h-full px-6 py-7 shadow-[0_32px_80px_-48px_rgba(29,53,87,0.4)] sm:px-8 xl:px-10`}>
                {children}
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
