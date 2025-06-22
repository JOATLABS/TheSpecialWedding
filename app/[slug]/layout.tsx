// app/[slug]/layout.tsx

import React from "react";
import { notFound } from "next/navigation";
import { WeddingProvider } from '@/components/WeddingProvider';

export async function fetchWeddingBySlug(slug: string) {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/admin";
  const apiUrl = baseUrl.replace('/admin', ''); // Remove /admin for public endpoints
  const res = await fetch(`${apiUrl}/weddings/slug/${slug}`);
  if (!res.ok) return null;
  return await res.json();
}

export default async function WeddingLayout({ children, params }: { children: React.ReactNode; params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const wedding = await fetchWeddingBySlug(slug);

  if (!wedding) notFound();

  return (
    <WeddingProvider wedding={wedding}>
      {children}
    </WeddingProvider>
  );
}
