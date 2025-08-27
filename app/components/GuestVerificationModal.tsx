'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';

interface GuestVerificationModalProps {
  slug: string;
  onVerified: (weddingData: any, guestData?: any) => void;
  onCancel?: () => void;
}

interface PrivacyInfo {
  couple_names: string;
  privacy_mode: string;
  requires_password: boolean;
  requires_guest_verification: boolean;
  verification_requirements: {
    otp_enabled: boolean;
    supports_phone: boolean;
    supports_email: boolean;
  };
}

export default function GuestVerificationModal({ 
  slug, 
  onVerified, 
  onCancel 
}: GuestVerificationModalProps) {
  const [privacyInfo, setPrivacyInfo] = useState<PrivacyInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [sendingOtp, setSendingOtp] = useState(false);
  const [error, setError] = useState('');

  // Form states
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpStep, setOtpStep] = useState(false);
  const [otpContact, setOtpContact] = useState('');
  const [otpContactType, setOtpContactType] = useState('');
  const [otpCountdown, setOtpCountdown] = useState(0);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const API_URL = API_BASE_URL.replace('/admin', ''); // Remove /admin for public endpoints

  useEffect(() => {
    fetchPrivacyInfo();
  }, [slug]);

  const fetchPrivacyInfo = async () => {
    try {
      const response = await fetch(`${API_URL}/weddings/privacy-info/${slug}`);
      if (!response.ok) {
        throw new Error('Failed to load wedding information');
      }
      const data = await response.json();
      setPrivacyInfo(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load wedding information');
    } finally {
      setLoading(false);
    }
  };

  const handleVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    setError('');

    try {
      const verificationData: any = {};
      
      if (privacyInfo?.privacy_mode === 'password' && password) {
        verificationData.password = password;
      } else if (privacyInfo?.privacy_mode === 'private') {
        if (token) {
          verificationData.token = token;
        } else if (otpStep && otpCode && otpContact) {
          // OTP verification
          verificationData.otp_code = otpCode;
          verificationData.contact = otpContact;
        } else {
          // Request OTP
          if (phone) {
            verificationData.phone = phone.trim();
          } else if (email) {
            verificationData.email = email.trim();
          }
        }
      }

      const response = await fetch(`${API_URL}/weddings/verify-guest-access/${slug}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(verificationData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Verification failed');
      }

      const result = await response.json();
      
      // Check if OTP is required
      if (result.otp_required) {
        await sendOtp(result.contact, result.contact_type);
        return;
      }
      
      onVerified(result.wedding, result.guest);

    } catch (err: any) {
      setError(err.message || 'Verification failed. Please check your information and try again.');
    } finally {
      setVerifying(false);
    }
  };

  const sendOtp = async (contact: string, contactType: string) => {
    setSendingOtp(true);
    setError('');
    
    try {
      const response = await fetch(`${API_URL}/api/otp/send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          wedding_id: slug, // Use slug as wedding_id for now
          contact: contact,
          contact_type: contactType
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to send verification code');
      }

      const result = await response.json();
      setOtpStep(true);
      setOtpContact(contact);
      setOtpContactType(contactType);
      setOtpCountdown(result.expires_in_minutes * 60); // Convert to seconds
      
      // Start countdown
      const countdown = setInterval(() => {
        setOtpCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(countdown);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

    } catch (err: any) {
      setError(err.message || 'Failed to send verification code');
    } finally {
      setSendingOtp(false);
    }
  };

  const resendOtp = async () => {
    if (otpContact && otpContactType) {
      await sendOtp(otpContact, otpContactType);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const goBackToContact = () => {
    setOtpStep(false);
    setOtpCode('');
    setOtpContact('');
    setOtpContactType('');
    setOtpCountdown(0);
    setError('');
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading wedding information...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!privacyInfo) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Unable to Load Wedding</h2>
            <p className="text-gray-600 mb-4">{error}</p>
            {onCancel && (
              <Button onClick={onCancel} variant="secondary">
                Go Back
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // If wedding is public, don't show modal
  if (privacyInfo.privacy_mode === 'public') {
    useEffect(() => {
      onVerified({ couple_names: privacyInfo.couple_names });
    }, []);
    return null;
  }

  // OTP Step UI
  if (otpStep) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
          <div className="p-6">
            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Enter Verification Code
              </h2>
              <div className="w-16 h-1 bg-rose-400 mx-auto mb-4"></div>
              <p className="text-gray-600">
                We sent a 6-digit code to your {otpContactType}:
              </p>
              <p className="font-semibold text-gray-800 mt-1">
                {otpContact}
              </p>
            </div>

            <form onSubmit={handleVerification} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Verification Code
                </label>
                <input
                  type="text"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-transparent text-center text-2xl font-mono tracking-widest"
                  placeholder="000000"
                  maxLength={6}
                  required
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm text-red-600">{error}</p>
                </div>
              )}

              <div className="flex space-x-3">
                <Button
                  type="submit"
                  disabled={verifying || otpCode.length !== 6}
                  className="flex-1 bg-rose-600 hover:bg-rose-700 disabled:bg-gray-400"
                >
                  {verifying ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Verifying...
                    </>
                  ) : (
                    'Verify'
                  )}
                </Button>
              </div>

              <div className="text-center space-y-2">
                {otpCountdown > 0 ? (
                  <p className="text-sm text-gray-600">
                    Code expires in {formatTime(otpCountdown)}
                  </p>
                ) : (
                  <button
                    type="button"
                    onClick={resendOtp}
                    disabled={sendingOtp}
                    className="text-sm text-rose-600 hover:text-rose-700 disabled:text-gray-400"
                  >
                    {sendingOtp ? 'Sending...' : 'Send new code'}
                  </button>
                )}
                
                <button
                  type="button"
                  onClick={goBackToContact}
                  className="block mx-auto text-sm text-gray-600 hover:text-gray-800"
                >
                  ← Back to contact info
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // Main verification form
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {privacyInfo.couple_names}
            </h2>
            <div className="w-16 h-1 bg-rose-400 mx-auto mb-4"></div>
            <p className="text-gray-600">
              {privacyInfo.privacy_mode === 'password' 
                ? 'This wedding is password protected'
                : 'Guest verification required'
              }
            </p>
          </div>

          <form onSubmit={handleVerification} className="space-y-4">
            {privacyInfo.privacy_mode === 'password' ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Wedding Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
                  placeholder="Enter wedding password"
                  required
                />
              </div>
            ) : (
              <>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                  <p className="text-sm text-blue-800">
                    <strong>Have your invitation?</strong> You can use your invitation token for quick access.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Invitation Token (Optional)
                  </label>
                  <input
                    type="text"
                    value={token}
                    onChange={(e) => {
                      setToken(e.target.value);
                      if (e.target.value) {
                        setPhone('');
                        setEmail('');
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
                    placeholder="Enter your invitation token"
                  />
                </div>

                {!token && (
                  <>
                    <div className="text-center text-gray-500 text-sm">
                      - OR -
                    </div>

                    <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                      <p className="text-sm text-green-800">
                        <strong>Don't have your token?</strong> Enter your phone number or email below to receive a verification code.
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Phone Number
                      </label>
                      <input
                        type="tel"
                        value={phone}
                        onChange={(e) => {
                          setPhone(e.target.value);
                          if (e.target.value) setEmail(''); // Clear email when phone is entered
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
                        placeholder="Enter your phone number"
                      />
                    </div>

                    <div className="text-center py-2">
                      <span className="text-gray-400 text-sm">OR</span>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Email Address
                      </label>
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => {
                          setEmail(e.target.value);
                          if (e.target.value) setPhone(''); // Clear phone when email is entered
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
                        placeholder="Enter your email address"
                      />
                    </div>

                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                      <p className="text-sm text-gray-600">
                        <strong>Note:</strong> Use the same contact information from your original invitation.
                      </p>
                    </div>
                  </>
                )}
              </>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}

            <div className="flex space-x-3 pt-4">
              {onCancel && (
                <Button
                  type="button"
                  onClick={onCancel}
                  variant="secondary"
                  className="flex-1"
                >
                  Cancel
                </Button>
              )}
              <Button
                type="submit"
                disabled={verifying || sendingOtp || (privacyInfo?.privacy_mode === 'private' && !token && !phone && !email && !password)}
                className="flex-1 bg-rose-600 hover:bg-rose-700"
              >
                {(verifying || sendingOtp) ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    {sendingOtp ? 'Sending Code...' : 'Verifying...'}
                  </>
                ) : (
                  privacyInfo?.privacy_mode === 'private' && !token && (phone || email) ? 'Send Verification Code' : 'Access Wedding'
                )}
              </Button>
            </div>
          </form>

          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500">
              Having trouble accessing the wedding? Please contact the couple directly.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}