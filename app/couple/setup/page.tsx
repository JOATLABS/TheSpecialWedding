'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import { Heart, Lock, Loader2, CheckCircle, XCircle, ArrowRight } from 'lucide-react';

export default function CoupleSetupPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token');

  const [verifying, setVerifying] = useState(true);
  const [valid, setValid] = useState(false);
  const [inviteData, setInviteData] = useState<{ email: string; partner1_name: string; partner2_name?: string } | null>(null);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

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
      } catch (err) {
        // Invalid token
      } finally {
        setVerifying(false);
      }
    };

    verify();
  }, [token]);

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault();

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
      const res = await fetch(`${getApiBaseUrl()}/couple/setup-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        toast.error(data.detail || 'Setup failed');
        return;
      }

      localStorage.setItem('couple_token', data.access_token);
      localStorage.setItem('couple_data', JSON.stringify(data.couple));
      toast.success('Account setup complete! Welcome!');
      router.push('/couple/dashboard');
    } catch (err) {
      toast.error('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (verifying) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-[#1e3a5f] mx-auto mb-4" />
          <p className="text-gray-500">Verifying your invitation...</p>
        </div>
      </div>
    );
  }

  if (!token || !valid) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-red-50 rounded-full mb-4">
            <XCircle className="w-8 h-8 text-red-500" />
          </div>
          <h1 className="text-2xl font-serif text-gray-800 mb-2">Invalid or Expired Link</h1>
          <p className="text-gray-500 mb-6">
            This invitation link is no longer valid. Please ask your wedding planner to send a new invitation.
          </p>
          <a href="/couple/login" className="text-[#1e3a5f] font-medium hover:underline">
            Already have an account? Sign in
          </a>
        </div>
      </div>
    );
  }

  const coupleName = inviteData?.partner2_name
    ? `${inviteData.partner1_name} & ${inviteData.partner2_name}`
    : inviteData?.partner1_name;

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-[#1e3a5f] rounded-full mb-4">
            <Heart className="w-8 h-8 text-[#d4af37]" />
          </div>
          <h1 className="text-3xl font-serif text-[#1e3a5f] mb-2">Welcome, {coupleName}!</h1>
          <p className="text-gray-500">Set up your wedding portal account</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8">
          <div className="flex items-center gap-3 bg-green-50 text-green-700 p-3 rounded-xl mb-6">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm">Invitation verified for <strong>{inviteData?.email}</strong></p>
          </div>

          <form onSubmit={handleSetup} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Create Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
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
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  required
                  minLength={8}
                  className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] transition-all text-gray-800"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#1e3a5f] text-white py-3 rounded-xl font-medium hover:bg-[#2a4a6f] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
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
      </div>
    </div>
  );
}
