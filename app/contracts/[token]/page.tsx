'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { preloadStripeClient } from '@/utils/stripeClient';
import { toast } from 'sonner';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import ContractTemplate from '../../components/contracts/ContractTemplate';
import DigitalSignature, { SignatureData } from '../../components/contracts/DigitalSignature';
import StripePaymentCapture, { PaymentMethodData } from '../../components/contracts/StripePaymentCapture';
import {
  Loader2,
  CheckCircle,
  AlertCircle,
  FileText,
  CreditCard,
  PenLine,
  PartyPopper,
  Calendar,
  DollarSign,
  ArrowRight
} from 'lucide-react';

interface ContractData {
  id: string;
  status: string;
  couple: {
    partner1_name: string;
    email: string;
    partner2_name?: string;
    name?: string;
    partner_name?: string;
    display_name?: string;
    partner_email?: string;
    phone?: string;
  };
  wedding_date?: string;
  venue?: string;
  package_snapshot: {
    name: string;
    description?: string;
    total_amount: number;
    currency: string;
    services: Array<{ name: string; description?: string; included: boolean }>;
    payment_schedule: Array<{
      name: string;
      trigger: string;
      percentage?: number;
      amount?: number;
      days_after?: number;
      days_before?: number;
    }>;
    cancellation_policy?: string;
    late_payment_policy?: string;
    custom_terms?: string;
  };
  planner_name?: string;
  planner_email?: string;
  planner_phone?: string;
  planner_logo?: string;
  sent_at?: string;
  viewed_at?: string;
  signed_at?: string;
  signature?: {
    signed_by: string;
  };
  payment_method_last4?: string;
  payment_method_brand?: string;
}

type SigningStep = 'review' | 'payment' | 'signature' | 'complete';

export default function PublicContractPage() {
  const params = useParams();
  const token = params.token as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [contract, setContract] = useState<ContractData | null>(null);

  // Signing flow state
  const [currentStep, setCurrentStep] = useState<SigningStep>('review');
  const [setupIntentSecret, setSetupIntentSecret] = useState<string>('');
  const [setupCustomerId, setSetupCustomerId] = useState<string>('');
  const [paymentData, setPaymentData] = useState<PaymentMethodData | null>(null);
  const [signatureData, setSignatureData] = useState<SignatureData | null>(null);
  const [signing, setSigning] = useState(false);

  const fetchContract = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/public/contracts/${token}`);

      if (response.status === 404) {
        setError('This contract link is invalid or has expired.');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to load contract');
      }

      const data = await response.json();
      setContract(data.contract);

      // If contract is already signed, go to complete step
      if (['signed', 'active', 'completed'].includes(data.contract.status)) {
        setCurrentStep('complete');
      }
    } catch (err) {
      setError('Unable to load the contract. Please try again later.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchContract();
  }, [fetchContract]);

  useEffect(() => {
    preloadStripeClient().catch(() => undefined);
  }, []);

  const initiatePaymentSetup = async () => {
    try {
      const baseUrl = getApiBaseUrl();

      // Create a SetupIntent for saving the payment method
      const response = await fetch(`${baseUrl}/public/contracts/${token}/setup-intent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        throw new Error('Failed to initialize payment setup');
      }

      const data = await response.json();
      setSetupIntentSecret(data.client_secret);
      setSetupCustomerId(data.customer_id || '');
      setCurrentStep('payment');
    } catch (err) {
      toast.error('Failed to initialize payment. Please try again.');
    }
  };

  const handlePaymentMethodCaptured = (data: PaymentMethodData) => {
    setPaymentData(data);
    setCurrentStep('signature');
    toast.success('Payment method saved!');
  };

  const handleSignatureComplete = async (data: SignatureData) => {
    if (!paymentData) {
      toast.error('Please complete payment setup first');
      setCurrentStep('payment');
      return;
    }

    setSignatureData(data);
    setSigning(true);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/public/contracts/${token}/sign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          signature_name: data.signatureName,
          stripe_customer_id: paymentData.customerId,
          stripe_payment_method_id: paymentData.paymentMethodId,
          payment_method_last4: paymentData.last4,
          payment_method_brand: paymentData.brand,
          accept_terms: data.acceptedTerms
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to sign contract');
      }

      const result = await response.json();
      setContract(prev => prev ? { ...prev, ...result.contract, status: 'signed' } : null);
      setCurrentStep('complete');
      toast.success('Contract signed successfully!');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to sign contract';
      toast.error(message);
    } finally {
      setSigning(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-500 mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-400">Loading your contract...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !contract) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center p-4">
        <Card className="max-w-md w-full p-8 text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
            Contract Not Found
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            {error || 'This contract link is invalid or has expired.'}
          </p>
        </Card>
      </div>
    );
  }

  // Already signed - show confirmation
  if (currentStep === 'complete') {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-12 px-4">
        <div className="max-w-3xl mx-auto">
          {/* Success Banner */}
          <Card className="mb-8 p-8 text-center bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-green-200 dark:border-green-800">
            <PartyPopper className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
              Contract Signed!
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mb-6">
              Thank you for signing! Your wedding planning journey has officially begun.
            </p>

            {contract.payment_method_last4 && (
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 rounded-lg text-sm">
                <CreditCard size={16} className="text-slate-500" />
                <span className="text-slate-600 dark:text-slate-400">
                  Payments will be charged to card ending in{' '}
                  <span className="font-medium text-slate-900 dark:text-white">
                    {contract.payment_method_last4}
                  </span>
                </span>
              </div>
            )}
          </Card>

          {/* Contract Details */}
          <ContractTemplate
            packageSnapshot={contract.package_snapshot}
            couple={contract.couple}
            weddingDate={contract.wedding_date}
            venue={contract.venue}
            plannerName={contract.planner_name}
            plannerEmail={contract.planner_email}
            plannerPhone={contract.planner_phone}
            plannerLogo={contract.planner_logo}
            status={contract.status}
            signedAt={contract.signed_at}
            signatureName={contract.signature?.signed_by}
          />

          {/* Next Steps */}
          <Card className="mt-8 p-6">
            <h2 className="font-semibold text-slate-900 dark:text-white mb-4">
              What happens next?
            </h2>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center flex-shrink-0">
                  <CheckCircle size={16} className="text-primary-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-900 dark:text-white">
                    Confirmation email sent
                  </p>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    A copy of your signed contract has been sent to {contract.couple.email}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                  <Calendar size={16} className="text-slate-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-900 dark:text-white">
                    Payment reminders
                  </p>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    You&apos;ll receive reminders before each scheduled payment
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                  <DollarSign size={16} className="text-slate-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-900 dark:text-white">
                    Automatic payments
                  </p>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    Payments will be processed according to your schedule
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  // Signing flow
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-4">
            {[
              { step: 'review', label: 'Review', icon: FileText },
              { step: 'payment', label: 'Payment', icon: CreditCard },
              { step: 'signature', label: 'Sign', icon: PenLine }
            ].map((item, index) => {
              const Icon = item.icon;
              const isActive = item.step === currentStep;
              const isComplete =
                (item.step === 'review' && ['payment', 'signature'].includes(currentStep)) ||
                (item.step === 'payment' && currentStep === 'signature');

              return (
                <div key={item.step} className="flex items-center">
                  <div
                    className={`flex items-center gap-2 px-4 py-2 rounded-full transition-colors ${
                      isActive
                        ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400'
                        : isComplete
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-400'
                    }`}
                  >
                    {isComplete ? (
                      <CheckCircle size={18} />
                    ) : (
                      <Icon size={18} />
                    )}
                    <span className="text-sm font-medium">{item.label}</span>
                  </div>
                  {index < 2 && (
                    <ArrowRight size={16} className="mx-2 text-slate-300 dark:text-slate-600" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Step: Review */}
        {currentStep === 'review' && (
          <>
            <ContractTemplate
              packageSnapshot={contract.package_snapshot}
              couple={contract.couple}
              weddingDate={contract.wedding_date}
              venue={contract.venue}
              plannerName={contract.planner_name}
              plannerEmail={contract.planner_email}
              plannerPhone={contract.planner_phone}
              plannerLogo={contract.planner_logo}
              status={contract.status}
            />

            <div className="mt-8 text-center">
              <Button
                onClick={initiatePaymentSetup}
                size="lg"
                className="px-12 py-4 text-lg"
              >
                Continue to Payment Setup
                <ArrowRight size={20} className="ml-2" />
              </Button>
              <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                You&apos;ll set up your payment method before signing
              </p>
            </div>
          </>
        )}

        {/* Step: Payment */}
        {currentStep === 'payment' && (
          <Card className="max-w-lg mx-auto p-8">
            <div className="text-center mb-6">
              <CreditCard className="w-12 h-12 text-primary-500 mx-auto mb-3" />
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                Set Up Payment Method
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mt-2">
                Your card will be securely saved for scheduled payments
              </p>
            </div>

            <StripePaymentCapture
              clientSecret={setupIntentSecret}
              customerId={setupCustomerId}
              onPaymentMethodCaptured={handlePaymentMethodCaptured}
              onError={(err) => toast.error(err)}
            />

            <div className="mt-6 text-center">
              <button
                onClick={() => setCurrentStep('review')}
                className="text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
              >
                ← Back to contract review
              </button>
            </div>
          </Card>
        )}

        {/* Step: Signature */}
        {currentStep === 'signature' && (
          <Card className="max-w-lg mx-auto p-8">
            <div className="text-center mb-6">
              <PenLine className="w-12 h-12 text-primary-500 mx-auto mb-3" />
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                Sign Your Contract
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mt-2">
                Type your full name below to digitally sign
              </p>
            </div>

            {/* Payment method confirmation */}
            {paymentData && (
              <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg flex items-center gap-3">
                <CheckCircle className="text-green-500" size={20} />
                <div className="text-sm">
                  <p className="font-medium text-green-700 dark:text-green-300">
                    Payment method saved
                  </p>
                  <p className="text-green-600 dark:text-green-400">
                    {paymentData.brand} ending in {paymentData.last4}
                  </p>
                </div>
              </div>
            )}

            <DigitalSignature
              coupleName={contract.couple.display_name || contract.couple.name || contract.couple.partner1_name}
              onSignatureComplete={handleSignatureComplete}
              disabled={signing}
            />

            {signing && (
              <div className="mt-6 flex items-center justify-center gap-2 text-primary-600">
                <Loader2 className="animate-spin" size={20} />
                <span>Processing your signature...</span>
              </div>
            )}

            <div className="mt-6 text-center">
              <button
                onClick={() => setCurrentStep('payment')}
                disabled={signing}
                className="text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 disabled:opacity-50"
              >
                ← Back to payment setup
              </button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
