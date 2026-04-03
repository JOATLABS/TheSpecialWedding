"use client";

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Textarea } from '@/components/ui/Textarea';
import { useAdmin } from '@/contexts/AdminContext';
import { Loader2, DollarSign, Send, Calendar, Mail, Link2 } from 'lucide-react';
import { toast } from 'sonner';
import { createPaymentLink, sendPaymentLink, type PayerType, type RecipientType } from '@/services/vendorManagementApi';
import { formatAdminDate, DEFAULT_TIMEZONE } from '@/utils/dateFormat';

interface VendorPaymentModalProps {
  open: boolean;
  onClose: () => void;
  vendorId: string;
  vendorName: string;
  vendorEmail: string;
  weddingId?: string;
  contractId?: string;
  milestoneId?: string;
  plannerEmail?: string;
  plannerName?: string;
  coupleEmail?: string;
  coupleNames?: string;
  onPaymentLinkCreated?: () => void;
}

type PaymentFlow = 'couple_to_vendor' | 'planner_to_vendor';

export function VendorPaymentModal({
  open,
  onClose,
  vendorId,
  vendorName,
  vendorEmail,
  weddingId,
  contractId,
  milestoneId,
  plannerEmail,
  plannerName,
  coupleEmail,
  coupleNames,
  onPaymentLinkCreated,
}: VendorPaymentModalProps) {
  const { token } = useAdmin();
  const [loading, setLoading] = useState(false);
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailMessage, setEmailMessage] = useState('');
  const [paymentFlow, setPaymentFlow] = useState<PaymentFlow>('couple_to_vendor');
  const [sendImmediately, setSendImmediately] = useState(true);
  const [step, setStep] = useState<'details' | 'confirm'>('details');

  const resetForm = () => {
    setAmount('');
    setDescription('');
    setDueDate('');
    setEmailSubject('');
    setEmailMessage('');
    setPaymentFlow('couple_to_vendor');
    setSendImmediately(true);
    setStep('details');
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleCreatePaymentLink = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      toast.error('Please enter a valid amount');
      return;
    }

    if (!vendorEmail) {
      toast.error('Vendor email is required');
      return;
    }

    // Validate payer info based on flow
    if (paymentFlow === 'couple_to_vendor' && !coupleEmail) {
      toast.error('Couple email is required for couple-to-vendor payments');
      return;
    }

    try {
      setLoading(true);

      if (!token) {
        toast.error('Please log in to create payment links');
        return;
      }

      // Determine payer and recipient based on flow
      let payerType: PayerType;
      let payerEmail: string;
      let payerName: string;
      let recipientType: RecipientType = 'vendor';
      let recipientEmail = vendorEmail;
      let recipientName = vendorName;

      if (paymentFlow === 'couple_to_vendor') {
        payerType = 'couple';
        payerEmail = coupleEmail || '';
        payerName = coupleNames || 'The Couple';
      } else {
        payerType = 'planner';
        payerEmail = plannerEmail || '';
        payerName = plannerName || 'Wedding Planner';
      }

      const paymentLinkData = {
        payer_type: payerType,
        payer_email: payerEmail,
        payer_name: payerName,
        recipient_type: recipientType,
        recipient_email: recipientEmail,
        recipient_name: recipientName,
        amount: parseFloat(amount),
        currency: 'USD',
        description: description || `Payment to ${vendorName}`,
        due_date: dueDate || undefined,
        wedding_id: weddingId,
        contract_id: contractId,
        milestone_id: milestoneId,
        vendor_profile_id: vendorId,
        email_subject: emailSubject || undefined,
        email_message: emailMessage || undefined,
      };

      // Create payment link
      const paymentLink = await createPaymentLink(token, paymentLinkData);

      if (sendImmediately) {
        // Send the payment link immediately
        await sendPaymentLink(token, paymentLink._id);
        toast.success(`Payment link sent to ${payerEmail}!`);
      } else {
        toast.success('Payment link created! You can send it later from the Payments tab.');
      }

      if (onPaymentLinkCreated) onPaymentLinkCreated();
      handleClose();

    } catch (error: any) {
      console.error('Payment link error:', error);
      toast.error(error.message || 'Failed to create payment link');
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    if (!amount || parseFloat(amount) <= 0) {
      toast.error('Please enter a valid amount');
      return;
    }
    setStep('confirm');
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Link2 className="h-5 w-5 text-green-600" aria-hidden="true" />
            Create Payment Link
          </DialogTitle>
          <DialogDescription>
            Send a secure payment link to collect payment for {vendorName}
          </DialogDescription>
        </DialogHeader>

        {step === 'details' && (
          <div className="space-y-4 py-4">
            {/* Payment Flow Selection */}
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Who will pay?</legend>
              <div className="grid grid-cols-2 gap-2" role="group">
                <button
                  type="button"
                  onClick={() => setPaymentFlow('couple_to_vendor')}
                  className={`p-3 rounded-lg border-2 text-left transition-all ${
                    paymentFlow === 'couple_to_vendor'
                      ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                  }`}
                  role="radio"
                  aria-checked={paymentFlow === 'couple_to_vendor'}
                  aria-label={`Couple pays vendor: ${coupleNames || 'Couple'} pays ${vendorName}`}
                >
                  <div className="font-medium text-sm">Couple pays Vendor</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {coupleNames || 'Couple'} → {vendorName}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => setPaymentFlow('planner_to_vendor')}
                  className={`p-3 rounded-lg border-2 text-left transition-all ${
                    paymentFlow === 'planner_to_vendor'
                      ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                  }`}
                  role="radio"
                  aria-checked={paymentFlow === 'planner_to_vendor'}
                  aria-label={`Planner pays vendor: ${plannerName || 'You'} pays ${vendorName}`}
                >
                  <div className="font-medium text-sm">I pay Vendor</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {plannerName || 'You'} → {vendorName}
                  </div>
                </button>
              </div>
            </fieldset>

            {/* Amount */}
            <div className="space-y-2">
              <Label htmlFor="amount">Amount (USD) <span aria-label="required">*</span></Label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-500" aria-hidden="true" />
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="pl-9"
                  aria-required="true"
                  aria-describedby="amount-hint"
                />
              </div>
              <p id="amount-hint" className="text-xs text-gray-500">Enter the payment amount in USD</p>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                placeholder="e.g., Deposit, Final Balance, Photography Package..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            {/* Due Date */}
            <div className="space-y-2">
              <Label htmlFor="dueDate" className="flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Due Date (Optional)
              </Label>
              <Input
                id="dueDate"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                min={new Date().toISOString().split('T')[0]}
              />
            </div>

            {/* Email Customization */}
            <fieldset className="border-t pt-4 mt-4">
              <legend className="flex items-center gap-2 mb-3">
                <Mail className="h-4 w-4 text-gray-500" aria-hidden="true" />
                <span className="text-sm font-medium">Email Customization (Optional)</span>
              </legend>
              <div className="space-y-3">
                <div>
                  <Input
                    id="email-subject"
                    placeholder="Custom email subject..."
                    value={emailSubject}
                    onChange={(e) => setEmailSubject(e.target.value)}
                    aria-label="Custom email subject (optional)"
                  />
                </div>
                <div>
                  <Textarea
                    id="email-message"
                    placeholder="Add a personal message to the payment request email..."
                    value={emailMessage}
                    onChange={(e) => setEmailMessage(e.target.value)}
                    rows={2}
                    aria-label="Custom message (optional)"
                  />
                </div>
              </div>
            </fieldset>
          </div>
        )}

        {step === 'confirm' && (
          <div className="space-y-4 py-4">
            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-3">
              <h3 className="font-medium text-sm text-gray-700 dark:text-gray-300">Payment Link Summary</h3>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Amount:</span>
                  <span className="font-semibold text-lg">${parseFloat(amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Description:</span>
                  <span>{description || `Payment to ${vendorName}`}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Payment from:</span>
                  <span>{paymentFlow === 'couple_to_vendor' ? (coupleNames || 'Couple') : (plannerName || 'You')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Payment to:</span>
                  <span>{vendorName}</span>
                </div>
                {dueDate && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Due date:</span>
                    <span>{formatAdminDate(dueDate)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Send Immediately Toggle */}
            <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <div>
                <div className="font-medium text-sm">Send immediately</div>
                <div className="text-xs text-gray-500">
                  Email payment link to {paymentFlow === 'couple_to_vendor' ? (coupleEmail || 'couple') : (plannerEmail || 'you')}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSendImmediately(!sendImmediately)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  sendImmediately ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    sendImmediately ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 text-sm p-3 rounded-md">
              <strong>Note:</strong> Payment links are powered by Stripe. The payer will receive a secure link to complete payment via credit card or bank transfer.
            </div>
          </div>
        )}

        <DialogFooter>
          {step === 'details' ? (
            <>
              <Button variant="outline" onClick={handleClose} disabled={loading}>
                Cancel
              </Button>
              <Button onClick={handleNext} disabled={!amount}>
                Continue
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setStep('details')} disabled={loading}>
                Back
              </Button>
              <Button onClick={handleCreatePaymentLink} disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4 mr-2" />
                    {sendImmediately ? 'Create & Send' : 'Create Link'}
                  </>
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
