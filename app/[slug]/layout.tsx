// app/[slug]/layout.tsx

import React from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { WeddingProvider } from '@/components/WeddingProvider';
import { Wedding } from '@/types/wedding';
import ErrorBoundary from '@/components/ErrorBoundary';
import { fetchWeddingPrivacyInfo } from '@/utils/weddingPrivacyInfo';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const privacyInfoResult = await fetchWeddingPrivacyInfo(slug);

  if (privacyInfoResult.kind !== 'ok') {
    return { title: 'Wedding' };
  }

  const privacyInfo = privacyInfoResult.privacyInfo;

  const coupleNames = privacyInfo.couple_names || 'Wedding';
  const weddingDate = privacyInfo.date
    ? new Date(privacyInfo.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : '';
  const venue = typeof privacyInfo.venue === 'string'
    ? privacyInfo.venue
    : typeof privacyInfo.venue?.name === 'string'
      ? privacyInfo.venue.name
      : '';

  const titleParts = [coupleNames];
  if (weddingDate) titleParts.push(weddingDate);
  const title = titleParts.join(' — ');

  const descParts = [`Celebrate with ${coupleNames}`];
  if (weddingDate) descParts.push(`on ${weddingDate}`);
  if (venue) descParts.push(`at ${venue}`);
  const description = descParts.join(' ') + '. View event details, RSVP, and more.';

  // Private weddings should not be indexed by search engines
  const isPrivate = privacyInfo.privacy_mode !== 'public';

  return {
    title,
    description,
    robots: isPrivate ? { index: false, follow: false } : undefined,
    openGraph: isPrivate ? undefined : {
      title: `${coupleNames} | The Special Wedding`,
      description,
    },
  };
}

export default async function WeddingLayout({ children, params }: { children: React.ReactNode; params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const privacyInfoResult = await fetchWeddingPrivacyInfo(slug);

  if (privacyInfoResult.kind === 'not_found') {
    notFound();
  }

  if (privacyInfoResult.kind === 'error') {
    throw new Error(privacyInfoResult.message);
  }

  const privacyInfo = privacyInfoResult.privacyInfo;

  // Pass minimal wedding info for the layout
  // The actual wedding data will be loaded by the client-side verification
  // For public weddings, we include full data since no verification is needed
  const minimalWedding: Wedding = {
    id: privacyInfo.id ?? privacyInfo._id ?? slug,
    slug,
    couple_names: privacyInfo.couple_names ?? '',
    date: privacyInfo.date ?? new Date().toISOString(),
    events: Array.isArray(privacyInfo.events) ? (privacyInfo.events as unknown as Wedding['events']) : [],
    requires_authentication: privacyInfo.privacy_mode === 'public' ? false : true,
    privacy_mode: privacyInfo.privacy_mode,
    ...(privacyInfo.featured_image ? { featured_image: privacyInfo.featured_image } : {}),
    ...(privacyInfo.theme_config ? { theme_config: privacyInfo.theme_config as unknown as Wedding['theme_config'] } : {}),
    ...(privacyInfo.rsvp_config ? { rsvp_config: privacyInfo.rsvp_config as unknown as Wedding['rsvp_config'] } : {}),
    // Include additional data for public weddings
    ...(Array.isArray(privacyInfo.registries) ? { registries: privacyInfo.registries as unknown as Wedding['registries'] } : {}),
    ...(Array.isArray(privacyInfo.faqs) ? { faqs: privacyInfo.faqs as unknown as Wedding['faqs'] } : {}),
    ...(privacyInfo.our_story ? { our_story: privacyInfo.our_story as unknown as Wedding['our_story'] } : {}),
    ...(privacyInfo.venue ? { venue: privacyInfo.venue as unknown as Wedding['venue'] } : {}),
    ...(Array.isArray(privacyInfo.wedding_party) ? { wedding_party: privacyInfo.wedding_party as unknown as Wedding['wedding_party'] } : {}),
  };

  return (
    <ErrorBoundary>
      <WeddingProvider wedding={minimalWedding}>
        {children}
      </WeddingProvider>
    </ErrorBoundary>
  );
}
