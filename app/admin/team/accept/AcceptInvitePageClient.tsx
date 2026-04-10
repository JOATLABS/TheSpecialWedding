'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast, Toaster } from 'sonner';
import { Loader2, Eye, EyeOff, Shield, CheckCircle2, AlertCircle } from 'lucide-react';

import { getApiBaseUrl } from '@/utils/env';

interface InviteInfo {
  email: string;
  role: string;
  permissions: Record<string, boolean>;
  company_name: string | null;
  planner_name: string | null;
  is_expired: boolean;
}

const PERMISSION_LABELS: Record<string, string> = {
  manage_guests: 'Manage Guests',
  manage_budget: 'Manage Budget',
  manage_gallery: 'Manage Gallery',
  manage_seating: 'Manage Seating',
  manage_vendors: 'Manage Vendors',
  send_rsvp: 'Send RSVP',
  send_reminders: 'Send Reminders',
  manage_forms: 'Manage Forms',
  view_analytics: 'View Analytics',
  manage_wedding_settings: 'Wedding Settings',
  manage_contracts: 'Manage Contracts',
  manage_packages: 'Manage Packages',
  manage_couple_portal: 'Manage Couple Portal',
  message_couples: 'Message Couples',
  view_shared_calendar: 'View Shared Calendar',
  view_calendar_details: 'View Calendar Details',
  connect_personal_calendar: 'Connect Personal Calendar',
  manage_calendar_connections: 'Manage Calendar Connections',
  schedule_meetings: 'Schedule Meetings',
  edit_meetings: 'Edit Meetings',
  cancel_meetings: 'Cancel Meetings',
  send_meeting_invites: 'Send Meeting Invites',
  view_team_availability: 'View Team Availability',
  manage_calendar_tasks: 'Manage Calendar Tasks',
  sync_calendar_tasks: 'Sync Calendar Tasks',
};

const pageBackgroundClass =
  'min-h-screen bg-gradient-to-br from-rose-50 via-white to-sky-50 dark:from-dark-bg dark:to-slate-800';

const cardClass =
  'rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700/50 dark:bg-slate-800/60 dark:shadow-none dark:backdrop-blur-xl';

const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 transition-colors focus:border-wedding-rose focus:outline-none dark:border-slate-700/50 dark:bg-slate-900/60 dark:text-slate-200 dark:placeholder:text-slate-600';

export default function AcceptInvitePageClient({ initialToken }: { initialToken: string | null }) {
  const router = useRouter();
  const token = initialToken;

  const [inviteInfo, setInviteInfo] = useState<InviteInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Invalid invitation link. No token provided.');
      setLoading(false);
      return;
    }

    const fetchInviteInfo = async () => {
      try {
        const baseUrl = getApiBaseUrl();
        const response = await fetch(`${baseUrl}/admin/team/invite-info/${token}`);

        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.detail || 'This invitation is no longer valid.');
        }

        const data = await response.json();
        setInviteInfo(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load invitation details.');
      } finally {
        setLoading(false);
      }
    };

    void fetchInviteInfo();
  }, [token]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!firstName.trim() || !lastName.trim()) {
      toast.error('Please enter your first and last name.');
      return;
    }

    if (password.length < 8) {
      toast.error('Password must be at least 8 characters.');
      return;
    }

    if (!/[A-Z]/.test(password)) {
      toast.error('Password must contain at least one uppercase letter.');
      return;
    }

    if (!/[a-z]/.test(password)) {
      toast.error('Password must contain at least one lowercase letter.');
      return;
    }

    if (!/\d/.test(password)) {
      toast.error('Password must contain at least one number.');
      return;
    }

    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
      toast.error('Password must contain at least one special character.');
      return;
    }

    if (password !== confirmPassword) {
      toast.error('Passwords do not match.');
      return;
    }

    setSubmitting(true);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/team/accept-invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          password,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to accept invitation.');
      }

      setSuccess(true);
      toast.success('Welcome to the team!');

      setTimeout(() => {
        router.push('/admin/login?success=invitation_accepted');
      }, 2500);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const enabledPermissions = inviteInfo
    ? Object.entries(inviteInfo.permissions)
        .filter(([, enabled]) => enabled)
        .map(([key]) => PERMISSION_LABELS[key] || key)
    : [];

  const roleColors: Record<string, string> = {
    admin: 'border border-rose-200 bg-rose-50 text-rose-700 dark:border-transparent dark:bg-[rgba(212,165,165,0.15)] dark:text-wedding-rose',
    editor: 'border border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-transparent dark:bg-[rgba(168,218,220,0.15)] dark:text-wedding-sage',
    viewer: 'border border-slate-200 bg-slate-100 text-slate-600 dark:border-transparent dark:bg-slate-500/15 dark:text-slate-400',
  };

  if (loading) {
    return (
      <div className={`${pageBackgroundClass} flex items-center justify-center`}>
        <Toaster position="top-right" richColors />
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-wedding-rose mx-auto" />
          <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">Loading invitation…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`${pageBackgroundClass} flex items-center justify-center p-6`}>
        <Toaster position="top-right" richColors />
        <div className="w-full max-w-md text-center">
          <div className="mb-6 inline-flex h-16 w-16 items-center justify-center rounded-full bg-red-50 dark:bg-red-500/10">
            <AlertCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
          </div>
          <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-200">Invitation Not Found</h2>
          <p className="mb-6 text-slate-600 dark:text-slate-400">{error}</p>
          <button
            onClick={() => router.push('/admin/login')}
            className="text-wedding-rose hover:text-wedding-rose/80 text-sm font-medium transition-colors"
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className={`${pageBackgroundClass} flex items-center justify-center p-6`}>
        <Toaster position="top-right" richColors />
        <div className="w-full max-w-md text-center">
          <div className="mb-6 inline-flex h-16 w-16 items-center justify-center rounded-full bg-emerald-50 dark:bg-green-500/10">
            <CheckCircle2 className="h-8 w-8 text-emerald-600 dark:text-green-400" />
          </div>
          <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-200">Welcome to the team!</h2>
          <p className="mb-2 text-slate-600 dark:text-slate-400">Your account has been created successfully.</p>
          <p className="text-sm text-slate-500 dark:text-slate-500">Redirecting you to login…</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${pageBackgroundClass} flex items-center justify-center p-6`}>
      <Toaster position="top-right" richColors />
      <div className="w-full max-w-[480px]">
        <div className="text-center mb-8">
          <img
            src="/logo.svg"
            alt="The Special Wedding"
            width={160}
            height={40}
            className="mx-auto mb-3 block"
          />
          <p className="text-sm text-slate-500 dark:text-slate-400">You&apos;ve been invited to join a team</p>
        </div>

        <div className={cardClass}>
          <div className="text-center mb-6">
            <p className="mb-2 text-slate-700 dark:text-slate-200">
              <span className="font-semibold">{inviteInfo?.company_name || inviteInfo?.planner_name || 'A wedding planner'}</span>{' '}
              invited you as
            </p>
            <span
              className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold ${
                roleColors[inviteInfo?.role || 'viewer']
              }`}
            >
              <Shield className="w-3.5 h-3.5" />
              {inviteInfo?.role ? inviteInfo.role.charAt(0).toUpperCase() + inviteInfo.role.slice(1) : 'Member'}
            </span>
            {inviteInfo?.email && (
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                Invitation sent to <span className="font-medium text-slate-700 dark:text-slate-300">{inviteInfo.email}</span>
              </p>
            )}
          </div>

          {enabledPermissions.length > 0 && (
            <div className="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700/40 dark:bg-slate-900/40">
              <p className="mb-2.5 text-xs uppercase tracking-wider text-slate-500">Your permissions</p>
              <div className="flex flex-wrap gap-1.5">
                {enabledPermissions.map((permission) => (
                  <span
                    key={permission}
                    className="rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:border-transparent dark:bg-wedding-sage/10 dark:text-wedding-sage"
                  >
                    {permission}
                  </span>
                ))}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} data-testid="accept-form">
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-700 dark:text-slate-400">First Name</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(event) => setFirstName(event.target.value)}
                  placeholder="First name…"
                  data-testid="first-name"
                  className={inputClass}
                  autoComplete="given-name"
                  required
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-700 dark:text-slate-400">Last Name</label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(event) => setLastName(event.target.value)}
                  placeholder="Last name…"
                  data-testid="last-name"
                  className={inputClass}
                  autoComplete="family-name"
                  required
                />
              </div>
            </div>

            <div className="mb-4">
              <label className="mb-1.5 block text-xs font-medium text-slate-700 dark:text-slate-400">Create Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Min 8 characters…"
                  data-testid="password-input"
                  className={`${inputClass} pr-10`}
                  autoComplete="new-password"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 transition-colors hover:text-slate-700 dark:hover:text-slate-300"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {password.length > 0 && (
                <div className="mt-2 grid grid-cols-2 gap-1">
                  {[
                    { label: '8+ characters', met: password.length >= 8 },
                    { label: 'Uppercase letter', met: /[A-Z]/.test(password) },
                    { label: 'Lowercase letter', met: /[a-z]/.test(password) },
                    { label: 'Number', met: /\d/.test(password) },
                    { label: 'Special character', met: /[!@#$%^&*(),.?":{}|<>]/.test(password) },
                  ].map(({ label, met }) => (
                    <span key={label} className={`flex items-center gap-1 text-[11px] ${met ? 'text-emerald-600 dark:text-green-400' : 'text-slate-500 dark:text-slate-400'}`}>
                      <span className={`inline-block h-1 w-1 rounded-full ${met ? 'bg-emerald-500 dark:bg-green-400' : 'bg-slate-400 dark:bg-slate-600'}`} />
                      {label}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="mb-6">
              <label className="mb-1.5 block text-xs font-medium text-slate-700 dark:text-slate-400">Confirm Password</label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Re-enter password…"
                  data-testid="confirm-password"
                  className={`${inputClass} pr-10`}
                  autoComplete="new-password"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 transition-colors hover:text-slate-700 dark:hover:text-slate-300"
                  aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                >
                  {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              data-testid="accept-submit"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-wedding-rose to-[#c48e8e] py-3 text-sm font-semibold text-slate-950 transition-all hover:shadow-lg hover:shadow-wedding-rose/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating Account…
                </>
              ) : (
                'Join Team'
              )}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-slate-600 dark:text-slate-400">
          Already have an account?{' '}
          <button
            onClick={() => router.push('/admin/login')}
            className="text-wedding-rose hover:underline"
          >
            Sign in
          </button>
        </p>
      </div>
    </div>
  );
}
