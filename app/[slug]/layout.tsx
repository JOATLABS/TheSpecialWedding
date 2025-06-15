// app/[slug]/layout.tsx

import React from "react";
import { notFound } from "next/navigation";

// Create wedding context
import { WeddingContext } from '@/contexts/WeddingContext';

export async function fetchWeddingBySlug(slug: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const res = await fetch(`${base}/weddings/slug/${slug}`);
  if (!res.ok) return null;
  return await res.json();
}

export default async function WeddingLayout({ children, params }: { children: React.ReactNode; params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const wedding = await fetchWeddingBySlug(slug);

  if (!wedding) notFound();

  return (
    <html>
      <body>
        <WeddingContext.Provider value={wedding}>
          {children}
        </WeddingContext.Provider>
      </body>
    </html>
  );
}
