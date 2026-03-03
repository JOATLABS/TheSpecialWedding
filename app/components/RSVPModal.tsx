// components/RSVPModal.tsx

'use client';

import { Fragment, useState, useEffect, useRef } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import RSVPForm from '@/components/RSVPForm';
import AlreadyRSVPedScreen from '@/components/AlreadyRSVPedScreen';
import { WeddingContext } from '@/contexts/WeddingContext';

type ModalStep = 'loading' | 'otp_request' | 'otp_verify' | 'rsvp_form' | 'already_rsvped';

interface RSVPModalProps {
  isOpen: boolean;
  token: string;
  slug: string;
  onClose: () => void;
}

/* ─── color helpers ─── */
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace('#', '');
  const num = parseInt(h, 16);
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

function lightenColor(hex: string, amount: number): string {
  const { r, g, b } = hexToRgb(hex);
  const lr = Math.min(255, Math.floor(r + (255 - r) * amount));
  const lg = Math.min(255, Math.floor(g + (255 - g) * amount));
  const lb = Math.min(255, Math.floor(b + (255 - b) * amount));
  return `rgb(${lr}, ${lg}, ${lb})`;
}

export default function RSVPModal({ isOpen, token, slug, onClose }: RSVPModalProps) {
  const [step, setStep] = useState<ModalStep>('loading');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isTokenExpired, setIsTokenExpired] = useState(false);
  const [guestData, setGuestData] = useState<any>(null);
  const [weddingData, setWeddingData] = useState<any>(null);
  const [rsvpData, setRsvpData] = useState<any>(null);
  const [guestId, setGuestId] = useState('');
  const [otp, setOtp] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);
  const [editMode, setEditMode] = useState(false);
  const [formCompleted, setFormCompleted] = useState(false);
  const [otpContactType, setOtpContactType] = useState<'phone' | 'email' | ''>('');
  const isSubmittingRef = useRef(false);

  /* ─── theme colors (with safe fallbacks to original hardcoded values) ─── */
  const tc = weddingData?.theme_config;
  const accentColor = tc?.accent_color || '#D4A5A5';      // fallback = wedding-rose
  const secondaryColor = tc?.secondary_color || '#E9C46A'; // fallback = wedding-gold
  const aRgb = hexToRgb(accentColor);
  const sRgb = hexToRgb(secondaryColor);
  const blushColor = lightenColor(accentColor, 0.6);

  /** CSS custom properties cascaded to all child components */
  const themeVars = {
    '--rsvp-accent': accentColor,
    '--rsvp-accent-rgb': `${aRgb.r}, ${aRgb.g}, ${aRgb.b}`,
    '--rsvp-secondary': secondaryColor,
    '--rsvp-secondary-rgb': `${sRgb.r}, ${sRgb.g}, ${sRgb.b}`,
    '--rsvp-blush': blushColor,
  } as React.CSSProperties;

  // Reset all state when modal closes
  const handleClose = () => {
    setEditMode(false);
    setFormCompleted(false);
    setError('');
    setIsTokenExpired(false);
    setOtp('');
    setOtpContactType('');
    onClose();
  };

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
    setIsTokenExpired(false);
    try {
      const res = await fetch(`${apiBase}/weddings/guest-access/${slug}/${token}`);
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const errorMessage = errorData.detail || '';

        const isExpired = res.status === 401 || res.status === 404 ||
          errorMessage.toLowerCase().includes('expired') ||
          errorMessage.toLowerCase().includes('invalid') ||
          errorMessage.toLowerCase().includes('not found');

        if (isExpired) {
          setIsTokenExpired(true);
          throw new Error('Your invitation link has expired or is no longer valid. Please contact the couple for a new link.');
        }

        throw new Error(errorMessage || 'Unable to load your invitation. Please check the link and try again.');
      }
      const data = await res.json();
      const { wedding, guest, rsvp } = data;

      if (!wedding || !guest) {
        throw new Error('Invitation data not found. Please check the link and try again.');
      }

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

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to send verification code');
      }

      setOtpContactType(data.contact_type || 'phone');
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

      const verifyData = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(verifyData.detail || 'Invalid verification code');
      }

      if (verifyData.guest) {
        setGuestData(verifyData.guest);
        setGuestId(verifyData.guest.id || verifyData.guest._id);
      }

      let latestRsvp = rsvpData;
      const accessRes = await fetch(`${apiBase}/weddings/guest-access/${slug}/${token}`);
      if (accessRes.ok) {
        const data = await accessRes.json();
        if (data.wedding) {
          const weddingForContext = {
            ...data.wedding,
            id: data.wedding.id || data.wedding._id || slug,
            slug: data.wedding.slug || slug,
          };
          setWeddingData(weddingForContext);
        }
        latestRsvp = data.rsvp || null;
        setRsvpData(latestRsvp);
      }

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

    try {
      const response = await fetch(`${apiBase}/otp/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guest_id: guestId }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to resend code');
      }

      if (data.contact_type) {
        setOtpContactType(data.contact_type);
      }

      setResendCooldown(65);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend code');
    } finally {
      setLoading(false);
    }
  };

  const handleRSVPSuccess = () => {
    setFormCompleted(true);
  };

  const handleEditRSVP = () => {
    setEditMode(true);
    setStep('rsvp_form');
  };

  const canDismiss = formCompleted ||
    (step === 'already_rsvped' && !editMode) ||
    (error && !loading) ||
    isTokenExpired;

  /* ────────────── render helpers ────────────── */

  /** Reusable accent-colored button style */
  const accentBtnStyle: React.CSSProperties = {
    backgroundColor: accentColor,
    color: '#0f172a',
    boxShadow: `0 10px 15px -3px rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, 0.4)`,
  };

  const renderStep = () => {
    switch (step) {
      case 'loading':
        return (
          <div className="text-center py-12">
            {loading ? (
              <>
                <div
                  className="inline-block h-10 w-10 animate-spin rounded-full border-4 border-solid border-r-transparent mb-4"
                  style={{ borderColor: accentColor, borderRightColor: 'transparent' }}
                />
                <p className="text-slate-300">Loading your invitation...</p>
              </>
            ) : error ? (
              <>
                <div
                  className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6"
                  style={{ backgroundColor: `rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, 0.2)` }}
                >
                  <svg className="w-8 h-8" style={{ color: accentColor }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                <p className="mb-4" style={{ color: accentColor }}>{error}</p>
                <div className="flex flex-col gap-3">
                  {!isTokenExpired && (
                    <button
                      onClick={fetchInitialData}
                      className="px-6 py-3 font-semibold rounded-full shadow-lg hover:opacity-90 transition-all"
                      style={accentBtnStyle}
                    >
                      Try Again
                    </button>
                  )}
                  <button
                    onClick={handleClose}
                    className="px-6 py-3 border border-white/20 text-white font-semibold rounded-full hover:bg-white/10 transition-all"
                  >
                    {isTokenExpired ? 'Close' : 'Cancel'}
                  </button>
                </div>
              </>
            ) : null}
          </div>
        );

      case 'otp_request':
        return (
          <div className="text-center py-6">
            <div
              className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6"
              style={{ backgroundColor: `rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, 0.2)` }}
            >
              <svg className="w-10 h-10" style={{ color: accentColor }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              You&apos;re invited to <span className="font-semibold" style={{ color: accentColor }}>{weddingData?.couple_names}&apos;s</span> wedding!
            </p>
            <p className="text-sm text-slate-400 mb-8">
              To protect your privacy, we&apos;ll send a verification code to your {guestData?.phone ? 'phone' : 'email'} before you can RSVP.
            </p>

            {error && (
              <div
                className="rounded-2xl p-4 mb-6"
                style={{
                  borderWidth: 1,
                  borderStyle: 'solid',
                  borderColor: `rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, 0.4)`,
                  backgroundColor: `rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, 0.1)`,
                }}
              >
                <p className="text-sm" style={{ color: accentColor }}>{error}</p>
              </div>
            )}

            <button
              onClick={handleRequestOTP}
              disabled={loading}
              className="w-full py-4 font-semibold rounded-full shadow-lg hover:opacity-90 disabled:opacity-50 transition-all"
              style={accentBtnStyle}
            >
              {loading ? 'Sending...' : 'Send Verification Code'}
            </button>
            <button
              onClick={handleClose}
              disabled={loading}
              className="w-full mt-3 py-3 border border-white/20 text-white/70 text-sm rounded-full hover:bg-white/10 disabled:opacity-50 transition-all"
            >
              Cancel
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
              A 6-digit code was sent to your {otpContactType || 'phone'}. Enter it below to continue.
            </p>
            <div className="flex flex-col gap-4">
              <input
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
                className="w-full px-4 py-4 border border-white/10 bg-white/5 rounded-xl text-center tracking-[0.5em] text-white text-xl placeholder-slate-500 focus:ring-1 focus:outline-none backdrop-blur"
                style={{ '--tw-ring-color': accentColor } as React.CSSProperties}
                placeholder="------"
                autoFocus
              />
              <button
                onClick={handleVerifyOTP}
                disabled={loading || otp.length !== 6}
                className="w-full py-4 px-6 rounded-full font-semibold shadow-lg hover:opacity-90 disabled:opacity-50 transition-all"
                style={accentBtnStyle}
              >
                {loading ? 'Verifying...' : 'Verify & Continue'}
              </button>
              {error && <p className="text-center text-sm" style={{ color: accentColor }}>{error}</p>}
              <div className="text-center mt-2 space-y-2">
                <button
                  onClick={handleResendOTP}
                  disabled={loading || resendCooldown > 0}
                  className="text-sm hover:opacity-80 disabled:opacity-50 transition-colors"
                  style={{ color: accentColor }}
                >
                  {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend Code'}
                </button>
                <div>
                  <button
                    onClick={handleClose}
                    disabled={loading}
                    className="text-sm text-white/50 hover:text-white/70 disabled:opacity-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        );

      case 'rsvp_form':
        return (
          <RSVPForm
            guest={guestData}
            token={token}
            existingRsvp={editMode ? rsvpData : null}
            onSuccess={handleRSVPSuccess}
            onViewWeddingPage={handleClose}
          />
        );

      case 'already_rsvped':
        return (
          <AlreadyRSVPedScreen
            guest={guestData}
            rsvp={rsvpData}
            onEditClick={handleEditRSVP}
            onViewWeddingPage={handleClose}
          />
        );

      default:
        return null;
    }
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-50"
        onClose={() => { if (canDismiss) handleClose(); }}
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
              <Dialog.Panel
                className="w-full max-w-2xl rounded-[2rem] border border-white/10 bg-slate-950 shadow-2xl overflow-hidden"
                style={themeVars}
              >
                {/* Dark themed background effects — uses couple's accent + secondary colors */}
                <div className="relative">
                  <div
                    className="absolute inset-0 opacity-60"
                    style={{
                      background:
                        `radial-gradient(900px 600px at 15% -10%, rgba(${aRgb.r},${aRgb.g},${aRgb.b},0.35), transparent 70%), radial-gradient(1200px 700px at 90% 110%, rgba(${sRgb.r},${sRgb.g},${sRgb.b},0.25), transparent 65%)`,
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
