'use client';

import { useEffect, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import { Heart } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';
import { clearLegacyCoupleStorage, extractApiErrorMessage } from '@/couple/lib/auth';
import { BrandLockup } from '@/components/brand/BrandLockup';
import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getStatusHeading(message: string | null): string {
  const normalized = message?.toLowerCase() ?? '';
  if (normalized.includes('inactive') || normalized.includes('unavailable') || normalized.includes('paused')) {
    return 'Portal access paused';
  }
  return 'Please sign in again';
}

export default function CoupleLoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    const message = new URLSearchParams(window.location.search).get('message');
    if (message) {
      setStatusMessage(message);
      toast.error(message);
    }
  }, []);

  const disableSubmit = !emailPattern.test(email) || password.length === 0 || loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (disableSubmit) return;

    setLoading(true);
    setError(null);
    setStatusMessage(null);

    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
        credentials: 'include',
      });

      if (!res.ok) {
        setError(await extractApiErrorMessage(res, 'Sign-in failed. Please check your email and password.'));
        return;
      }

      clearLegacyCoupleStorage();
      toast.success('Welcome back!');
      window.location.assign('/couple/dashboard');
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-dvh overflow-x-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]">
      {/* Ambient blurs — matches admin login */}
      <div aria-hidden="true" className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute bottom-[-6rem] left-[-6rem] h-[22rem] w-[22rem] rounded-full bg-wedding-navy/10 blur-3xl" />

      <div className="relative mx-auto flex min-h-dvh w-full max-w-3xl flex-col items-center justify-start gap-5 px-4 py-8 sm:gap-6 sm:px-6 sm:py-10 lg:justify-center lg:py-8">
        <header className="relative z-10 flex w-full justify-center px-2">
          <span className="sm:hidden">
            <BrandLockup
              variant="full"
              surface="light"
              size="lg"
              className="drop-shadow-[0_16px_36px_rgba(29,53,87,0.16)]"
            />
          </span>
          <span className="hidden sm:block">
            <BrandLockup
              variant="full"
              surface="light"
              size="xl"
              className="drop-shadow-[0_18px_42px_rgba(29,53,87,0.18)]"
            />
          </span>
        </header>
        <div className="relative isolate w-full overflow-hidden rounded-[2rem] border border-white/40 bg-white/25 p-3 shadow-2xl backdrop-blur-2xl sm:rounded-[3rem] sm:p-6">
          {/* Inner ambient blurs */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0">
            <div className="absolute -left-16 top-12 h-32 w-32 rounded-full bg-white/50 blur-3xl" />
            <div className="absolute -right-20 bottom-10 h-28 w-40 rounded-full bg-wedding-rose/20 blur-3xl" />
          </div>

          <div className="relative">
            <section>
              <GlassCard depth="near" blur="xl" className="px-5 py-6 sm:px-8 sm:py-7 xl:px-10">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase text-wedding-navy/70 sm:text-sm">Wedding portal</p>
                    <h1 className="mt-2 text-[1.6rem] font-semibold text-wedding-navy sm:text-[1.8rem]">Welcome back</h1>
                    <p className="mt-2 text-[0.9rem] text-wedding-navy/70">
                      Sign in to view your wedding details, messages, and more.
                    </p>
                  </div>
                  <div className="hidden shrink-0 rounded-full bg-white/50 p-4 text-wedding-rose backdrop-blur sm:block">
                    <Heart className="h-8 w-8" aria-hidden="true" />
                  </div>
                </div>

                <div className="mt-6 space-y-5">
                  <form className="space-y-4" onSubmit={handleSubmit} noValidate>
                    <div className="space-y-2">
                      <label htmlFor="email" className="text-sm font-medium text-wedding-navy">
                        Email
                      </label>
                      <input
                        id="email"
                        type="email"
                        inputMode="email"
                        autoComplete="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        aria-invalid={error !== null && !emailPattern.test(email)}
                        className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 text-base text-wedding-navy shadow-inner placeholder:text-wedding-navy/40 focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                        placeholder="your@email.com"
                      />
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="password" className="text-sm font-medium text-wedding-navy">
                        Password
                      </label>
                      <div className="relative">
                        <input
                          id="password"
                          type={showPassword ? 'text' : 'password'}
                          autoComplete="current-password"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          required
                          className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 pr-12 text-base text-wedding-navy shadow-inner placeholder:text-wedding-navy/40 focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                          placeholder="Enter your password"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute inset-y-0 right-0 flex items-center rounded-r-xl px-4 text-sm font-medium text-wedding-navy/80 hover:text-wedding-rose focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose/60"
                          aria-pressed={showPassword}
                        >
                          {showPassword ? 'Hide' : 'Show'}
                        </button>
                      </div>
                    </div>

                    {error && (
                      <p role="alert" className="rounded-lg border border-wedding-rose/40 bg-wedding-rose/10 px-3 py-2 text-sm text-wedding-rose">
                        {error}
                      </p>
                    )}

                    {statusMessage && !error && (
                      <div
                        role="status"
                        className="rounded-lg border border-amber-300/70 bg-amber-50 px-3 py-3 text-sm text-amber-800"
                      >
                        <p className="font-semibold">
                          {getStatusHeading(statusMessage)}
                        </p>
                        <p className="mt-1">{statusMessage}</p>
                      </div>
                    )}

                    <Button
                      type="submit"
                      disabled={disableSubmit}
                      isLoading={loading}
                      className="w-full justify-center rounded-xl py-3 text-base shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60"
                      size="lg"
                    >
                      Sign in
                    </Button>
                  </form>

                  <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-center">
                    <Link
                      href="/couple/forgot-password"
                      className="text-sm text-wedding-navy/70 hover:text-wedding-navy transition-colors"
                    >
                      Forgot your password?
                    </Link>
                    <Link
                      href={PUBLIC_LOGIN_PATH}
                      className="text-sm text-wedding-navy/60 hover:text-wedding-navy transition-colors"
                    >
                      Planner Portal →
                    </Link>
                  </div>

                  <div className="border-t border-white/30 pt-4 text-center">
                    <p className="text-sm text-wedding-navy/60">
                      Don&apos;t have an account? Your planner will send you an invitation.
                    </p>
                  </div>
                </div>
              </GlassCard>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
