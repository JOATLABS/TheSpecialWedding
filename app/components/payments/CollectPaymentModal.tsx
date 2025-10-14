"use client";

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Loader2, DollarSign } from 'lucide-react';
import { toast } from 'sonner';

interface CollectPaymentModalProps {
  open: boolean;
  onClose: () => void;
  weddingId: string;
  weddingTitle: string;
  onPaymentCreated?: (paymentIntent: any) => void;
}

export function CollectPaymentModal({
  open,
  onClose,
  weddingId,
  weddingTitle,
  onPaymentCreated,
}: CollectPaymentModalProps) {
  const [loading, setLoading] = useState(false);
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [paymentLink, setPaymentLink] = useState('');

  const handleCreatePayment = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      toast.error('Please enter a valid amount');
      return;
    }

    try {
      setLoading(true);

      const token = localStorage.getItem('authToken');
      if (!token) {
        toast.error('Please log in to create payment requests');
        return;
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/stripe/create-payment-intent`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify({
            amount: parseFloat(amount),
            currency: 'usd',
            wedding_id: weddingId,
            description: description || `Payment for ${weddingTitle}`,
            metadata: {
              wedding_title: weddingTitle,
              payment_type: 'wedding_services',
            },
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create payment request');
      }

      const data = await response.json();
      const paymentIntent = data.payment_intent;

      // Generate payment link (you'll need to create a payment page)
      const link = `${window.location.origin}/pay/${paymentIntent.payment_intent_id}`;
      setPaymentLink(link);

      toast.success('Payment request created successfully!');

      if (onPaymentCreated) {
        onPaymentCreated(paymentIntent);
      }

      // Copy to clipboard
      navigator.clipboard.writeText(link);
      toast.success('Payment link copied to clipboard!');
    } catch (error: any) {
      console.error('Payment creation error:', error);
      toast.error(error.message || 'Failed to create payment request');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setAmount('');
    setDescription('');
    setPaymentLink('');
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Collect Payment from Couple</DialogTitle>
          <DialogDescription>
            Create a payment request for {weddingTitle}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {!paymentLink ? (
            <>
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
                <p className="text-sm text-gray-500">
                  Enter the amount you want to collect from the couple
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description (Optional)</Label>
                <Textarea
                  id="description"
                  placeholder="e.g., Final payment for wedding services, Deposit for venue..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                />
              </div>
            </>
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg bg-green-50 dark:bg-green-900/20 p-4 border border-green-200 dark:border-green-800">
                <h4 className="font-semibold text-green-900 dark:text-green-100 mb-2">
                  Payment Link Created!
                </h4>
                <p className="text-sm text-green-700 dark:text-green-300 mb-3">
                  Share this link with your couple to collect ${parseFloat(amount).toFixed(2)}
                </p>
                <div className="bg-white dark:bg-gray-800 p-3 rounded border break-all text-sm font-mono">
                  {paymentLink}
                </div>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => {
                    navigator.clipboard.writeText(paymentLink);
                    toast.success('Link copied!');
                  }}
                >
                  Copy Link
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => {
                    window.open(`mailto:?subject=Payment Request for ${weddingTitle}&body=Please complete your payment using this link: ${paymentLink}`, '_blank');
                  }}
                >
                  Email Link
                </Button>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          {!paymentLink ? (
            <>
              <Button variant="outline" onClick={handleClose} disabled={loading}>
                Cancel
              </Button>
              <Button onClick={handleCreatePayment} disabled={loading || !amount}>
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Creating...
                  </>
                ) : (
                  'Create Payment Request'
                )}
              </Button>
            </>
          ) : (
            <Button onClick={handleClose} className="w-full">
              Done
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
