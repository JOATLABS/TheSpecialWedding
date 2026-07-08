import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

import MarketingFooter from './MarketingFooter';
import SaasNav from './SaasNav';

const relatedPolicies = [
  { href: '/privacy', label: 'Privacy' },
  { href: '/terms', label: 'Terms' },
  { href: '/google-calendar', label: 'Google Calendar' },
  { href: '/google-data-deletion', label: 'Data deletion' },
  { href: '/support', label: 'Support' },
];

type PolicyPageShellProps = {
  eyebrow: string;
  title: string;
  description: ReactNode;
  lastUpdated?: string;
  children: ReactNode;
};

export function PolicyPageShell({
  eyebrow,
  title,
  description,
  lastUpdated = 'July 8, 2026',
  children,
}: PolicyPageShellProps) {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <main className="pt-24">
        <section className="border-b border-white/10 bg-slate-950 px-6 pb-12 pt-10 sm:px-8 lg:px-12">
          <div className="mx-auto max-w-6xl">
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-1.5 text-sm font-medium text-slate-300 transition hover:border-white/30 hover:bg-white/10 hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to homepage
            </Link>

            <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-end">
              <header className="max-w-4xl">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-wedding-rose/80">
                  {eyebrow}
                </p>
                <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                  {title}
                </h1>
                <div className="mt-5 max-w-3xl text-base leading-8 text-slate-300 sm:text-lg">
                  {description}
                </div>
              </header>

              <aside className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Policy pages
                </p>
                <div className="mt-3 grid gap-2">
                  {relatedPolicies.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      className="rounded-md px-2 py-1.5 text-sm text-slate-300 transition hover:bg-white/10 hover:text-white"
                    >
                      {link.label}
                    </Link>
                  ))}
                </div>
                <p className="mt-4 border-t border-white/10 pt-3 text-xs text-slate-500">
                  Last updated: {lastUpdated}
                </p>
              </aside>
            </div>
          </div>
        </section>

        <section className="bg-white px-6 py-12 text-slate-900 sm:px-8 lg:px-12">
          <div className="mx-auto max-w-6xl space-y-10">{children}</div>
        </section>
      </main>
      <MarketingFooter />
    </div>
  );
}

export function PolicySection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid min-w-0 gap-5 border-t border-slate-200 pt-8 first:border-t-0 first:pt-0 md:grid-cols-[16rem_minmax(0,1fr)]">
      <h2 className="text-xl font-semibold tracking-tight text-slate-950">{title}</h2>
      <div className="min-w-0 space-y-4 text-sm leading-7 text-slate-700 sm:text-base">{children}</div>
    </section>
  );
}

export function PolicyCallout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-5 text-slate-800">
      <p className="font-semibold text-slate-950">{title}</p>
      <div className="mt-2 space-y-3 text-sm leading-7">{children}</div>
    </div>
  );
}
