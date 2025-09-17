// app/layout.tsx
import './styles/globals.css'
import { Analytics } from "@vercel/analytics/next"
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'TheSpecialWedding - Professional Wedding Planning Platform',
  description: 'Transform your wedding planning business with TheSpecialWedding - a comprehensive platform for wedding planners',
  viewport: 'width=device-width, initial-scale=1, maximum-scale=5',
  themeColor: '#D4A5A5',
  manifest: '/manifest.json',
  appleWebAppCapable: 'yes',
  appleWebAppStatusBarStyle: 'default',
  formatDetection: {
    telephone: false,
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        {/* Additional mobile-friendly meta tags */}
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-title" content="TheSpecialWedding" />
        <meta name="application-name" content="TheSpecialWedding" />
        <meta name="msapplication-TileColor" content="#D4A5A5" />

        {/* Preconnect to Google Fonts for faster loading */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        {children}
        <Analytics />

        {/* Service Worker Registration */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.register('/service-worker.js').then(
                    function(registration) {
                      console.log('ServiceWorker registration successful');
                    },
                    function(err) {
                      console.log('ServiceWorker registration failed: ', err);
                    }
                  );
                });
              }
            `,
          }}
        />
      </body>
    </html>
  )
}