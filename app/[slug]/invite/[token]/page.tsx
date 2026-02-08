// app/[slug]/invite/[token]/page.tsx
// Redirects RSVP invite links to the couple's wedding page with RSVP modal

import { redirect } from 'next/navigation';

export const dynamic = 'force-dynamic';

export default async function InvitePage({ params }: { params: Promise<{ slug: string, token: string }> }) {
  const { slug, token } = await params;
  redirect(`/${slug}?rsvp_token=${token}`);
}
