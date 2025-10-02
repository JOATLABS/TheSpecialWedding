'use client';

import Link from 'next/link';
import { FormEvent, useMemo, useState } from 'react';

import { SocialAuthButtons } from '@/components/auth/SocialAuthButtons';
import { Button } from '@/components/ui/Button';
import { GlassCard } from '@/components/ui/GlassCard';
import { useAdmin } from '@/contexts/AdminContext';

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function WelcomeShowcase() {
  return (
    <div className="relative w-full max-w-md rounded-[2rem] border border-white/45 bg-gradient-to-br from-white/70 via-white/35 to-white/5 p-6 shadow-2xl backdrop-blur-xl">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.6),transparent_45%),radial-gradient(circle_at_bottom_right,rgba(240,224,255,0.5),transparent_55%)]"
      />
      <div className="relative z-10 space-y-6 text-wedding-navy">
        <div className="space-y-2">
          <p className="text-[0.65rem] font-semibold uppercase tracking-[0.35em] text-wedding-navy/70">Planner experience</p>
          <h2 className="text-xl font-semibold leading-snug sm:text-2xl">Operate with confidence</h2>
          <p className="text-[0.8rem] text-wedding-navy/75 sm:text-sm">
            A focused command centre that keeps budgets, forms, and vendor comms aligned without overwhelming the first screen.
          </p>
        </div>

        <dl className="grid gap-3">
          <div className="flex items-start gap-3 rounded-3xl border border-white/50 bg-white/55 p-3 shadow-lg backdrop-blur">
            <div className="mt-1 rounded-full bg-wedding-rose/20 p-2 text-wedding-rose">
              <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 6v6l3 3" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="12" cy="12" r="9" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="space-y-1">
              <dt className="text-xs font-semibold">Real-time status</dt>
              <dd className="text-[0.72rem] text-wedding-navy/70">Review budgets and KPIs in a single glance.</dd>
            </div>
          </div>
          <div className="flex items-start gap-3 rounded-3xl border border-white/50 bg-white/55 p-3 shadow-lg backdrop-blur">
            <div className="mt-1 rounded-full bg-wedding-navy/10 p-2 text-wedding-navy">
              <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M5 12l5 5L19 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="space-y-1">
              <dt className="text-xs font-semibold">Seamless onboarding</dt>
              <dd className="text-[0.72rem] text-wedding-navy/70">SSO-first flows keep every login fast and secure.</dd>
            </div>
          </div>
        </dl>

        <div className="rounded-3xl border border-white/40 bg-white/45 p-4 text-[0.72rem] text-wedding-navy/70 shadow-inner backdrop-blur">
          <h3 className="text-xs font-semibold text-wedding-navy">Mobile friendly by default</h3>
          <p className="mt-1.5">Glass surface densities and spacing follow 2025 Apple design guidance for a calm, legible welcome on any screen.</p>
        </div>
      </div>
    </div>
  );
}

export default function AdminLoginPage() {
  const { login } = useAdmin();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const disableSubmit = useMemo(() => {
    if (!emailPattern.test(email)) {
      return true;
    }
    return password.length === 0 || submitting;
  }, [email, password.length, submitting]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (disableSubmit) {
      setError('Enter a valid email address and password to continue.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await login(email.trim(), password, rememberMe);
    } catch (err) {
      setError('We could not sign you in. Double-check your credentials or try another method.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-[-6rem] left-[-6rem] h-[22rem] w-[22rem] rounded-full bg-wedding-navy/10 blur-3xl"
      />

      <div className="relative mx-auto flex w-full max-w-5xl items-stretch px-4 py-12 sm:px-6 lg:py-16">
        <div className="relative isolate w-full overflow-hidden rounded-[3rem] border border-white/40 bg-white/25 p-5 shadow-2xl backdrop-blur-2xl sm:p-8">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0">
            <div className="absolute -left-16 top-12 h-32 w-32 rounded-full bg-white/50 blur-3xl" />
            <div className="absolute -right-20 bottom-10 h-28 w-40 rounded-full bg-wedding-rose/20 blur-3xl" />
            <div className="absolute inset-y-12 left-1/2 hidden w-px -translate-x-1/2 bg-gradient-to-b from-white/5 via-white/50 to-white/5 opacity-70 blur-sm lg:block" />
          </div>

          <div className="relative grid items-center gap-8 lg:grid-cols-[0.95fr_1fr] lg:gap-10">
            <section className="order-2 flex justify-center lg:order-1 lg:pr-6">
              <div className="mx-auto w-full max-w-xs sm:max-w-sm lg:mx-0">
                <WelcomeShowcase />
              </div>
            </section>

            <section className="order-1 lg:order-2 lg:pl-6">
              <GlassCard depth="near" blur="xl" className="px-7 py-8 sm:px-10">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.3em] text-wedding-navy/70 sm:text-sm">Planner portal</p>
                    <h1 className="mt-2 text-2xl font-semibold text-wedding-navy sm:text-3xl">Welcome back, planner</h1>
                    <p className="mt-2 text-sm text-wedding-navy/70">
                      Securely access your automation workspace to review budgets, forms, analytics, and notifications in one place.
                    </p>
                  </div>
                  <div className="hidden shrink-0 rounded-full bg-white/50 p-4 text-wedding-rose backdrop-blur sm:block">
                    <svg aria-hidden="true" className="h-8 w-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path
                        d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-3.53 0-8 1.79-8 5.33V21h16v-1.67C20 15.79 15.53 14 12 14z"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                </div>

                <div className="mt-6 space-y-5">
                  <div>
                    <SocialAuthButtons flow="login" redirectPath="/admin" />
                    <p className="mt-3 text-xs text-wedding-navy/60">
                      Use your organisation&apos;s Google Workspace or Apple ID to keep access fast, secure, and passwordless on any device.
                    </p>
                  </div>

                  <div className="flex items-center gap-3 text-xs font-medium uppercase tracking-[0.3em] text-wedding-navy/40">
                    <div className="h-px flex-1 bg-gradient-to-r from-transparent via-wedding-navy/30 to-transparent" aria-hidden="true" />
                    <span>Or email</span>
                    <div className="h-px flex-1 bg-gradient-to-r from-transparent via-wedding-navy/30 to-transparent" aria-hidden="true" />
                  </div>

                  <form className="space-y-4" onSubmit={handleSubmit} noValidate>
                    <div className="space-y-2">
                      <label htmlFor="email" className="text-sm font-medium text-wedding-navy">
                        Work email
                      </label>
                      <input
                        id="email"
                        type="email"
                        inputMode="email"
                        autoComplete="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        required
                        aria-invalid={error !== null && !emailPattern.test(email)}
                        aria-describedby="email-guidance"
                        className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 text-base text-wedding-navy shadow-inner placeholder:text-wedding-navy/40 focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                      />
                      <p id="email-guidance" className="text-xs text-wedding-navy/60">
                        We use your email to match your planner workspace. Use the address registered with your organisation.
                      </p>
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
                          onChange={(event) => setPassword(event.target.value)}
                          required
                          aria-invalid={error !== null && password.length === 0}
                          className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 pr-12 text-base text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword((previous) => !previous)}
                          className="absolute inset-y-0 right-0 flex items-center rounded-r-xl px-4 text-sm font-medium text-wedding-navy/80 hover:text-wedding-rose focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose/60"
                          aria-pressed={showPassword}
                        >
                          {showPassword ? 'Hide' : 'Show'}
                        </button>
                      </div>
                    </div>

                    <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
                      <label className="flex items-center gap-2 text-sm text-wedding-navy">
                        <input
                          type="checkbox"
                          checked={rememberMe}
                          onChange={(event) => setRememberMe(event.target.checked)}
                          className="h-4 w-4 rounded border-wedding-navy/20 text-wedding-rose focus:ring-wedding-rose/60"
                        />
                        <span>Keep me signed in on this device</span>
                      </label>
                      <Link
                        href="/"
                        className="text-sm font-medium text-wedding-rose transition hover:text-wedding-gold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose/60"
                      >
                        Return to SaaS home
                      </Link>
                    </div>

                    {error && (
                      <p role="alert" className="rounded-lg border border-wedding-rose/40 bg-wedding-rose/10 px-3 py-2 text-sm text-wedding-rose">
                        {error}
                      </p>
                    )}

                    <Button
                      type="submit"
                      disabled={disableSubmit}
                      className="w-full justify-center rounded-xl py-3 text-base shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60"
                      aria-busy={submitting}
                    >
                      {submitting ? 'Signing you in…' : 'Log in to planner portal'}
                    </Button>
                  </form>
                </div>

                <div className="mt-6 rounded-2xl border border-white/30 bg-white/40 px-5 py-4 text-sm text-wedding-navy/70 shadow-inner">
                  <h2 className="text-xs font-semibold uppercase tracking-[0.25em] text-wedding-navy/60 sm:text-sm">Mobile ready</h2>
                  <p className="mt-1.5 text-xs sm:text-sm">
                    Adaptive layout, biometric-friendly SSO, and WCAG AA contrast keep the portal effortless on phones and tablets without introducing extra scrolling.
                  </p>
                </div>
              </GlassCard>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
