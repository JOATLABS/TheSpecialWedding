import type { Metadata } from 'next';

import SaasNav from '@/components/saas/SaasNav';
import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import { serializeJsonLd } from '@/seo/jsonLd';

import TemplatesClient from './TemplatesClient';
import { MARKETING_TEMPLATES } from './manifest';

const SITE_URL = 'https://thespecialwedding.io';
const TEMPLATES_PATH = '/resources/templates';
const TEMPLATES_URL = `${SITE_URL}${TEMPLATES_PATH}`;

export const metadata: Metadata = {
  title: 'Free Wedding Planner Templates | Download 9 Planner PDFs',
  description:
    'Download free wedding planner templates for client intake, wedding timelines, vendor onboarding, guest needs, shot lists, and day-of contacts.',
  alternates: {
    canonical: TEMPLATES_PATH,
  },
  openGraph: {
    title: 'Free Wedding Planner Templates',
    description:
      'Nine production-ready wedding planning templates for intake, timelines, vendors, guests, shot lists, and day-of contacts.',
    url: TEMPLATES_URL,
    siteName: 'The Special Wedding',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Free Wedding Planner Templates',
    description:
      'Download 9 free wedding planner templates built for real client and vendor workflows.',
  },
  robots: {
    index: true,
    follow: true,
  },
};

const templatesJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'CollectionPage',
      '@id': TEMPLATES_URL,
      url: TEMPLATES_URL,
      name: 'Free Wedding Planner Templates',
      description:
        'A collection of free wedding planner templates for intake, timelines, vendor onboarding, guest needs, shot lists, and day-of contacts.',
      mainEntity: {
        '@id': `${TEMPLATES_URL}#template-list`,
      },
    },
    {
      '@type': 'ItemList',
      '@id': `${TEMPLATES_URL}#template-list`,
      name: 'Free Wedding Planner Templates',
      numberOfItems: MARKETING_TEMPLATES.length,
      itemListElement: MARKETING_TEMPLATES.map((template, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        item: {
          '@id': `${TEMPLATES_URL}#${template.id}`,
        },
      })),
    },
    ...MARKETING_TEMPLATES.map((template) => ({
      '@type': 'CreativeWork',
      '@id': `${TEMPLATES_URL}#${template.id}`,
      url: `${TEMPLATES_URL}#${template.id}`,
      name: template.name,
      description: template.description,
      genre: template.category,
      isAccessibleForFree: true,
      publisher: {
        '@type': 'Organization',
        name: 'The Special Wedding',
        url: SITE_URL,
      },
    })),
  ],
};

export default function PublicTemplatesPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Resources', href: '/resources' },
          { name: 'Templates', href: TEMPLATES_PATH },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(templatesJsonLd) }}
      />

      <section className="mx-auto max-w-6xl px-6 pb-16 pt-28 sm:px-10 sm:pb-20">
        <div className="mb-10 max-w-3xl">
          <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-wedding-rose">
            Free download
          </p>
          <h1 className="mt-3 text-4xl font-semibold leading-tight text-white sm:text-5xl">
            Free wedding planner templates
          </h1>
          <p className="mt-4 text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
            Nine production-ready PDFs for intake, timelines, vendor onboarding,
            guest needs, shot lists, and day-of contacts. Each template can be
            downloaded without creating an account.
          </p>
        </div>

        <TemplatesClient templates={MARKETING_TEMPLATES} surface="dark" />
      </section>
    </main>
  );
}
