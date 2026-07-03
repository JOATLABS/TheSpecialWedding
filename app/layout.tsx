// app/layout.tsx
import './styles/globals.css'
import Script from 'next/script'
import type { Metadata } from 'next'
import { MARKETING_FEATURES } from './data/marketingFeatures';
import { UmamiRuntimeLoader } from './components/analytics/UmamiRuntimeLoader';
import { resolveUmamiScriptConfig } from './utils/umamiScriptConfig';

const TOOL_COUNT = MARKETING_FEATURES.length;

export const metadata: Metadata = {
  // Title kept within 45-60 char band so it doesn't get truncated in
  // SERPs. Previous "Wedding Planner Software & CRM for Pros — The
  // Special Wedding" was 61 chars and got cut. New value tested via
  // BLG Technical Audit (https://www.babylovegrowth.ai/en/dashboard/geo-audit).
  title: {
    default: 'All-In-One Wedding Planner Software & CRM for Pros',
    template: '%s | The Special Wedding',
  },
  // Meta description tightened to fit the 140-160 char band SERPs
  // display in full. Previous 235-char value was truncated mid-thought.
  description: 'All-in-one wedding planning OS & CRM for planners. Manage guests, RSVPs, seating, budgets, contracts, timelines, and a live couple portal. Free trial.',
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
    title: 'The Special Wedding — Wedding Planning Software for Professional Planners',
    description: 'Guest management, budgets, contracts, vendor CRM, seating, payments, and day-of execution — one platform built for professional wedding planners.',
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
    title: 'The Special Wedding — Software for Professional Wedding Planners',
    description: 'Guest management, RSVPs, seating, vendor CRM, and day-of execution in one platform built for professional planners. Start your free trial.',
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

  return (
    <html lang="en">
      <head>
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
                  description: `All-in-one wedding planning software with ${TOOL_COUNT} tools for professional planners — couple portal, guest management, AI contracts, SMS reminders, vendor CRM, seating, budgets, photo gallery, and day-of execution.`,
                },
                {
                  '@type': 'SoftwareApplication',
                  name: 'The Special Wedding',
                  applicationCategory: 'BusinessApplication',
                  operatingSystem: 'Web',
                  url: 'https://thespecialwedding.io',
                  description: `All-in-one wedding planning software with ${TOOL_COUNT} AI-powered tools for professional planners — couple portal, guest management, contracts, SMS reminders, vendor CRM, seating, budgets, photo gallery, forms, and more.`,
                  offers: {
                    '@type': 'AggregateOffer',
                    lowPrice: '29',
                    highPrice: '59',
                    priceCurrency: 'USD',
                    offerCount: 2,
                  },
                },
              ],
            }),
          }}
        />
      </head>
      <body suppressHydrationWarning>
        {children}

        {/* Umami Analytics — self-hosted on Coolify, privacy-first, no cookies. */}
        {umamiConfig && (
          <Script
            async
            src={umamiConfig.src}
            data-website-id={umamiConfig.websiteId}
            strategy="afterInteractive"
          />
        )}
        <UmamiRuntimeLoader />
      </body>
    </html>
  )
}
