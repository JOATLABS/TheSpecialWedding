// app/otp/verify/page.tsx

'use client';

import { useState, useEffect, Suspense, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import RSVPForm from '@/components/RSVPForm';
import AlreadyRSVPedScreen from '@/components/AlreadyRSVPedScreen';
import { WeddingContext } from '@/contexts/WeddingContext';

// Get API base URL - strip /admin suffix for public endpoints
// NEXT_PUBLIC_API_BASE_URL typically ends with /admin for admin panel use
const getApiBase = (): string => {
  const url = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!url) {
    console.warn('NEXT_PUBLIC_API_BASE_URL not set, using relative URLs');
    return '';
  }
  return url.replace('/admin', '');
};

const apiBase = getApiBase();

function VerifyOTPContent() {
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isVerified, setIsVerified] = useState(false);
  const [otpVerified, setOtpVerified] = useState(false); // Track OTP verification separately
  const [guestData, setGuestData] = useState(null);
  const [weddingData, setWeddingData] = useState<any>(null);
  const [rsvpData, setRsvpData] = useState<any>(null); // Existing RSVP data if already submitted
  const [editMode, setEditMode] = useState(false); // Allow editing existing RSVP
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
      const data = await accessRes.json();
      const { wedding, guest, rsvp } = data;

      // Validate response data
      if (!wedding) {
        console.error('Wedding data missing from response:', data);
        throw new Error('Wedding data not found. Please try again.');
      }
      if (!guest) {
        console.error('Guest data missing from response:', data);
        throw new Error('Guest data not found. Please try again.');
      }

      // Map _id to id for WeddingContext compatibility
      // MongoDB returns _id, but frontend expects id
      const weddingForContext = {
        ...wedding,
        id: wedding.id || wedding._id || slug,
        // Ensure slug is present
        slug: wedding.slug || slug,
      };

      console.log('Wedding data loaded successfully:', {
        weddingId: weddingForContext.id,
        guestId: guest.id,
        hasEvents: !!wedding.events?.length,
        hasExistingRsvp: !!rsvp?.has_rsvp
      });

      setWeddingData(weddingForContext);
      setGuestData(guest);
      setRsvpData(rsvp);
      setIsVerified(true);
    } catch (err) {
      console.error('fetchWeddingData error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load RSVP form');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    // Prevent double-submit
    if (isSubmittingRef.current) {
      console.log('OTP verification already in progress, ignoring duplicate click');
      return;
    }
    isSubmittingRef.current = true;
    setLoading(true);
    setError('');

    try {
      if (!token) {
        throw new Error('Missing RSVP token');
      }
      if (!guest_id) {
        throw new Error('Missing guest ID');
      }
      if (!slug) {
        throw new Error('Missing wedding slug');
      }

      console.log('Verifying OTP for guest:', guest_id);
      const response = await fetch(`${apiBase}/otp/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guest_id, otp }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        console.error('OTP verification failed:', errorData);
        throw new Error(errorData.detail || 'Failed to verify OTP');
      }

      console.log('OTP verified successfully, fetching wedding data...');
      // OTP verified successfully - mark this so user doesn't need to re-enter
      setOtpVerified(true);

      // Now fetch wedding + guest data
      await fetchWeddingData();
    } catch (err) {
      console.error('handleVerifyOTP error:', err);
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
    // Check if guest has already RSVPed and not in edit mode
    const showAlreadyRsvped = rsvpData?.has_rsvp && !editMode;

    return (
      <WeddingContext.Provider value={weddingData}>
        <div className="min-h-screen bg-slate-950 relative overflow-hidden">
          {/* Background effects matching landing page */}
          <div
            className="absolute inset-0 opacity-60"
            style={{
              background:
                "radial-gradient(900px 600px at 15% -10%, rgba(212,165,165,0.35), transparent 70%), radial-gradient(1200px 700px at 90% 110%, rgba(232,196,106,0.25), transparent 65%)",
            }}
          />
          <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'160\' height=\'160\' viewBox=\'0 0 40 40\'%3E%3Cg fill=%27none%27 stroke=%27rgba(255,255,255,0.04)%27 stroke-width=%270.5%27%3E%3Cpath d=%27M0 0h40v40H0z%27/%3E%3Cpath d=%27M0 20h40M20 0v40%27/%3E%3C/g%3E%3C/svg%3E')] opacity-40" />
          <div className="relative max-w-2xl mx-auto px-4 py-8 sm:py-12">
            {showAlreadyRsvped ? (
              <AlreadyRSVPedScreen
                guest={guestData}
                rsvp={rsvpData}
                onEditClick={() => setEditMode(true)}
                onViewWeddingPage={() => { window.location.href = `/${slug}`; }}
              />
            ) : (
              <RSVPForm
                guest={guestData}
                token={token}
                onViewWeddingPage={() => { window.location.href = `/${slug}`; }}
              />
            )}
          </div>
        </div>
      </WeddingContext.Provider>
    );
  }

  // OTP verified but wedding data fetch failed - show retry option
  if (otpVerified && !isVerified) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(900px 600px at 50% 0%, rgba(212,165,165,0.35), transparent 70%)",
          }}
        />
        <div className="relative max-w-md w-full mx-4">
          <div className="rounded-[2.5rem] border border-white/10 bg-white/5 backdrop-blur-xl p-8">
            <div className="w-16 h-16 bg-wedding-rose/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-wedding-rose" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-semibold text-white text-center mb-4">Identity Verified</h2>
            <p className="text-center text-slate-300 mb-6">
              Your identity has been verified. Click below to load your RSVP form.
            </p>
            <div className="flex flex-col gap-4">
              <button
                onClick={fetchWeddingData}
                disabled={loading}
                className="w-full bg-wedding-rose text-slate-900 py-3 px-6 rounded-full font-semibold shadow-lg shadow-wedding-rose/40 hover:bg-wedding-blush disabled:opacity-50 transition-all"
              >
                {loading ? 'Loading...' : 'Load RSVP Form'}
              </button>
              {error && <p className="text-wedding-rose text-center mt-4">{error}</p>}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center relative overflow-hidden">
      <div
        className="absolute inset-0 opacity-60"
        style={{
          background:
            "radial-gradient(900px 600px at 50% 0%, rgba(212,165,165,0.35), transparent 70%)",
        }}
      />
      <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'160\' height=\'160\' viewBox=\'0 0 40 40\'%3E%3Cg fill=%27none%27 stroke=%27rgba(255,255,255,0.04)%27 stroke-width=%270.5%27%3E%3Cpath d=%27M0 0h40v40H0z%27/%3E%3Cpath d=%27M0 20h40M20 0v40%27/%3E%3C/g%3E%3C/svg%3E')] opacity-40" />
      <div className="relative max-w-md w-full mx-4">
        <div className="rounded-[2.5rem] border border-white/10 bg-white/5 backdrop-blur-xl p-8">
          <div className="flex items-center justify-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-1.5 text-xs uppercase tracking-[0.3em] backdrop-blur mb-6 mx-auto w-fit">
            Verify Identity
          </div>
          <h2 className="text-2xl font-semibold text-white text-center mb-4">Enter Verification Code</h2>
          <p className="text-center text-slate-300 mb-6">
            A 6-digit code was sent to your phone.
          </p>
          <div className="flex flex-col gap-4">
            <input
              type="text"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              maxLength={6}
              className="w-full px-4 py-4 border border-white/10 bg-white/5 rounded-xl text-center tracking-[0.5em] text-white text-xl placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 backdrop-blur"
              placeholder="------"
            />
            <button
              onClick={handleVerifyOTP}
              disabled={loading || otp.length !== 6}
              className="w-full bg-wedding-rose text-slate-900 py-3 px-6 rounded-full font-semibold shadow-lg shadow-wedding-rose/40 hover:bg-wedding-blush disabled:opacity-50 transition-all"
            >
              {loading ? 'Verifying...' : 'Verify'}
            </button>
            {error && <p className="text-wedding-rose text-center mt-4">{error}</p>}
            <div className="text-center mt-4">
              <button
                onClick={handleResendOTP}
                disabled={loading || resendCooldown > 0}
                className="text-sm text-wedding-rose hover:text-wedding-blush disabled:opacity-50 transition-colors"
              >
                {resendCooldown > 0 ? `Resend OTP in ${resendCooldown}s` : 'Resend OTP'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function VerifyOTPPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-950 flex items-center justify-center relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(900px 600px at 50% 0%, rgba(212,165,165,0.35), transparent 70%)",
          }}
        />
        <div className="relative max-w-md w-full mx-4">
          <div className="rounded-[2.5rem] border border-white/10 bg-white/5 backdrop-blur-xl p-8">
            <div className="text-center">
              <div className="inline-block h-10 w-10 animate-spin rounded-full border-4 border-solid border-wedding-rose border-r-transparent"></div>
              <p className="mt-4 text-slate-300">Loading...</p>
            </div>
          </div>
        </div>
      </div>
    }>
      <VerifyOTPContent />
    </Suspense>
  );
}
