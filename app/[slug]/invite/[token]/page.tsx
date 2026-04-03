'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';

import { exchangeGuestInviteToken } from '@/utils/guestAccess';


export default function InvitePage() {
  const params = useParams<{ slug: string; token: string }>();
  const router = useRouter();
  const slug = typeof params.slug === 'string' ? params.slug : '';
  const token = typeof params.token === 'string' ? params.token : '';
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    const exchangeInvite = async () => {
      if (!slug || !token) {
        if (active) {
          setError('The invitation link is incomplete.');
        }
        return;
      }

      try {
        await exchangeGuestInviteToken(slug, token);
        if (active) {
          router.replace(`/${slug}#rsvp`);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'We could not open this invitation.');
        }
      }
    };

    void exchangeInvite();

    return () => {
      active = false;
    };
  }, [router, slug, token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 to-pink-50 dark:from-slate-900 dark:to-slate-800">
      <div className="text-center max-w-md px-6">
        {error ? (
          <>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-white mb-3">Invitation unavailable</h1>
            <p className="text-slate-600 dark:text-slate-300 mb-6">{error}</p>
            <button
              type="button"
              onClick={() => router.replace(`/${slug}`)}
              className="inline-flex items-center rounded-full bg-rose-500 px-6 py-3 font-semibold text-slate-950 shadow-lg transition hover:opacity-90"
            >
              Go to Wedding Page
            </button>
          </>
        ) : (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-600 dark:border-rose-400 mx-auto mb-4"></div>
            <p className="text-slate-600 dark:text-slate-300">Opening your invitation…</p>
          </>
        )}
      </div>
    </div>
  );
}
