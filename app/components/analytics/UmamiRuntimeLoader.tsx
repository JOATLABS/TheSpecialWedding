'use client';

import { useEffect } from 'react';

type AnalyticsConfigResponse = {
  websiteId?: string;
  src?: string;
};

function hasUmamiTracker(): boolean {
  if (typeof window === 'undefined') return true;
  if (window.umami?.track) return true;
  return Boolean(document.querySelector('script[data-website-id][src*="script.js"]'));
}

function isSafeTrackerConfig(config: AnalyticsConfigResponse): config is Required<AnalyticsConfigResponse> {
  if (!config.websiteId || !config.src) return false;
  try {
    const url = new URL(config.src);
    return url.protocol === 'https:';
  } catch {
    return false;
  }
}

export function UmamiRuntimeLoader() {
  useEffect(() => {
    if (hasUmamiTracker()) return;

    let cancelled = false;

    fetch('/api/public/analytics-config', {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((config: AnalyticsConfigResponse | null) => {
        if (cancelled || !config || !isSafeTrackerConfig(config) || hasUmamiTracker()) {
          return;
        }

        const script = document.createElement('script');
        script.async = true;
        script.defer = true;
        script.src = config.src;
        script.dataset.websiteId = config.websiteId;
        document.body.appendChild(script);
      })
      .catch(() => {
        // Analytics must never break the marketing page.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
