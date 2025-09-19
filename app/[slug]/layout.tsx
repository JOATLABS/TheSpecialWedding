// app/[slug]/layout.tsx

import React from "react";
import { notFound } from "next/navigation";
import { WeddingProvider } from '@/components/WeddingProvider';

async function fetchWeddingPrivacyInfo(slug: string) {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not defined");
  }
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
  const minimalWedding = {
  id: privacyInfo.id ?? "", // or a sensible default
  date: privacyInfo.date ?? null, // or a sensible default
  events: privacyInfo.events ?? [], // or a sensible default
  couple_names: privacyInfo.couple_names,
  slug: slug,
  privacy_mode: privacyInfo.privacy_mode,
  requires_authentication: privacyInfo.privacy_mode === 'public' ? false : true
};

  return (
    <WeddingProvider wedding={minimalWedding}>
      {children}
    </WeddingProvider>
  );
}
