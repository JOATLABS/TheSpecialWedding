'use client';

import Link from 'next/link';
import { FormEvent, useMemo, useState } from 'react';

import { SocialAuthButtons } from '@/components/auth/SocialAuthButtons';
import { Button } from '@/components/ui/Button';
import { GlassCard } from '@/components/ui/GlassCard';
import { useAdmin } from '@/contexts/AdminContext';

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const floatingWordConfig = [
  { text: 'Welcome planners', top: '12%', left: '18%', delay: '0s' },
  { text: 'Unified budgets', top: '58%', left: '10%', delay: '1.5s' },
  { text: 'Glassmorphic flows', top: '26%', left: '58%', delay: '3s' },
  { text: 'Secure SSO', top: '70%', left: '55%', delay: '4.5s' },
  { text: 'Mobile ready', top: '40%', left: '77%', delay: '6s' },
];

function FloatingWelcomeWords() {
  return (
    <div className="relative flex h-[22rem] w-full items-center justify-center overflow-hidden rounded-[2.5rem] border border-white/40 bg-white/30 p-10 shadow-2xl backdrop-blur-xl lg:h-[24rem] xl:h-[26rem]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/40 via-white/20 to-transparent"
      />
      <div className="relative h-full w-full">
        <p className="sr-only">Celebratory welcome words animate to introduce the planner portal.</p>
        {floatingWordConfig.map((word) => (
          <span
            key={word.text}
            aria-hidden="true"
            className="floating-word select-none text-base font-semibold tracking-wide text-wedding-navy/80 sm:text-lg"
            style={{ top: word.top, left: word.left, animationDelay: word.delay }}
          >
            {word.text}
          </span>
        ))}
      </div>
      <style jsx>{`
        .floating-word {
          position: absolute;
          padding: 0.75rem 1.5rem;
          border-radius: 9999px;
          background: linear-gradient(135deg, rgba(255, 255, 255, 0.85), rgba(255, 255, 255, 0.55));
          box-shadow: 0 12px 30px -20px rgba(14, 28, 64, 0.5);
          animation: floatUp 11s ease-in-out infinite;
          will-change: transform;
        }

        .floating-word:nth-child(odd) {
          animation-duration: 9s;
        }

        @keyframes floatUp {
          0% {
            transform: translate3d(0, 0, 0);
          }
          45% {
            transform: translate3d(0, -16px, 0);
          }
          55% {
            transform: translate3d(0, -16px, 0);
          }
          100% {
            transform: translate3d(0, 0, 0);
          }
        }
      `}</style>
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
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-[-6rem] left-[-6rem] h-[22rem] w-[22rem] rounded-full bg-wedding-navy/10 blur-3xl"
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl items-center px-4 py-16 sm:px-8">
        <div className="relative isolate w-full overflow-hidden rounded-[3rem] border border-white/40 bg-white/25 p-6 shadow-2xl backdrop-blur-2xl sm:p-10 lg:p-12">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0">
            <div className="absolute -left-16 top-12 h-32 w-32 rounded-full bg-white/50 blur-3xl" />
            <div className="absolute -right-20 bottom-10 h-28 w-40 rounded-full bg-wedding-rose/20 blur-3xl" />
            <div className="absolute inset-y-12 left-1/2 hidden w-px -translate-x-1/2 bg-gradient-to-b from-white/5 via-white/50 to-white/5 opacity-70 blur-sm lg:block" />
          </div>

          <div className="relative grid gap-12 lg:grid-cols-2 lg:gap-16">
            <section className="order-2 flex flex-col justify-center lg:order-1 lg:pr-6">
              <div className="mx-auto w-full max-w-md lg:mx-0">
                <FloatingWelcomeWords />
              </div>

              <GlassCard
                depth="far"
                blur="lg"
                className="mt-10 space-y-4 border border-white/40 bg-white/45 p-8 text-left text-wedding-navy/80"
              >
                <h2 className="text-lg font-semibold text-wedding-navy">Why this flow follows 2025 best practices</h2>
                <p>
                  Research-backed login design keeps the SSO path primary, provides inline guidance, and preserves trust with transparent security messaging.
                  Linking directly from the SaaS landing page sets clear expectations and avoids dead ends.
                </p>
                <p>
                  On mobile, the layout collapses gracefully, ensuring thumb-friendly spacing, accessible typography, and performant gradients without compromising readability or control sizes.
                </p>
                <p>
                  Need provisioning changes? Ask your organisation&apos;s owner to add your email in the admin settings before attempting sign in.
                </p>
              </GlassCard>
            </section>

            <section className="order-1 lg:order-2 lg:pl-6">
              <GlassCard depth="near" blur="xl" className="h-full px-8 py-10 sm:px-12">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium uppercase tracking-[0.3em] text-wedding-navy/70">Planner portal</p>
                    <h1 className="mt-3 text-3xl font-semibold text-wedding-navy sm:text-4xl">Welcome back, planner</h1>
                    <p className="mt-2 text-sm text-wedding-navy/70 sm:text-base">
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

                <div className="mt-8 space-y-6">
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

                  <form className="space-y-5" onSubmit={handleSubmit} noValidate>
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

                <div className="mt-8 rounded-2xl border border-white/30 bg-white/40 px-6 py-5 text-sm text-wedding-navy/70 shadow-inner">
                  <h2 className="text-sm font-semibold uppercase tracking-[0.25em] text-wedding-navy/60">Mobile ready</h2>
                  <p className="mt-2">
                    Optimised spacing, large tap targets, and biometric-friendly single sign-on mean the planner portal works beautifully on phones and tablets.
                  </p>
                  <ul className="mt-3 space-y-2 text-sm">
                    <li className="flex items-start gap-2">
                      <span aria-hidden="true" className="mt-1 h-2 w-2 rounded-full bg-wedding-rose" />
                      <span>Adaptive layout scales from 320px to desktop without losing readability.</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span aria-hidden="true" className="mt-1 h-2 w-2 rounded-full bg-wedding-navy" />
                      <span>Glassmorphic surfaces maintain contrast ratios that pass WCAG AA.</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span aria-hidden="true" className="mt-1 h-2 w-2 rounded-full bg-wedding-gold" />
                      <span>Touch optimised toggles, buttons, and authentication flows reduce friction for on-the-go planners.</span>
                    </li>
                  </ul>
                </div>
              </GlassCard>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
