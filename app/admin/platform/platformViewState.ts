import type { PlatformTabId } from './PlatformTabs';

export type PlatformPrimaryView =
  | 'storefront'
  | 'loading'
  | 'health_error'
  | 'empty'
  | 'metrics';

interface PlatformViewStateInput {
  activeTab: PlatformTabId;
  authLoading: boolean;
  healthLoading: boolean;
  isRootAdmin: boolean;
  hasMetrics: boolean;
  hasHealthError: boolean;
}

/** Keep the root-only storefront queue independent from unrelated health APIs. */
export function resolvePlatformPrimaryView({
  activeTab,
  authLoading,
  healthLoading,
  isRootAdmin,
  hasMetrics,
  hasHealthError,
}: PlatformViewStateInput): PlatformPrimaryView {
  if (activeTab === 'storefront' && !authLoading && isRootAdmin) return 'storefront';
  if (authLoading || healthLoading) return 'loading';
  if (hasHealthError && !hasMetrics) return 'health_error';
  if (!hasMetrics) return 'empty';
  return 'metrics';
}
