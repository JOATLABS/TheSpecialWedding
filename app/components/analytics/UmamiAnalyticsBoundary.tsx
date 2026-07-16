'use client';

import Script from 'next/script';
import { usePathname } from 'next/navigation';

import {
  isAnalyticsSensitivePath,
  UMAMI_BEFORE_SEND_HANDLER_NAME,
} from '@/utils/analyticsPrivacy';
import type { UmamiScriptConfig } from '@/utils/umamiScriptConfig';

import { UmamiRuntimeLoader } from './UmamiRuntimeLoader';

type UmamiAnalyticsBoundaryProps = {
  config: UmamiScriptConfig | null;
};

type UmamiAnalyticsForPathProps = UmamiAnalyticsBoundaryProps & {
  pathname: string | null;
};

export function UmamiAnalyticsForPath({
  config,
  pathname,
}: UmamiAnalyticsForPathProps) {
  // Fail closed until Next has resolved the current App Router pathname.
  if (pathname === null || isAnalyticsSensitivePath(pathname)) {
    return null;
  }

  return (
    <>
      {config ? (
        <Script
          async
          src={config.src}
          data-website-id={config.websiteId}
          data-before-send={UMAMI_BEFORE_SEND_HANDLER_NAME}
          referrerPolicy="no-referrer"
          strategy="afterInteractive"
        />
      ) : null}
      <UmamiRuntimeLoader />
    </>
  );
}

export function UmamiAnalyticsBoundary({ config }: UmamiAnalyticsBoundaryProps) {
  const pathname = usePathname();

  return <UmamiAnalyticsForPath config={config} pathname={pathname} />;
}
