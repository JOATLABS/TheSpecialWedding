// app/utils/umami.ts
//
// Thin client-side wrapper around the Umami tracker. Safe in SSR (no-op when
// `window` is undefined) and tolerant of the tracker not being loaded — the
// public site renders the Umami `<Script>` in `app/layout.tsx`, gated on the
// `NEXT_PUBLIC_UMAMI_WEBSITE_ID` and `NEXT_PUBLIC_UMAMI_SRC` build vars. When
// either var is unset (local dev, staging without analytics, etc.) the script
// never loads and `window.umami` is undefined; this helper silently no-ops so
// analytics gaps never break the app.
//
// Usage:
//   import { umamiTrack } from '@/utils/umami';
//   umamiTrack('pricing_cta_clicked', { plan_id: 'plan_signature' });
//
// Event names should be lower_snake_case verbs/nouns that describe a funnel
// milestone — `signup_modal_opened`, `signup_registered`, `pricing_viewed`,
// etc. Keep property keys short and consistent across callers.

declare global {
  interface Window {
    umami?: {
      track: (
        eventName: string,
        eventData?: Record<string, unknown>,
      ) => void;
    };
  }
}

export function umamiTrack(
  eventName: string,
  eventData?: Record<string, unknown>,
): void {
  if (typeof window === 'undefined') return;
  const tracker = window.umami;
  if (!tracker || typeof tracker.track !== 'function') return;
  try {
    tracker.track(eventName, eventData);
  } catch {
    // Swallow tracking errors — never let analytics break the app.
  }
}

export {};
