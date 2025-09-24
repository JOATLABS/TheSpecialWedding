'use client'

import { Analytics } from '@vercel/analytics/react'
import { useEffect } from 'react'

export default function ClientAnalytics() {
  useEffect(() => {
    // Register service worker on client side only
    if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/service-worker.js').catch(() => {});
    }
  }, []);

  return <Analytics />;
}