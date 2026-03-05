'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { toast, Toaster } from 'sonner';
import { Loader2, Eye, EyeOff, Shield, CheckCircle2, AlertCircle } from 'lucide-react';
import NextImage from 'next/image';

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
};

export default function AcceptInvitePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token');

  const [inviteInfo, setInviteInfo] = useState<InviteInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
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

    fetchInviteInfo();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!firstName.trim() || !lastName.trim()) {
      toast.error('Please enter your first and last name.');
      return;
    }

    if (password.length < 8) {
      toast.error('Password must be at least 8 characters.');
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

      // Redirect to login after a short delay
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
    admin: 'bg-[rgba(212,165,165,0.15)] text-wedding-rose',
    editor: 'bg-[rgba(168,218,220,0.15)] text-wedding-sage',
    viewer: 'bg-slate-500/15 text-slate-400',
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-dark-bg to-slate-800 flex items-center justify-center">
        <Toaster position="top-right" richColors />
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-wedding-rose mx-auto" />
          <p className="mt-4 text-slate-400 text-sm">Loading invitation...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-dark-bg to-slate-800 flex items-center justify-center p-6">
        <Toaster position="top-right" richColors />
        <div className="w-full max-w-md text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 mb-6">
            <AlertCircle className="w-8 h-8 text-red-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-200 mb-2">Invitation Not Found</h2>
          <p className="text-slate-400 mb-6">{error}</p>
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

  // Success state
  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-dark-bg to-slate-800 flex items-center justify-center p-6">
        <Toaster position="top-right" richColors />
        <div className="w-full max-w-md text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-500/10 mb-6">
            <CheckCircle2 className="w-8 h-8 text-green-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-200 mb-2">Welcome to the team!</h2>
          <p className="text-slate-400 mb-2">Your account has been created successfully.</p>
          <p className="text-slate-500 text-sm">Redirecting you to login...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-bg to-slate-800 flex items-center justify-center p-6">
      <Toaster position="top-right" richColors />
      <div className="w-full max-w-[480px]">
        {/* Logo */}
        <div className="text-center mb-8">
          <NextImage
            src="/logo.svg"
            alt="The Special Wedding"
            width={180}
            height={45}
            className="h-10 w-auto mx-auto mb-3"
            priority
          />
          <p className="text-sm text-slate-500">You&apos;ve been invited to join a team</p>
        </div>

        {/* Card */}
        <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-8 backdrop-blur-xl">
          {/* Invite header */}
          <div className="text-center mb-6">
            <p className="text-slate-200 mb-2">
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
          </div>

          {/* Permissions display */}
          {enabledPermissions.length > 0 && (
            <div className="bg-slate-900/40 rounded-xl p-4 mb-6">
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2.5">Your permissions</p>
              <div className="flex flex-wrap gap-1.5">
                {enabledPermissions.map((perm) => (
                  <span
                    key={perm}
                    className="bg-wedding-sage/10 text-wedding-sage px-2.5 py-1 rounded-md text-xs font-medium"
                  >
                    {perm}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} data-testid="accept-form">
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">First Name</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="First name"
                  data-testid="first-name"
                  className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-3.5 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-wedding-rose focus:outline-none transition-colors"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Last Name</label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Last name"
                  data-testid="last-name"
                  className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-3.5 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-wedding-rose focus:outline-none transition-colors"
                  required
                />
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Create Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 8 characters"
                  data-testid="password-input"
                  className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-3.5 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-wedding-rose focus:outline-none transition-colors pr-10"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Confirm Password</label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  data-testid="confirm-password"
                  className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-3.5 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-wedding-rose focus:outline-none transition-colors pr-10"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              data-testid="accept-submit"
              className="w-full bg-gradient-to-r from-wedding-rose to-[#c48e8e] text-slate-900 font-semibold py-3 rounded-xl text-sm hover:shadow-lg hover:shadow-wedding-rose/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating Account...
                </>
              ) : (
                'Join Team'
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
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
