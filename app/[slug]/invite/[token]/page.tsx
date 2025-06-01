// app/[slug]/invite/[token]/page.tsx

import React from 'react';
import { notFound } from 'next/navigation';
import RSVPForm from '@/components/RSVPForm';

export async function fetchGuestByToken(slug: string, token: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const weddingRes = await fetch(`${base}/weddings/slug/${slug}`);
  if (!weddingRes.ok) return null;
  const wedding = await weddingRes.json();

  const guestRes = await fetch(`${base}/invite/${token}?wedding_id=${wedding._id}`);
  if (!guestRes.ok) return null;
  const guest = await guestRes.json();

  return { guest, wedding };
}

export default async function InvitePage({ params }: { params: { slug: string, token: string } }) {
  const { slug, token } = params;
  const data = await fetchGuestByToken(slug, token);
  if (!data) notFound();

  const { guest, wedding } = data;

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-4">
      <h1 className="text-3xl font-bold text-center">{wedding.couple_names}'s Wedding</h1>
      <p className="text-center text-gray-600">Hi {guest.name}! You're invited to celebrate with us.</p>
      <RSVPForm guest={guest} token={token} />
    </div>
  );
}
