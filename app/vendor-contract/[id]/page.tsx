'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';

interface ContractSection {
  id: string;
  title: string;
  content: string;
  order: number;
}

interface PublicContract {
  _id: string;
  contract_title: string;
  contract_number?: string;
  vendor_name: string;
  vendor_email: string;
  planner_name?: string;
  planner_company?: string;
  couple_names?: string;
  wedding_date?: string;
  service_date?: string;
  service_location?: string;
  service_category: string;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  total_amount: number;
  deposit_amount?: number;
  currency: string;
  status: string;
  sent_at?: string;
  viewed_at?: string;
  signed_at?: string;
  signed_by_name?: string;
}

export default function PublicContractPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const contractId = params.id as string;
  const token = searchParams.get('token');

  // State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [contract, setContract] = useState<PublicContract | null>(null);
  const [signing, setSigning] = useState(false);
  const [signed, setSigned] = useState(false);
  const [showSignModal, setShowSignModal] = useState(false);

  // Signature form
  const [signerName, setSignerName] = useState('');
  const [signerEmail, setSignerEmail] = useState('');
  const [agreeToTerms, setAgreeToTerms] = useState(false);

  // Fetch contract
  const fetchContract = useCallback(async () => {
    if (!contractId || !token) {
      setError('Invalid contract link. Please check your email and try again.');
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const API_BASE = getApiBaseUrl();
      const response = await fetch(`${API_BASE}/vendor-contract/public/contracts/${contractId}?token=${token}`);

      if (!response.ok) {
        if (response.status === 404) {
          setError('Contract not found. It may have been removed or the link has expired.');
        } else if (response.status === 403) {
          setError('Access denied. This link may have expired or is invalid.');
        } else {
          setError('Failed to load contract. Please try again later.');
        }
        return;
      }

      const data = await response.json();
      setContract(data);

      // Pre-fill signer info from contract
      setSignerName(data.vendor_name);
      setSignerEmail(data.vendor_email);

      // Check if already signed
      if (data.status === 'signed' || data.status === 'completed') {
        setSigned(true);
      }
    } catch (err) {
      console.error('Error fetching contract:', err);
      setError('Failed to load contract. Please check your internet connection and try again.');
    } finally {
      setLoading(false);
    }
  }, [contractId, token]);

  useEffect(() => {
    fetchContract();
  }, [fetchContract]);

  // Handle signing
  const handleSign = async () => {
    if (!signerName || !signerEmail || !agreeToTerms) {
      return;
    }

    setSigning(true);
    try {
      const API_BASE = getApiBaseUrl();
      const response = await fetch(
        `${API_BASE}/vendor-contract/public/contracts/${contractId}/sign?token=${token}&signer_name=${encodeURIComponent(signerName)}&signer_email=${encodeURIComponent(signerEmail)}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to sign contract');
      }

      setSigned(true);
      setShowSignModal(false);
      // Refresh contract to get updated status
      fetchContract();
    } catch (err) {
      console.error('Error signing contract:', err);
      setError('We couldn\u2019t complete the signature. Please check your connection and try again.');
    } finally {
      setSigning(false);
    }
  };

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: contract?.currency || 'USD',
    }).format(amount);
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading contract...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Unable to Load Contract</h1>
          <p className="text-gray-600 mb-6">{error}</p>
          <p className="text-sm text-gray-500">
            If you believe this is an error, please contact the wedding planner who sent you this contract.
          </p>
        </div>
      </div>
    );
  }

  if (!contract) {
    return null;
  }

  // Signed success state
  if (signed && contract.signed_at) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100">
        <div className="max-w-2xl mx-auto px-4 py-16">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Contract Signed!</h1>
            <p className="text-lg text-gray-600 mb-6">
              Thank you for signing. {contract.planner_name || 'The wedding planner'} has been notified.
            </p>

            <div className="bg-gray-50 rounded-xl p-6 text-left mb-6">
              <h3 className="font-semibold text-gray-900 mb-4">Contract Summary</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Contract</span>
                  <span className="font-medium text-gray-900">{contract.contract_title}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Amount</span>
                  <span className="font-medium text-gray-900">{formatCurrency(contract.total_amount)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Signed By</span>
                  <span className="font-medium text-gray-900">{contract.signed_by_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Signed On</span>
                  <span className="font-medium text-gray-900">
                    {new Date(contract.signed_at).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            <p className="text-sm text-gray-500">
              A confirmation email has been sent to {contract.vendor_email}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900">{contract.contract_title}</h1>
              <p className="text-sm text-gray-500">
                {contract.contract_number && `#${contract.contract_number} - `}
                From {contract.planner_name || contract.planner_company || 'Wedding Planner'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {signed ? (
                <span className="px-4 py-2 bg-green-100 text-green-800 rounded-full font-medium">
                  Signed
                </span>
              ) : (
                <button
                  onClick={() => setShowSignModal(true)}
                  className="px-6 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg font-semibold hover:opacity-90 transition-opacity shadow-lg"
                >
                  Sign Contract
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Contract Content */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Summary Card */}
        <div className="bg-white rounded-2xl shadow-xl mb-8 overflow-hidden">
          <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-8 text-white">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <div className="text-indigo-200 text-sm mb-1">Vendor</div>
                <div className="font-semibold">{contract.vendor_name}</div>
              </div>
              <div>
                <div className="text-indigo-200 text-sm mb-1">Event</div>
                <div className="font-semibold">
                  {contract.couple_names || 'Wedding'}
                </div>
              </div>
              <div>
                <div className="text-indigo-200 text-sm mb-1">Date</div>
                <div className="font-semibold">
                  {contract.service_date
                    ? new Date(contract.service_date).toLocaleDateString()
                    : contract.wedding_date
                    ? new Date(contract.wedding_date).toLocaleDateString()
                    : 'TBD'}
                </div>
              </div>
              <div>
                <div className="text-indigo-200 text-sm mb-1">Total Amount</div>
                <div className="text-2xl font-bold">{formatCurrency(contract.total_amount)}</div>
              </div>
            </div>
          </div>

          {contract.deposit_amount && (
            <div className="px-6 py-4 bg-amber-50 border-b border-amber-100">
              <div className="flex items-center gap-2 text-amber-800">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="font-medium">
                  Deposit of {formatCurrency(contract.deposit_amount)} required upon signing
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Contract Sections */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
            <h2 className="font-semibold text-gray-900">Contract Details</h2>
          </div>

          <div className="p-6 space-y-8">
            {contract.sections
              .sort((a, b) => a.order - b.order)
              .map((section) => (
                <div key={section.id} className="border-b border-gray-100 pb-6 last:border-0 last:pb-0">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">{section.title}</h3>
                  <div className="prose prose-gray max-w-none">
                    <div className="whitespace-pre-wrap text-gray-700">{section.content}</div>
                  </div>
                </div>
              ))}

            {contract.terms_and_conditions && (
              <div className="border-b border-gray-100 pb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Terms & Conditions</h3>
                <div className="prose prose-gray max-w-none">
                  <div className="whitespace-pre-wrap text-gray-700">{contract.terms_and_conditions}</div>
                </div>
              </div>
            )}

            {contract.cancellation_policy && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Cancellation Policy</h3>
                <div className="prose prose-gray max-w-none">
                  <div className="whitespace-pre-wrap text-gray-700">{contract.cancellation_policy}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer CTA */}
        {!signed && (
          <div className="mt-8 text-center">
            <button
              onClick={() => setShowSignModal(true)}
              className="px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl font-semibold text-lg hover:opacity-90 transition-opacity shadow-lg"
            >
              Review Complete - Sign Contract
            </button>
            <p className="mt-3 text-sm text-gray-500">
              By signing, you agree to the terms and conditions outlined above.
            </p>
          </div>
        )}
      </main>

      {/* Sign Modal */}
      {showSignModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-2xl font-bold text-gray-900">Sign Contract</h2>
              <p className="text-gray-600 mt-1">
                Please confirm your details to sign this contract electronically.
              </p>
            </div>

            <div className="p-6 space-y-6">
              {/* Summary */}
              <div className="bg-gray-50 rounded-xl p-4">
                <div className="text-sm text-gray-500 mb-1">You are signing</div>
                <div className="font-semibold text-gray-900">{contract.contract_title}</div>
                <div className="text-lg font-bold text-indigo-600 mt-1">
                  {formatCurrency(contract.total_amount)}
                </div>
              </div>

              {/* Signer info */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Your Full Name (as it will appear on the contract)
                </label>
                <input
                  type="text"
                  value={signerName}
                  onChange={(e) => setSignerName(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="Enter your full name"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Your Email Address
                </label>
                <input
                  type="email"
                  value={signerEmail}
                  onChange={(e) => setSignerEmail(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="Enter your email"
                />
              </div>

              {/* Agreement checkbox */}
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  id="agree"
                  checked={agreeToTerms}
                  onChange={(e) => setAgreeToTerms(e.target.checked)}
                  className="mt-1 w-5 h-5 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                />
                <label htmlFor="agree" className="text-sm text-gray-700">
                  I have read and agree to the terms and conditions of this contract. I understand that this
                  electronic signature is legally binding.
                </label>
              </div>

              {/* Legal notice */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-blue-600 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div className="text-sm text-blue-800">
                    <strong>Electronic Signature Notice:</strong> By clicking &quot;Sign Contract&quot;, you consent
                    to sign this document electronically. Your signature will be recorded with your IP
                    address and timestamp for verification purposes.
                  </div>
                </div>
              </div>
            </div>

            <div className="p-6 bg-gray-50 rounded-b-2xl flex gap-3">
              <button
                onClick={() => setShowSignModal(false)}
                className="flex-1 px-4 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={handleSign}
                disabled={signing || !signerName || !signerEmail || !agreeToTerms}
                className="flex-1 px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {signing ? (
                  <>
                    <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Signing...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Sign Contract
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
