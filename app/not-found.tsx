import Link from 'next/link';
import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff] px-4">
      <div className="text-center max-w-md">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-wedding-rose/70 mb-3">
          Page not found
        </p>
        <h1 className="text-5xl font-bold text-wedding-navy mb-4">404</h1>
        <p className="text-base text-wedding-navy/70 mb-8">
          This page doesn&apos;t exist or may have been moved. If you followed a link, it might be outdated.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-white shadow-lg transition hover:bg-wedding-rose/90"
          >
            Go to homepage
          </Link>
          <Link
            href={PUBLIC_LOGIN_PATH}
            className="inline-flex items-center justify-center rounded-full border border-wedding-navy/20 px-6 py-3 text-base font-semibold text-wedding-navy transition hover:border-wedding-navy/40"
          >
            Sign in to dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
