'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Heart, Lock, Loader2, CheckCircle, XCircle, ArrowRight, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';

import { GlassCard } from '@/components/ui/GlassCard';
import { clearLegacyCoupleStorage } from '@/couple/lib/auth';
import { getApiBaseUrl } from '@/utils/env';

interface PasswordValidation {
  minLength: boolean;
  hasUppercase: boolean;
  hasLowercase: boolean;
  hasNumber: boolean;
}

const validatePassword = (password: string): PasswordValidation => ({
  minLength: password.length >= 8,
  hasUppercase: /[A-Z]/.test(password),
  hasLowercase: /[a-z]/.test(password),
  hasNumber: /\d/.test(password),
});

const isPasswordValid = (validation: PasswordValidation): boolean =>
  validation.minLength && validation.hasUppercase && validation.hasLowercase && validation.hasNumber;

export default function CoupleSetupPageClient({ initialToken }: { initialToken: string | null }) {
  const router = useRouter();
  const token = initialToken;

  const [verifying, setVerifying] = useState(true);
  const [valid, setValid] = useState(false);
  const [inviteData, setInviteData] = useState<{
    email: string;
    partner1_name: string;
    partner2_name?: string;
  } | null>(null);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);

  const validation = validatePassword(password);

  useEffect(() => {
    if (!token) {
      setVerifying(false);
      return;
    }

    const verify = async () => {
      try {
        const res = await fetch(`${getApiBaseUrl()}/couple/verify-invite/${token}`);
        const data = await res.json();
        if (res.ok && data.valid) {
          setValid(true);
          setInviteData(data);
        }
      } catch {
        // Invalid token
      } finally {
        setVerifying(false);
      }
    };

    void verify();
  }, [token]);

  const handleSetup = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!isPasswordValid(validation)) {
      toast.error('Please meet all password requirements');
      return;
    }

    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/setup-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
        credentials: 'include',
      });

      const data = await res.json();

      if (!res.ok) {
        toast.error(data.detail || 'Setup failed');
        return;
      }

      clearLegacyCoupleStorage();
      toast.success('Account setup complete! Welcome!');
      router.push('/couple/dashboard');
    } catch {
      toast.error('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (verifying) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-primary-500 mx-auto mb-4" />
          <p className="text-slate-500 dark:text-slate-400">Verifying your invitation...</p>
        </div>
      </div>
    );
  }

  if (!token || !valid) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-red-50 dark:bg-red-900/20 rounded-full mb-4">
            <XCircle className="w-8 h-8 text-red-500" />
          </div>
          <h1 className="text-2xl font-heading font-semibold text-slate-900 dark:text-white mb-2">
            Invalid or Expired Link
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mb-6">
            This invitation link is no longer valid. Please ask your wedding planner to send a new invitation.
          </p>
          <a
            href="/couple/login"
            className="text-primary-600 dark:text-primary-400 font-medium hover:underline"
          >
            Already have an account? Sign in
          </a>
        </div>
      </div>
    );
  }

  const coupleName = inviteData?.partner2_name
    ? `${inviteData.partner1_name} & ${inviteData.partner2_name}`
    : inviteData?.partner1_name;

  const reqItems: { label: string; met: boolean }[] = [
    { label: 'At least 8 characters', met: validation.minLength },
    { label: 'One uppercase letter', met: validation.hasUppercase },
    { label: 'One lowercase letter', met: validation.hasLowercase },
    { label: 'One number', met: validation.hasNumber },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 dark:bg-primary-500 rounded-full mb-4">
            <Heart className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-heading font-semibold text-slate-900 dark:text-white mb-2">
            Welcome, {coupleName}!
          </h1>
          <p className="text-slate-500 dark:text-slate-400">Set up your wedding portal account</p>
        </div>

        <GlassCard depth="near" blur="xl">
          <div className="px-6 py-7 sm:px-8">
            <div className="flex items-center gap-3 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 p-3 rounded-xl mb-6">
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
              <p className="text-sm">
                Invitation verified for <strong>{inviteData?.email}</strong>
              </p>
            </div>

            <form onSubmit={handleSetup} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                  Create Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="At least 8 characters"
                    required
                    minLength={8}
                    className="w-full rounded-xl border border-white/40 dark:border-slate-600 bg-white/60 dark:bg-slate-800/60 px-4 py-3 pr-12 text-base text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 flex items-center rounded-r-xl px-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              {password.length > 0 && (
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {reqItems.map((requirement) => (
                    <div key={requirement.label} className="flex items-center gap-2">
                      {requirement.met ? (
                        <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600 flex-shrink-0" />
                      )}
                      <span
                        className={`text-xs ${requirement.met ? 'text-green-600 dark:text-green-400' : 'text-slate-400 dark:text-slate-500'}`}
                      >
                        {requirement.label}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    placeholder="Confirm your password"
                    required
                    minLength={8}
                    className="w-full rounded-xl border border-white/40 dark:border-slate-600 bg-white/60 dark:bg-slate-800/60 px-4 py-3 pr-12 text-base text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute inset-y-0 right-0 flex items-center rounded-r-xl px-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                  >
                    {showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {confirmPassword.length > 0 && password !== confirmPassword && (
                  <p className="mt-1.5 text-xs text-red-500">Passwords do not match</p>
                )}
              </div>

              <button
                type="submit"
                disabled={loading || !isPasswordValid(validation) || password !== confirmPassword}
                className="w-full bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-xl font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    Set Up My Account
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
