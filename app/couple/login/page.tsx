'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import { Heart, Loader2 } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const showcaseHighlights = [
  {
    label: 'Your wedding, at a glance',
    description: 'Timeline, budget, guest stats, forms, and messages — everything in one place.',
  },
  {
    label: 'Stay connected with your planner',
    description: 'Send messages, receive updates, and track every detail together in real-time.',
  },
];

const showcaseStats = [
  { value: 'Real-time', caption: 'Updates from your planner arrive instantly' },
  { value: 'Any device', caption: 'Access your portal from phone or desktop' },
];

function WelcomeShowcase() {
  return (
    <div className="relative w-full max-w-xl overflow-hidden rounded-[2.5rem] border border-white/45 bg-gradient-to-br from-white/65 via-white/30 to-white/10 p-6 shadow-[0_40px_120px_-40px_rgba(29,53,87,0.35)] backdrop-blur-2xl sm:p-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.65),transparent_55%),radial-gradient(circle_at_bottom_left,rgba(212,165,165,0.45),transparent_60%)]"
      />
      <div className="relative z-10 flex flex-col gap-6 text-wedding-navy">
        <header className="space-y-2">
          <p className="text-[0.6rem] font-semibold uppercase tracking-[0.3em] text-wedding-navy/65">Your wedding hub</p>
          <h2 className="text-[1.15rem] font-semibold leading-tight sm:text-[1.3rem]">Your special day, beautifully organized</h2>
          <p className="text-[0.78rem] text-wedding-navy/70 sm:text-sm">
            Everything you need to stay in the loop with your planner, track your budget, and prepare for your big day.
          </p>
        </header>

        <dl className="grid gap-3">
          {showcaseHighlights.map((highlight) => (
            <div
              key={highlight.label}
              className="relative overflow-hidden rounded-[1.8rem] border border-white/50 bg-white/60 p-4 shadow-lg backdrop-blur"
            >
              <div className="pointer-events-none absolute -right-6 -top-6 h-16 w-16 rounded-full bg-wedding-rose/20 blur-xl" aria-hidden="true" />
              <div className="pointer-events-none absolute -bottom-10 left-3 h-20 w-20 rounded-full bg-wedding-sage/20 blur-2xl" aria-hidden="true" />
              <div className="relative z-10 space-y-1.5">
                <dt className="text-[0.65rem] font-semibold uppercase tracking-[0.28em] text-wedding-navy/60">{highlight.label}</dt>
                <dd className="text-[0.8rem] leading-relaxed text-wedding-navy/75">{highlight.description}</dd>
              </div>
            </div>
          ))}
        </dl>

        <div className="grid grid-cols-2 gap-3">
          {showcaseStats.map((stat) => (
            <div
              key={stat.caption}
              className="rounded-[1.6rem] border border-white/45 bg-white/55 px-4 py-3 text-center shadow-inner backdrop-blur"
            >
              <div className="text-lg font-semibold text-wedding-navy">{stat.value}</div>
              <p className="mt-1 text-[0.7rem] text-wedding-navy/65">{stat.caption}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function CoupleLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const disableSubmit = !emailPattern.test(email) || password.length === 0 || loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (disableSubmit) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || 'Sign-in failed. Please check your email and password.');
        return;
      }

      localStorage.setItem('couple_token', data.access_token);
      localStorage.setItem('couple_data', JSON.stringify(data.couple));
      toast.success('Welcome back!');
      router.push('/couple/dashboard');
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]">
      {/* Ambient blurs — matches admin login */}
      <div aria-hidden="true" className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute bottom-[-6rem] left-[-6rem] h-[22rem] w-[22rem] rounded-full bg-wedding-navy/10 blur-3xl" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1600px] items-center px-4 py-12 sm:px-6 lg:px-12">
        <div className="relative isolate w-full overflow-hidden rounded-[3rem] border border-white/40 bg-white/25 p-6 shadow-2xl backdrop-blur-2xl sm:p-8">
          {/* Inner ambient blurs */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0">
            <div className="absolute -left-16 top-12 h-32 w-32 rounded-full bg-white/50 blur-3xl" />
            <div className="absolute -right-20 bottom-10 h-28 w-40 rounded-full bg-wedding-rose/20 blur-3xl" />
            <div className="absolute inset-y-12 left-1/2 hidden w-px -translate-x-1/2 bg-gradient-to-b from-white/5 via-white/50 to-white/5 opacity-70 blur-sm md:block" />
          </div>

          <div className="relative grid items-stretch gap-10 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-12 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
            {/* Right: Showcase */}
            <section className="order-2 flex justify-center md:order-2 md:pl-6 lg:pl-10">
              <div className="w-full">
                <WelcomeShowcase />
              </div>
            </section>

            {/* Left: Login form */}
            <section className="order-1 md:order-1 md:pr-6 lg:pr-10">
              <GlassCard depth="near" blur="xl" className="h-full px-6 py-7 sm:px-8 xl:px-10">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.3em] text-wedding-navy/70 sm:text-sm">Wedding portal</p>
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
                          tabIndex={-1}
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

                    <Button
                      type="submit"
                      disabled={disableSubmit}
                      isLoading={loading}
                      className="w-full"
                      size="lg"
                    >
                      Sign in
                    </Button>
                  </form>

                  <div className="text-center">
                    <Link
                      href="/couple/forgot-password"
                      className="text-sm text-wedding-navy/70 hover:text-wedding-navy transition-colors"
                    >
                      Forgot your password?
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
