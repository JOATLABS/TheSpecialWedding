'use client';

import React from 'react';

import { BrandLockup } from '@/components/brand/BrandLockup';
import { SITE_ORIGIN } from '@/seo/crawlPolicy';
import { umamiTrack } from '@/utils/umami';

const PLATFORM_MARKETING_URL = `${SITE_ORIGIN}/?utm_source=wedding_microsite&utm_medium=referral&utm_campaign=platform_footer`;

interface PublicMicrositeFooterProps {
  isClone?: boolean;
  onPrivacy?: () => void;
  onTerms?: () => void;
}

function LegalLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="transition-colors hover:text-white">
      {children}
    </span>
  );
}

export function PublicMicrositeFooter({
  isClone = false,
  onPrivacy,
  onTerms,
}: PublicMicrositeFooterProps) {
  const year = new Date().getFullYear();
  const brand = (
    <BrandLockup
      variant="mark"
      surface="theme"
      size="sm"
      idPrefix={isClone ? 'microsite-footer-clone' : 'microsite-footer-primary'}
    />
  );

  return (
    <footer
      id={isClone ? undefined : 'footer'}
      data-microsite-footer={isClone ? 'clone' : 'primary'}
      className="mt-12 border-t border-white/10 bg-black/55 text-white backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-3 px-4 py-4 min-[360px]:flex-row sm:px-6 sm:py-5">
        {isClone ? (
          <span className="inline-flex min-w-0 items-center" aria-hidden="true">
            {brand}
          </span>
        ) : (
          <a
            href={PLATFORM_MARKETING_URL}
            target="_blank"
            rel="noopener noreferrer"
            referrerPolicy="no-referrer"
            aria-label="Visit The Special Wedding (opens in a new tab)"
            onClick={() => {
              umamiTrack('microsite_platform_brand_clicked', { location: 'footer' });
            }}
            className="inline-flex min-h-11 min-w-0 items-center rounded-md opacity-90 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--theme-secondary-light)] focus-visible:ring-offset-2 focus-visible:ring-offset-black"
          >
            {brand}
          </a>
        )}

        <div className="shrink-0 text-center min-[360px]:text-right">
          <div className="flex items-center justify-center gap-2 text-[10px] tracking-[0.12em] text-[var(--theme-secondary-light)] min-[360px]:justify-end">
            {isClone ? (
              <>
                <LegalLabel>Privacy</LegalLabel>
                <span aria-hidden="true">·</span>
                <LegalLabel>Terms</LegalLabel>
              </>
            ) : (
              <>
                {onPrivacy ? (
                  <button
                    type="button"
                    onClick={onPrivacy}
                    className="inline-flex min-h-11 items-center rounded-sm transition-colors hover:text-white hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--theme-secondary-light)]"
                  >
                    Privacy
                  </button>
                ) : (
                  <a
                    href="/privacy"
                    className="inline-flex min-h-11 items-center rounded-sm transition-colors hover:text-white hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--theme-secondary-light)]"
                  >
                    Privacy
                  </a>
                )}
                <span aria-hidden="true">·</span>
                {onTerms ? (
                  <button
                    type="button"
                    onClick={onTerms}
                    className="inline-flex min-h-11 items-center rounded-sm transition-colors hover:text-white hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--theme-secondary-light)]"
                  >
                    Terms
                  </button>
                ) : (
                  <a
                    href="/terms"
                    className="inline-flex min-h-11 items-center rounded-sm transition-colors hover:text-white hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--theme-secondary-light)]"
                  >
                    Terms
                  </a>
                )}
              </>
            )}
          </div>
          <p className="mt-1 text-[10px] tracking-[0.08em] text-white/45">
            &copy; {year}
          </p>
        </div>
      </div>
    </footer>
  );
}

export { PLATFORM_MARKETING_URL };
