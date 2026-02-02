// app/layout.tsx
import './styles/globals.css'
import Script from 'next/script'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Special Wedding',
  description: 'Professional Wedding Planning Platform',
  icons: {
    icon: '/favicon.svg',
    apple: '/logo_all.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const cloudflareToken = process.env.NEXT_PUBLIC_CLOUDFLARE_ANALYTICS_TOKEN;

  return (
    <html lang="en">
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