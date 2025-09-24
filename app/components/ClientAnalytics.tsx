'use client'

import { Analytics } from '@vercel/analytics/react'
import { useEffect, useState } from 'react'

export default function ClientAnalytics() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    // Register service worker on client side only
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/service-worker.js').catch(() => {});
    }
  }, [])

  if (!mounted) {
    return null
  }

  return <Analytics />
}