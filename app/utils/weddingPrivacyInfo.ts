import { cache } from 'react';

import { getServerApiBaseUrl } from '@/utils/env';
import { isNonWeddingSlug } from '@/utils/slug-constants';

export interface WeddingPrivacyInfo {
  id?: string;
  _id?: string;
  couple_names?: string;
  date?: string;
  privacy_mode?: 'private' | 'password' | 'public';
  requires_password?: boolean;
  requires_guest_verification?: boolean;
  featured_image?: string;
  theme_config?: Record<string, unknown>;
  rsvp_config?: Record<string, unknown>;
  events?: unknown[];
  registries?: unknown[];
  faqs?: unknown[];
  our_story?: Record<string, unknown> | null;
  venue?: Record<string, unknown> | string | null;
  wedding_party?: unknown[];
  verification_requirements?: Record<string, unknown>;
}

export type WeddingPrivacyInfoResult =
  | { kind: 'ok'; privacyInfo: WeddingPrivacyInfo }
  | { kind: 'not_found' }
  | { kind: 'error'; status: number | null; message: string };

function getPrivacyInfoRevalidateSeconds(): number {
  const parsed = Number.parseInt(process.env.WEDDING_PRIVACY_INFO_REVALIDATE_SECONDS ?? '30', 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }
  return 30;
}

export const fetchWeddingPrivacyInfo = cache(async (slug: string): Promise<WeddingPrivacyInfoResult> => {
  if (isNonWeddingSlug(slug)) {
    return { kind: 'not_found' };
  }

  const baseUrl = getServerApiBaseUrl();
  const apiUrl = baseUrl.replace('/admin', '');

  try {
    const response = await fetch(`${apiUrl}/weddings/privacy-info/${slug}`, {
      next: {
        revalidate: getPrivacyInfoRevalidateSeconds(),
        tags: [`wedding-privacy:${slug}`],
      },
    });

    if (response.status === 404) {
      return { kind: 'not_found' };
    }

    if (!response.ok) {
      return {
        kind: 'error',
        status: response.status,
        message: `Privacy bootstrap request failed with status ${response.status}`,
      };
    }

    let privacyInfo: WeddingPrivacyInfo;
    try {
      privacyInfo = (await response.json()) as WeddingPrivacyInfo;
    } catch {
      return {
        kind: 'error',
        status: response.status,
        message: 'Privacy bootstrap response was not valid JSON',
      };
    }

    return {
      kind: 'ok',
      privacyInfo,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown privacy bootstrap error';
    return {
      kind: 'error',
      status: null,
      message: `Privacy bootstrap request failed: ${message}`,
    };
  }
});
