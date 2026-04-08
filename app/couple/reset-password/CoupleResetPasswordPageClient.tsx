'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Heart, Lock, Loader2, ArrowLeft, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

import { clearLegacyCoupleStorage, extractApiErrorMessage } from '@/couple/lib/auth';
import { getApiBaseUrl } from '@/utils/env';

function getResetErrorHeading(message: string | null): string {
  const normalized = message?.toLowerCase() ?? '';
  if (normalized.includes('inactive') || normalized.includes('unavailable') || normalized.includes('revoked')) {
    return 'Portal Unavailable';
  }
  return 'Invalid or Expired Link';
}

export default function CoupleResetPasswordPageClient({ initialToken }: { initialToken: string | null }) {
  const token = initialToken ?? '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [maskedEmail, setMaskedEmail] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setValidating(false);
      return;
    }

    const validate = async () => {
      try {
        const res = await fetch(`${getApiBaseUrl()}/couple/reset-password/validate/${token}`);
        if (res.ok) {
          const data = await res.json();
          setTokenValid(true);
          setMaskedEmail(data.email || '');
          setValidationError(null);
          return;
        }

        setValidationError(
          await extractApiErrorMessage(
            res,
            'This password reset link is invalid or has expired. Please request a new one.',
          ),
        );
      } catch {
        setValidationError(
          'We could not validate this reset link right now. Please try again or request a new one.',
        );
      } finally {
        setValidating(false);
      }
    };

    void validate();
  }, [token]);

  const handleReset = async (event: React.FormEvent) => {
    event.preventDefault();

    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
        credentials: 'include',
      });

      if (res.ok) {
        clearLegacyCoupleStorage();
        toast.success('Password reset successfully!');
        window.location.assign('/couple/dashboard');
      } else {
        const detail = await extractApiErrorMessage(res, 'Failed to reset password');
        setValidationError(detail);
        toast.error(detail);
      }
    } catch {
      toast.error('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  };

  if (validating) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-[#1e3a5f] mx-auto mb-4" />
          <p className="text-gray-500">Validating reset link...</p>
        </div>
      </div>
    );
  }

  if (!token || !tokenValid) {
    const errorHeading = getResetErrorHeading(validationError);
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-[#1e3a5f] rounded-full mb-4">
              <Heart className="w-8 h-8 text-[#d4af37]" />
            </div>
          </div>
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 text-center">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-800 mb-2">{errorHeading}</h2>
            <p className="text-sm text-gray-500 mb-6">
              {validationError || 'This password reset link is invalid or has expired. Please request a new one.'}
            </p>
            <Link
              href="/couple/forgot-password"
              className="inline-block bg-[#1e3a5f] text-white px-6 py-3 rounded-xl font-medium hover:bg-[#2a4a6f] transition-all"
            >
              Request New Link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-[#1e3a5f] rounded-full mb-4">
            <Heart className="w-8 h-8 text-[#d4af37]" />
          </div>
          <h1 className="text-3xl font-serif text-[#1e3a5f] mb-2">New Password</h1>
          <p className="text-gray-500 text-sm tracking-widest uppercase">The Special Wedding</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Set New Password</h2>
          {maskedEmail && (
            <p className="text-sm text-gray-500 mb-6">
              Resetting password for <span className="font-medium text-gray-700">{maskedEmail}</span>
            </p>
          )}

          <form onSubmit={handleReset} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">New Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 8 characters"
                  required
                  minLength={8}
                  className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] transition-all text-gray-800"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Confirm your password"
                  required
                  minLength={8}
                  className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] transition-all text-gray-800"
                />
              </div>
              {confirmPassword && password !== confirmPassword && (
                <p className="text-xs text-red-500 mt-1">Passwords do not match</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || password !== confirmPassword || password.length < 8}
              className="w-full bg-[#1e3a5f] text-white py-3 rounded-xl font-medium hover:bg-[#2a4a6f] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Reset Password'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link
              href="/couple/login"
              className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-[#1e3a5f] transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
