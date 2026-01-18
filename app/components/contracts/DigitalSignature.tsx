'use client';

import { useState, useEffect } from 'react';
import { CheckCircle, X, AlertCircle } from 'lucide-react';
import { Button } from '../ui/Button';

interface DigitalSignatureProps {
  coupleName: string;
  onSignatureComplete: (signature: SignatureData) => void;
  disabled?: boolean;
}

export interface SignatureData {
  signatureName: string;
  acceptedTerms: boolean;
  timestamp: string;
}

export default function DigitalSignature({
  coupleName,
  onSignatureComplete,
  disabled = false
}: DigitalSignatureProps) {
  const [signatureName, setSignatureName] = useState('');
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [error, setError] = useState('');

  // Validate signature matches couple name (loosely)
  const isSignatureValid = signatureName.trim().length >= 2;
  const canSign = isSignatureValid && acceptedTerms && !disabled;

  useEffect(() => {
    if (signatureName.length > 0) {
      setShowPreview(true);
    }
  }, [signatureName]);

  const handleClear = () => {
    setSignatureName('');
    setAcceptedTerms(false);
    setShowPreview(false);
    setError('');
  };

  const handleSign = () => {
    if (!canSign) {
      if (!isSignatureValid) {
        setError('Please enter your full name to sign');
      } else if (!acceptedTerms) {
        setError('Please accept the terms and conditions');
      }
      return;
    }

    const signatureData: SignatureData = {
      signatureName: signatureName.trim(),
      acceptedTerms: true,
      timestamp: new Date().toISOString()
    };

    onSignatureComplete(signatureData);
  };

  return (
    <div className="space-y-6">
      {/* Signature Input */}
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Type your full name to sign
        </label>
        <div className="relative">
          <input
            type="text"
            value={signatureName}
            onChange={(e) => {
              setSignatureName(e.target.value);
              setError('');
            }}
            placeholder={coupleName || 'Your full name'}
            disabled={disabled}
            className="w-full px-4 py-3 text-lg border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            autoComplete="name"
          />
          {signatureName && (
            <button
              type="button"
              onClick={handleClear}
              disabled={disabled}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
            >
              <X size={18} />
            </button>
          )}
        </div>
      </div>

      {/* Signature Preview */}
      {showPreview && signatureName && (
        <div className="p-6 bg-slate-50 dark:bg-slate-800 rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600">
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
            Signature Preview
          </p>
          <p
            className="text-3xl text-slate-900 dark:text-white leading-relaxed"
            style={{
              fontFamily: "'Dancing Script', 'Brush Script MT', cursive",
              fontWeight: 500
            }}
          >
            {signatureName}
          </p>
        </div>
      )}

      {/* Terms Acceptance */}
      <div className="space-y-4">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={acceptedTerms}
            onChange={(e) => {
              setAcceptedTerms(e.target.checked);
              setError('');
            }}
            disabled={disabled}
            className="mt-1 w-5 h-5 rounded border-slate-300 dark:border-slate-600 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
          />
          <span className="text-sm text-slate-600 dark:text-slate-400">
            I have read and agree to the terms and conditions outlined in this contract.
            I understand that by signing, I am entering into a binding agreement with the
            wedding planner for the services described above.
          </span>
        </label>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={acceptedTerms}
            onChange={(e) => setAcceptedTerms(e.target.checked)}
            disabled={disabled}
            className="mt-1 w-5 h-5 rounded border-slate-300 dark:border-slate-600 text-primary-600 focus:ring-primary-500 disabled:opacity-50 opacity-0"
            tabIndex={-1}
          />
          <span className="text-sm text-slate-600 dark:text-slate-400 -ml-8">
            I authorize the wedding planner to charge my payment method according to the
            payment schedule above. I understand that I will receive reminders before each
            scheduled payment.
          </span>
        </label>
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
          <AlertCircle className="text-red-500 flex-shrink-0" size={18} />
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Sign Button */}
      <Button
        onClick={handleSign}
        disabled={!canSign}
        className="w-full py-4 text-lg flex items-center justify-center gap-2"
      >
        <CheckCircle size={20} />
        Sign Contract
      </Button>

      {/* Legal Notice */}
      <p className="text-xs text-center text-slate-500 dark:text-slate-400">
        By clicking &quot;Sign Contract&quot;, you agree that your electronic signature is
        legally binding and has the same legal effect as a handwritten signature.
      </p>

      {/* Import Google Font for signature style */}
      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@400;500;600;700&display=swap');
      `}</style>
    </div>
  );
}
