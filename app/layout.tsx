// app/layout.tsx
import './styles/globals.css'
import type { Metadata } from 'next'
import React from 'react'
import ClientAnalytics from '@/components/ClientAnalytics'

export const metadata: Metadata = {
  title: 'TheSpecialWedding - Professional Wedding Planning Platform',
  description: 'Transform your wedding planning business with TheSpecialWedding - a comprehensive platform for wedding planners',
  manifest: '/manifest.json',
  formatDetection: {
    telephone: false,
  },
}

// 'device-width' ensures the viewport matches the device's screen width for responsive design
export const viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  themeColor: '#D4A5A5',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Additional mobile-friendly meta tags */}
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="TheSpecialWedding" />
        <meta name="application-name" content="TheSpecialWedding" />
        <meta name="msapplication-TileColor" content="#D4A5A5" />

        {/* Preconnect to Google Fonts for faster loading */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body suppressHydrationWarning>
        <div id="main-content">
          {children}
          {/* <ClientAnalytics /> */}
        </div>
      </body>
    </html>
  )
}