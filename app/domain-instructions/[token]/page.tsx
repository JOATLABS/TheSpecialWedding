import type { Metadata } from 'next';
import { Clock3, RefreshCw, ShieldX } from 'lucide-react';

import { loadDomainInstructions } from '../domainInstructionData';
import { DomainInstructionsView } from './DomainInstructionsView';

export const dynamic = 'force-dynamic';
export const revalidate = 0;
export const fetchCache = 'force-no-store';

export const metadata: Metadata = {
  title: 'DNS setup instructions',
  description: 'Secure, read-only DNS instructions for a planner storefront.',
  referrer: 'no-referrer',
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: {
      index: false,
      follow: false,
      noimageindex: true,
    },
  },
};

function UnavailableInstructions({ temporary }: { temporary: boolean }) {
  return (
    <main className="flex min-h-screen items-center justify-center overflow-x-hidden bg-[#f6f3f1] px-4 py-12 text-slate-950 dark:bg-slate-950 dark:text-slate-50">
      <section className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-xl dark:border-slate-700 dark:bg-slate-900 sm:p-10">
        <a
          href="/"
          className="mx-auto inline-flex rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wedding-navy focus-visible:ring-offset-2 dark:focus-visible:ring-wedding-rose"
          aria-label="The Special Wedding homepage"
        >
          {/* Bundled first-party asset. */}
          <img src="/logo-light.svg" alt="The Special Wedding" className="h-14 w-auto" />
        </a>

        <div className="mx-auto mt-8 flex h-14 w-14 items-center justify-center rounded-full bg-wedding-blush text-[#8d555d] dark:bg-[#3a2024] dark:text-wedding-rose">
          {temporary ? (
            <Clock3 className="h-7 w-7" aria-hidden="true" />
          ) : (
            <ShieldX className="h-7 w-7" aria-hidden="true" />
          )}
        </div>

        <h1 className="mt-5 text-3xl font-semibold tracking-tight text-wedding-navy dark:text-white">
          {temporary
            ? 'We could not load these instructions'
            : 'This instruction link is no longer available'}
        </h1>
        <p className="mx-auto mt-4 max-w-md text-base leading-7 text-slate-700 dark:text-slate-300">
          {temporary
            ? 'The secure instructions service is temporarily unavailable. No DNS changes were made.'
            : 'The link may have expired or been revoked. Ask the planner to send a new secure DNS instruction link.'}
        </p>

        <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:justify-center">
          {temporary ? (
            <a
              href="?retry=1"
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-wedding-navy px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#142a47] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wedding-navy focus-visible:ring-offset-2 dark:bg-wedding-rose dark:text-slate-950"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Try again
            </a>
          ) : null}
          <a
            href="/support"
            className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-800 transition hover:border-wedding-rose hover:bg-wedding-blush/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wedding-navy focus-visible:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-white"
          >
            Visit support
          </a>
        </div>

        <p className="mt-7 border-t border-slate-200 pt-5 text-sm leading-6 text-slate-500 dark:border-slate-700 dark:text-slate-400">
          This page is read-only. It cannot publish, activate, transfer, or disconnect a storefront.
        </p>
      </section>
    </main>
  );
}

export default async function DomainInstructionsPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const result = await loadDomainInstructions(token);

  if (result.status === 'ready') {
    return <DomainInstructionsView instruction={result.instruction} />;
  }

  return <UnavailableInstructions temporary={result.status === 'temporarily_unavailable'} />;
}
