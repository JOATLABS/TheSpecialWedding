'use client';

import { useEffect } from 'react';
import { PRIVATE_ADMIN_LOGIN_PATH } from '@/seo/crawlPolicy';

export default function LoginRedirectClient() {
  useEffect(() => {
    window.location.replace(PRIVATE_ADMIN_LOGIN_PATH);
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16 text-white">
      <div className="mx-auto flex min-h-[70vh] max-w-md flex-col items-center justify-center text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-wedding-rose">
          The Special Wedding
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-normal">
          Opening your workspace sign-in.
        </h1>
        <p className="mt-4 text-sm leading-6 text-slate-300">
          Your browser will continue to the planner portal.
        </p>
        <button
          type="button"
          onClick={() => window.location.assign(PRIVATE_ADMIN_LOGIN_PATH)}
          className="mt-8 inline-flex rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-rose-50"
        >
          Continue to sign in
        </button>
      </div>
    </main>
  );
}
