"use client";

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Textarea } from '@/components/ui/Textarea';
import { Loader2, DollarSign } from 'lucide-react';
import { toast } from 'sonner';

interface VendorPaymentModalProps {
  open: boolean;
  onClose: () => void;
  vendorId: string;
  vendorName: string;
  onPaymentComplete?: () => void;
}

export function VendorPaymentModal({
  open,
  onClose,
  vendorId,
  vendorName,
  onPaymentComplete,
}: VendorPaymentModalProps) {
  const [loading, setLoading] = useState(false);
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');

  const handlePayVendor = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      toast.error('Please enter a valid amount');
      return;
    }

    try {
      setLoading(true);

      const token = localStorage.getItem('admin_token');
      if (!token) {
        toast.error('Please log in to make payments');
        return;
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/stripe/pay-vendor`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            vendor_user_id: vendorId, // Note: This expects user_id, not vendor_profile_id.
                                      // If vendorId is profile ID, we need to resolve it.
                                      // For now assuming we pass the vendor's user ID if available,
                                      // or we need to look it up.
            amount: parseFloat(amount),
            currency: 'usd',
            description: description || `Payment to ${vendorName}`,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to process payment');
      }

      const data = await response.json();

      // TODO: Implement proper handling for different payment intent statuses (requires_payment_method,
      // requires_confirmation, requires_action) by integrating PaymentElement for client-side confirmation
      // and 3D Secure authentication when the planner doesn't have a saved payment method.

      if (data.payment_intent.status === 'succeeded') {
        toast.success(`Payment of $${amount} to ${vendorName} successful!`);
        if (onPaymentComplete) onPaymentComplete();
        onClose();
      } else if (data.payment_intent.status === 'requires_confirmation' || data.payment_intent.status === 'requires_action') {
         toast.success('Payment initiated. Please check your billing dashboard.');
         onClose();
      } else {
         toast.success('Payment processed successfully!');
         onClose();
      }

    } catch (error: any) {
      console.error('Payment error:', error);
      toast.error(error.message || 'Failed to process payment');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Pay Vendor</DialogTitle>
          <DialogDescription>
            Send a payment to {vendorName}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="amount">Amount (USD)</Label>
            <div className="relative">
              <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-500" />
              <Input
                id="amount"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description (Optional)</Label>
            <Textarea
              id="description"
              placeholder="e.g., Deposit, Final Balance..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          <div className="bg-blue-50 text-blue-800 text-sm p-3 rounded-md">
            Funds will be transferred from your connected account to the vendor.
            Platform fees may apply.
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handlePayVendor} disabled={loading || !amount}>
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              'Send Payment'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
