'use client'

import { Analytics } from "@vercel/analytics/next"
import { useEffect } from 'react'

export default function ClientAnalytics() {
  useEffect(() => {
    // Register service worker on client side only
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/service-worker.js').then(
        function(registration) {
          console.log('ServiceWorker registration successful');
        },
        function(err) {
          console.log('ServiceWorker registration failed: ', err);
        }
      );
    }
  }, []);

  return <Analytics />;
}