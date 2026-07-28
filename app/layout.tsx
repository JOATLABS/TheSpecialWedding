// app/layout.tsx
import './styles/globals.css'
import type { Metadata } from 'next'
import { UmamiAnalyticsBoundary } from './components/analytics/UmamiAnalyticsBoundary';
import { UMAMI_PRIVACY_GUARD_SCRIPT } from './utils/analyticsPrivacy';
import { resolveUmamiScriptConfig } from './utils/umamiScriptConfig';

export const metadata: Metadata = {
  // Title kept within 45-60 char band so it doesn't get truncated in
  // SERPs. Previous "Wedding Planner Software & CRM for Pros — The
  // Special Wedding" was 61 chars and got cut. New value tested via
  // BLG Technical Audit (https://www.babylovegrowth.ai/en/dashboard/geo-audit).
  title: {
    default: 'The Connected Operating System for Wedding Planners',
    template: '%s | The Special Wedding',
  },
  // Meta description tightened to fit the 140-160 char band SERPs
  // display in full. Previous 235-char value was truncated mid-thought.
  description: 'One planner-owned workspace connecting weddings, couples, guests, vendors, contracts, budgets, timelines, seating, and the public wedding experience.',
  keywords: ['wedding planner software', 'wedding planning business software', 'event planner CRM', 'wedding vendor management', 'guest management for planners', 'wedding seating chart tool', 'HoneyBook alternative', 'Aisle Planner alternative'],
  authors: [{ name: 'The Special Wedding' }],
  creator: 'The Special Wedding',
  verification: {
    google: process.env.GOOGLE_SITE_VERIFICATION,
    other: process.env.BING_SITE_VERIFICATION
      ? {
          'msvalidate.01': process.env.BING_SITE_VERIFICATION,
        }
      : undefined,
  },
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/',
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://thespecialwedding.io',
    siteName: 'The Special Wedding',
    title: 'The Special Wedding — The Connected Operating System for Wedding Planners',
    description: 'Replace disconnected spreadsheets, messages, documents, and timelines with one planner-owned wedding workspace.',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding — Wedding Planning Software Dashboard',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@thespecialwedding',
    title: 'The Special Wedding — The Connected Operating System for Wedding Planners',
    description: 'One planner-owned workspace for weddings, couples, guests, vendors, contracts, budgets, timelines, seating, and the public experience.',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  icons: {
    icon: '/favicon.svg',
    apple: '/logo_all.png',
  },
  manifest: '/manifest.json',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Umami Analytics (self-hosted via Coolify).
  // Website UUID comes from the Umami dashboard after the site is registered.
  // Script URL points at the self-hosted instance (e.g. https://umami.thespecialwedding.io/script.js).
  const umamiConfig = resolveUmamiScriptConfig();
  const appBuildCommit = process.env.NEXT_PUBLIC_APP_BUILD_COMMIT ?? 'unverified-build';

  return (
    <html lang="en">
      <head>
        <meta name="tsw-app-build-commit" content={appBuildCommit} />
        <script
          id="tsw-umami-privacy-guard"
          dangerouslySetInnerHTML={{ __html: UMAMI_PRIVACY_GUARD_SCRIPT }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              '@context': 'https://schema.org',
              '@graph': [
                {
                  '@type': 'Organization',
                  name: 'The Special Wedding',
                  url: 'https://thespecialwedding.io',
                  logo: 'https://thespecialwedding.io/logo.svg',
                  description: 'The connected operating system built specifically for wedding planners, replacing disconnected tools with one planner-owned workspace.',
                },
                {
                  '@type': 'SoftwareApplication',
                  name: 'The Special Wedding',
                  applicationCategory: 'BusinessApplication',
                  operatingSystem: 'Web',
                  url: 'https://thespecialwedding.io',
                  description: 'A planner-owned wedding workspace connecting client setup, couple experience, guests, vendors, contracts, budgets, timelines, seating, and communications.',
                  offers: {
                    '@type': 'AggregateOffer',
                    lowPrice: '49',
                    highPrice: '199',
                    priceCurrency: 'USD',
                    offerCount: 3,
                    // Keep in sync with scripts/seed_subscription_plans.py and
                    // COUPLE_LIFETIME_OFFER in app/constants/billing.py.
                    offers: [
                      {
                        '@type': 'Offer',
                        name: 'Solo Founding',
                        description: 'Planner workspace subscription, billed monthly or yearly.',
                        price: '49',
                        priceCurrency: 'USD',
                      },
                      {
                        '@type': 'Offer',
                        name: 'Solo Standard',
                        description: 'Planner workspace subscription, billed monthly or yearly.',
                        price: '99',
                        priceCurrency: 'USD',
                      },
                      {
                        '@type': 'Offer',
                        name: 'Couple Lifetime Access',
                        description: 'One-time fee giving a couple one wedding workspace for the lifetime of the wedding. Not a subscription.',
                        price: '199',
                        priceCurrency: 'USD',
                      },
                    ],
                  },
                },
              ],
            }),
          }}
        />
      </head>
      <body suppressHydrationWarning>
        {children}

        {/* Umami is completely withheld from secret-bearing instruction routes. */}
        <UmamiAnalyticsBoundary config={umamiConfig} />
      </body>
    </html>
  )
}
