// app/otp/verify/page.tsx

'use client';

import { useState, useEffect, Suspense, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import RSVPForm from '@/components/RSVPForm';
import { WeddingContext } from '@/contexts/WeddingContext';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || '';

function VerifyOTPContent() {
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isVerified, setIsVerified] = useState(false);
  const [otpVerified, setOtpVerified] = useState(false); // Track OTP verification separately
  const [guestData, setGuestData] = useState(null);
  const [weddingData, setWeddingData] = useState<any>(null);
  const [resendCooldown, setResendCooldown] = useState(65);
  const isSubmittingRef = useRef(false);
  const searchParams = useSearchParams();
  const guest_id = searchParams.get('guest_id');
  const token = searchParams.get('token') ?? '';
  const slug = searchParams.get('slug') ?? '';

  useEffect(() => {
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch wedding and guest data after OTP verification
  const fetchWeddingData = async () => {
    setLoading(true);
    setError('');

    try {
      const accessRes = await fetch(`${apiBase}/weddings/guest-access/${slug}/${token}`);
      if (!accessRes.ok) {
        const errorData = await accessRes.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to load RSVP form. Please try again.');
      }
      const { wedding, guest } = await accessRes.json();

      // Map _id to id for WeddingContext compatibility
      const weddingForContext = {
        ...wedding,
        id: wedding.id || wedding._id || slug,
      };

      setWeddingData(weddingForContext);
      setGuestData(guest);
      setIsVerified(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load RSVP form');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    // Prevent double-submit
    if (isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    setLoading(true);
    setError('');

    try {
      if (!token) {
        throw new Error('Missing RSVP token');
      }

      const response = await fetch(`${apiBase}/otp/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guest_id, otp }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to verify OTP');
      }

      // OTP verified successfully - mark this so user doesn't need to re-enter
      setOtpVerified(true);

      // Now fetch wedding + guest data
      await fetchWeddingData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setLoading(false);
      isSubmittingRef.current = false;
    }
  };

  const handleResendOTP = async () => {
    setLoading(true);
    setError('');
    setResendCooldown(65);

    try {
      const response = await fetch(`${apiBase}/otp/request`, {
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

  if (isVerified && guestData && weddingData) {
    return (
      <WeddingContext.Provider value={weddingData}>
        <RSVPForm guest={guestData} token={token} />
      </WeddingContext.Provider>
    );
  }

  // OTP verified but wedding data fetch failed - show retry option
  if (otpVerified && !isVerified) {
    return (
      <div className="min-h-screen bg-wedding-ivory flex items-center justify-center">
        <div className="max-w-md w-full bg-white p-8 rounded-lg shadow-lg">
          <h2 className="text-2xl font-bold text-wedding-navy text-center mb-6">Identity Verified!</h2>
          <p className="text-center text-gray-600 mb-6">
            Your identity has been verified. Click below to load your RSVP form.
          </p>
          <div className="flex flex-col gap-4">
            <button
              onClick={fetchWeddingData}
              disabled={loading}
              className="w-full bg-wedding-rose text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Load RSVP Form'}
            </button>
            {error && <p className="text-red-500 text-center mt-4">{error}</p>}
          </div>
        </div>
      </div>
    );
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

export default function VerifyOTPPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-wedding-ivory flex items-center justify-center">
        <div className="max-w-md w-full bg-white p-8 rounded-lg shadow-lg">
          <div className="text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-wedding-rose border-r-transparent"></div>
            <p className="mt-4 text-gray-600">Loading...</p>
          </div>
        </div>
      </div>
    }>
      <VerifyOTPContent />
    </Suspense>
  );
}
