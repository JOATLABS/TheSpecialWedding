import type { Metadata } from 'next';

import LegacyTemplatesRedirectClient from './LegacyTemplatesRedirectClient';

export const metadata: Metadata = {
  title: 'Free Wedding Planner Templates — The Special Wedding',
  description:
    'Free wedding planner templates now live as a tab inside the Resources hub.',
  alternates: {
    canonical: '/resources?tab=templates',
  },
  robots: {
    index: false,
    follow: true,
  },
};

export default function LegacyPublicTemplatesPage() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-24 text-center text-white">
      <LegacyTemplatesRedirectClient />
      <p className="text-sm text-slate-300">
        Free templates now live inside Resources.{' '}
        <a className="text-wedding-rose underline" href="/resources?tab=templates">
          Open the Templates tab
        </a>
        .
      </p>
    </main>
  );
}
