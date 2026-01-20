// app/layout.tsx
import './styles/globals.css'
import { SafeAnalytics } from './components/SafeAnalytics'
import Script from 'next/script'

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

        {/* Vercel Analytics - User experience metrics (wrapped in error boundary) */}
        <SafeAnalytics />

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