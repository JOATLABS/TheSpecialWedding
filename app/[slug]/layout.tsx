// app/[slug]/layout.tsx

import React from "react";
import { notFound } from "next/navigation";
import { WeddingProvider } from '@/components/WeddingProvider';
import { Wedding } from '@/types/wedding';

async function fetchWeddingPrivacyInfo(slug: string) {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/admin";
  const apiUrl = baseUrl.replace('/admin', ''); // Remove /admin for public endpoints
  try {
    const res = await fetch(`${apiUrl}/weddings/privacy-info/${slug}`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch (error) {
    return null;
  }
}

export default async function WeddingLayout({ children, params }: { children: React.ReactNode; params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const privacyInfo = await fetchWeddingPrivacyInfo(slug);

  if (!privacyInfo) notFound();

  // Pass minimal wedding info for the layout
  // The actual wedding data will be loaded by the client-side verification
  const minimalWedding: Wedding = {
    id: privacyInfo.id ?? privacyInfo._id ?? slug,
    slug,
    couple_names: privacyInfo.couple_names ?? '',
    date: privacyInfo.date ?? new Date().toISOString(),
    events: Array.isArray(privacyInfo.events) ? privacyInfo.events : [],
    requires_authentication: privacyInfo.privacy_mode === 'public' ? false : true,
    privacy_mode: privacyInfo.privacy_mode,
    ...(privacyInfo.theme_config ? { theme_config: privacyInfo.theme_config } : {}),
    ...(privacyInfo.rsvp_config ? { rsvp_config: privacyInfo.rsvp_config } : {}),
  };

  return (
    <WeddingProvider wedding={minimalWedding}>
      {children}
    </WeddingProvider>
  );
}
