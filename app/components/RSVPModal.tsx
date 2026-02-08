// components/RSVPModal.tsx

'use client';

import { Fragment, useState, useEffect, useRef } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import RSVPForm from '@/components/RSVPForm';
import AlreadyRSVPedScreen from '@/components/AlreadyRSVPedScreen';
import { WeddingContext } from '@/contexts/WeddingContext';

type ModalStep = 'loading' | 'otp_request' | 'otp_verify' | 'rsvp_form' | 'already_rsvped' | 'success';

interface RSVPModalProps {
  isOpen: boolean;
  token: string;
  slug: string;
  onClose: () => void;
}

export default function RSVPModal({ isOpen, token, slug, onClose }: RSVPModalProps) {
  const [step, setStep] = useState<ModalStep>('loading');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [guestData, setGuestData] = useState<any>(null);
  const [weddingData, setWeddingData] = useState<any>(null);
  const [rsvpData, setRsvpData] = useState<any>(null);
  const [guestId, setGuestId] = useState('');
  const [otp, setOtp] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);
  const [editMode, setEditMode] = useState(false);
  const isSubmittingRef = useRef(false);

  const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || '').replace('/admin', '');

  // Cooldown timer for OTP resend
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  // Fetch guest + wedding data when modal opens
  useEffect(() => {
    if (isOpen && !weddingData) {
      fetchInitialData();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const fetchInitialData = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/weddings/guest-access/${slug}/${token}`);
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Unable to load your invitation. Please check the link and try again.');
      }
      const data = await res.json();
      const { wedding, guest, rsvp } = data;

      if (!wedding || !guest) {
        throw new Error('Invitation data not found. Please check the link and try again.');
      }

      // Map _id to id for WeddingContext compatibility
      const weddingForContext = {
        ...wedding,
        id: wedding.id || wedding._id || slug,
        slug: wedding.slug || slug,
      };

      setWeddingData(weddingForContext);
      setGuestData(guest);
      setRsvpData(rsvp);
      setGuestId(guest.id || guest._id);
      setStep('otp_request');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load invitation');
      setStep('loading');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestOTP = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${apiBase}/otp/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guest_id: guestId }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to send verification code');
      }

      setResendCooldown(65);
      setStep('otp_verify');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${apiBase}/otp/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guest_id: guestId, otp }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Invalid verification code');
      }

      // Re-fetch to get latest guest data (in case planner updated it)
      let latestRsvp = rsvpData;
      const accessRes = await fetch(`${apiBase}/weddings/guest-access/${slug}/${token}`);
      if (accessRes.ok) {
        const data = await accessRes.json();
        if (data.guest) {
          setGuestData(data.guest);
          setGuestId(data.guest.id || data.guest._id);
        }
        if (data.wedding) {
          const weddingForContext = {
            ...data.wedding,
            id: data.wedding.id || data.wedding._id || slug,
            slug: data.wedding.slug || slug,
          };
          setWeddingData(weddingForContext);
        }
        // Always update rsvpData (even if null) to avoid stale state
        latestRsvp = data.rsvp || null;
        setRsvpData(latestRsvp);
      }

      // Determine next step using freshly fetched data (not stale state)
      if (latestRsvp?.has_rsvp && !editMode) {
        setStep('already_rsvped');
      } else {
        setStep('rsvp_form');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
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
        body: JSON.stringify({ guest_id: guestId }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to resend code');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend code');
    } finally {
      setLoading(false);
    }
  };

  const handleRSVPSuccess = () => {
    setStep('success');
  };

  const handleEditRSVP = () => {
    setEditMode(true);
    setStep('rsvp_form');
  };

  // Modal can only be dismissed after success or when viewing already-RSVPed state
  const canDismiss = step === 'success' || (step === 'already_rsvped' && !editMode);

  const renderStep = () => {
    switch (step) {
      case 'loading':
        return (
          <div className="text-center py-12">
            {loading ? (
              <>
                <div className="inline-block h-10 w-10 animate-spin rounded-full border-4 border-solid border-wedding-rose border-r-transparent mb-4" />
                <p className="text-slate-300">Loading your invitation...</p>
              </>
            ) : error ? (
              <>
                <div className="w-16 h-16 bg-wedding-rose/20 rounded-full flex items-center justify-center mx-auto mb-6">
                  <svg className="w-8 h-8 text-wedding-rose" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                <p className="text-wedding-rose mb-4">{error}</p>
                <button
                  onClick={fetchInitialData}
                  className="px-6 py-3 bg-wedding-rose text-slate-900 font-semibold rounded-full shadow-lg hover:bg-wedding-blush transition-all"
                >
                  Try Again
                </button>
              </>
            ) : null}
          </div>
        );

      case 'otp_request':
        return (
          <div className="text-center py-6">
            <div className="w-20 h-20 bg-wedding-rose/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-wedding-rose" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-1.5 text-xs uppercase tracking-[0.3em] backdrop-blur mb-4">
              Verify Identity
            </div>
            <h2 className="text-2xl font-semibold text-white mb-3">
              Welcome, {guestData?.name}
            </h2>
            <p className="text-slate-300 mb-2">
              You&apos;re invited to <span className="text-wedding-rose font-semibold">{weddingData?.couple_names}&apos;s</span> wedding!
            </p>
            <p className="text-sm text-slate-400 mb-8">
              To protect your privacy, we&apos;ll send a verification code to your phone before you can RSVP.
            </p>

            {error && (
              <div className="rounded-2xl border border-wedding-rose/40 bg-wedding-rose/10 p-4 mb-6">
                <p className="text-sm text-wedding-rose">{error}</p>
              </div>
            )}

            <button
              onClick={handleRequestOTP}
              disabled={loading}
              className="w-full py-4 bg-wedding-rose text-slate-900 font-semibold rounded-full shadow-lg shadow-wedding-rose/40 hover:bg-wedding-blush disabled:opacity-50 transition-all"
            >
              {loading ? 'Sending...' : 'Send Verification Code'}
            </button>
          </div>
        );

      case 'otp_verify':
        return (
          <div className="py-6">
            <div className="flex items-center justify-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-1.5 text-xs uppercase tracking-[0.3em] backdrop-blur mb-6 mx-auto w-fit">
              Verify Identity
            </div>
            <h2 className="text-2xl font-semibold text-white text-center mb-4">Enter Verification Code</h2>
            <p className="text-center text-slate-300 mb-6">
              A 6-digit code was sent to your phone. Enter it below to continue.
            </p>
            <div className="flex flex-col gap-4">
              <input
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
                className="w-full px-4 py-4 border border-white/10 bg-white/5 rounded-xl text-center tracking-[0.5em] text-white text-xl placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 backdrop-blur"
                placeholder="------"
                autoFocus
              />
              <button
                onClick={handleVerifyOTP}
                disabled={loading || otp.length !== 6}
                className="w-full bg-wedding-rose text-slate-900 py-4 px-6 rounded-full font-semibold shadow-lg shadow-wedding-rose/40 hover:bg-wedding-blush disabled:opacity-50 transition-all"
              >
                {loading ? 'Verifying...' : 'Verify & Continue'}
              </button>
              {error && <p className="text-wedding-rose text-center text-sm">{error}</p>}
              <div className="text-center mt-2">
                <button
                  onClick={handleResendOTP}
                  disabled={loading || resendCooldown > 0}
                  className="text-sm text-wedding-rose hover:text-wedding-blush disabled:opacity-50 transition-colors"
                >
                  {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend Code'}
                </button>
              </div>
            </div>
          </div>
        );

      case 'rsvp_form':
        return (
          <RSVPForm
            guest={guestData}
            token={token}
            onSuccess={handleRSVPSuccess}
            onViewWeddingPage={onClose}
          />
        );

      case 'already_rsvped':
        return (
          <AlreadyRSVPedScreen
            guest={guestData}
            rsvp={rsvpData}
            onEditClick={handleEditRSVP}
            onViewWeddingPage={onClose}
          />
        );

      case 'success':
        // Handled by RSVPForm's internal submitted state (which includes onViewWeddingPage button)
        return null;

      default:
        return null;
    }
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-50"
        onClose={() => { if (canDismiss) onClose(); }}
      >
        {/* Backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-2xl rounded-[2rem] border border-white/10 bg-slate-950 shadow-2xl overflow-hidden">
                {/* Dark themed background effects */}
                <div className="relative">
                  <div
                    className="absolute inset-0 opacity-60"
                    style={{
                      background:
                        'radial-gradient(900px 600px at 15% -10%, rgba(212,165,165,0.35), transparent 70%), radial-gradient(1200px 700px at 90% 110%, rgba(232,196,106,0.25), transparent 65%)',
                    }}
                  />
                  <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27160%27 height=%27160%27 viewBox=%270 0 40 40%27%3E%3Cg fill=%27none%27 stroke=%27rgba(255,255,255,0.04)%27 stroke-width=%270.5%27%3E%3Cpath d=%27M0 0h40v40H0z%27/%3E%3Cpath d=%27M0 20h40M20 0v40%27/%3E%3C/g%3E%3C/svg%3E')] opacity-40" />

                  <div className="relative max-h-[85vh] overflow-y-auto p-6 sm:p-8">
                    {weddingData ? (
                      <WeddingContext.Provider value={weddingData}>
                        {renderStep()}
                      </WeddingContext.Provider>
                    ) : (
                      renderStep()
                    )}
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
