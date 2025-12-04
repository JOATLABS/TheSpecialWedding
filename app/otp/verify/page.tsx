// app/otp/verify/page.tsx

'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import RSVPForm from '@/components/RSVPForm';

export default function VerifyOTPPage() {
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isVerified, setIsVerified] = useState(false);
  const [guestData, setGuestData] = useState(null);
  const [resendCooldown, setResendCooldown] = useState(60);
  const router = useRouter();
  const searchParams = useSearchParams();
  const guest_id = searchParams.get('guest_id');
  const token = searchParams.get('token');

  useEffect(() => {
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleVerifyOTP = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/otp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guest_id, otp }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to verify OTP');
      }

      // Fetch guest data after successful verification
      const guestRes = await fetch(`/api/guest/invite/${token}`);
      if (!guestRes.ok) {
        throw new Error('Failed to fetch guest data');
      }
      const guest = await guestRes.json();
      setGuestData(guest);
      setIsVerified(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOTP = async () => {
    setLoading(true);
    setError('');
    setResendCooldown(60);

    try {
      const response = await fetch('/api/otp/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guest_id }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to resend OTP');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (isVerified && guestData) {
    return <RSVPForm guest={guestData} token={token} />;
  }

  return (
    <div className="min-h-screen bg-wedding-ivory flex items-center justify-center">
      <div className="max-w-md w-full bg-white p-8 rounded-lg shadow-lg">
        <h2 className="text-2xl font-bold text-wedding-navy text-center mb-6">Enter Verification Code</h2>
        <p className="text-center text-gray-600 mb-6">
          A 6-digit code was sent to your phone.
        </p>
        <div className="flex flex-col gap-4">
          <input
            type="text"
            value={otp}
            onChange={(e) => setOtp(e.target.value)}
            maxLength={6}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg text-center tracking-[0.5em]"
            placeholder="______"
          />
          <button
            onClick={handleVerifyOTP}
            disabled={loading || otp.length !== 6}
            className="w-full bg-wedding-rose text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Verifying...' : 'Verify'}
          </button>
          {error && <p className="text-red-500 text-center mt-4">{error}</p>}
          <div className="text-center mt-4">
            <button
              onClick={handleResendOTP}
              disabled={loading || resendCooldown > 0}
              className="text-sm text-wedding-rose hover:underline disabled:opacity-50"
            >
              {resendCooldown > 0 ? `Resend OTP in ${resendCooldown}s` : 'Resend OTP'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
