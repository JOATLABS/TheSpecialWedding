// app/layout.tsx
import './styles/globals.css'
import Script from 'next/script'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: {
    default: 'The Special Wedding — Wedding Planner Software for Professionals | Guests, Vendors & More',
    template: '%s | The Special Wedding',
  },
  description: 'Wedding planning software built for professional planners. Manage guests, RSVPs, seating, vendor contracts, budgets, and day-of timelines — all from one dashboard. Start at $29/mo.',
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
  const cloudflareToken = process.env.NEXT_PUBLIC_CLOUDFLARE_ANALYTICS_TOKEN;

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
                  description: 'All-in-one wedding planning software with 18 tools for professional planners — couple portal, guest management, AI contracts, SMS reminders, vendor CRM, seating, budgets, photo gallery, and day-of execution.',
                },
                {
                  '@type': 'SoftwareApplication',
                  name: 'The Special Wedding',
                  applicationCategory: 'BusinessApplication',
                  operatingSystem: 'Web',
                  url: 'https://thespecialwedding.io',
                  description: 'All-in-one wedding planning software with 18 AI-powered tools for professional planners — couple portal, guest management, contracts, SMS reminders, vendor CRM, seating, budgets, photo gallery, forms, and more.',
                  offers: {
                    '@type': 'AggregateOffer',
                    lowPrice: '29',
                    highPrice: '59',
                    priceCurrency: 'USD',
                    offerCount: 2,
                  },
                },
                {
                  '@type': 'FAQPage',
                  mainEntity: [
                    {
                      '@type': 'Question',
                      name: 'Can I manage multiple weddings at once?',
                      acceptedAnswer: {
                        '@type': 'Answer',
                        text: 'Yes. Each wedding gets its own workspace with separate guest lists, budgets, seating, vendors, and branding — all managed from a single dashboard with portfolio-level analytics.',
                      },
                    },
                    {
                      '@type': 'Question',
                      name: 'What do my couples see?',
                      acceptedAnswer: {
                        '@type': 'Answer',
                        text: 'Every couple gets their own Couple Portal with a personalized dashboard, timeline, payment history, form submissions, an inbox to message you directly, photo memories, gift registry, and FAQs — no app download needed.',
                      },
                    },
                    {
                      '@type': 'Question',
                      name: 'How does the AI help me run my business?',
                      acceptedAnswer: {
                        '@type': 'Answer',
                        text: 'AI is woven into contracts (clause generation), service packages (pricing suggestions), reminders (tone-aware message drafting), budgets (spend forecasting), payments (cash flow predictions), and seating (conflict resolution) — saving hours of manual work every week.',
                      },
                    },
                    {
                      '@type': 'Question',
                      name: 'Can I send RSVPs and reminders via SMS?',
                      acceptedAnswer: {
                        '@type': 'Answer',
                        text: 'Yes. Send RSVP invitations and follow-up reminders via SMS (Twilio or Telnyx) or email (Resend), with automatic fallback if SMS fails, delivery tracking, and AI-drafted messages in formal, friendly, or casual tones.',
                      },
                    },
                    {
                      '@type': 'Question',
                      name: 'Can vendors collaborate in the platform?',
                      acceptedAnswer: {
                        '@type': 'Answer',
                        text: 'Yes. Invite photographers, caterers, and venues into dedicated workspaces with role-based access to timelines, contracts, deliverables, and file exchanges — plus a vendor advertising portal for agencies.',
                      },
                    },
                    {
                      '@type': 'Question',
                      name: 'Is there support on the wedding day?',
                      acceptedAnswer: {
                        '@type': 'Answer',
                        text: 'Signature and Agency plans include live chat with our success team plus on-call escalation for critical day-of moments.',
                      },
                    },
                  ],
                },
              ],
            }),
          }}
        />
      </head>
      <body suppressHydrationWarning>
        {children}

        {/* Cloudflare Web Analytics - Traffic & performance (FREE, privacy-first, no cookies!) */}
        {cloudflareToken && (
          <Script
            defer
            src='https://static.cloudflareinsights.com/beacon.min.js'
            data-cf-beacon={JSON.stringify({ token: cloudflareToken })}
            strategy="afterInteractive"
          />
        )}
      </body>
    </html>
  )
}
