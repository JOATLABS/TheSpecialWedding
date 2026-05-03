"use client";

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Textarea } from '@/components/ui/Textarea';
import { useAdmin } from '@/contexts/AdminContext';
import { Loader2, DollarSign } from 'lucide-react';
import { toast } from 'sonner';
import { getApiBaseUrl } from '@/utils/env';

interface Wedding {
  _id: string;
  title: string;
}

interface CollectPaymentModalProps {
  open: boolean;
  onClose: () => void;
  weddingId?: string;
  weddingTitle?: string;
  onPaymentCreated?: (paymentIntent: any) => void;
}

export function CollectPaymentModal({
  open,
  onClose,
  weddingId,
  weddingTitle,
  onPaymentCreated,
}: CollectPaymentModalProps) {
  const { token } = useAdmin();
  const apiBaseUrl = getApiBaseUrl();
  const [loading, setLoading] = useState(false);
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [paymentLink, setPaymentLink] = useState('');
  const [createdPaymentRequest, setCreatedPaymentRequest] = useState<any | null>(null);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWeddingId, setSelectedWeddingId] = useState<string>(weddingId || '');
  const [fetchingWeddings, setFetchingWeddings] = useState(false);

  const copyPaymentLink = async (link: string) => {
    if (!link) {
      return false;
    }

    if (!navigator?.clipboard?.writeText) {
      return false;
    }

    try {
      await navigator.clipboard.writeText(link);
      return true;
    } catch (error) {
      console.warn('Clipboard copy failed for payment link', error);
      return false;
    }
  };

  // Fetch weddings if not provided
  React.useEffect(() => {
    if (!weddingId && open) {
      const fetchWeddings = async () => {
        setFetchingWeddings(true);
        try {
          if (!token) return;
          const response = await fetch(`${apiBaseUrl}/admin/weddings`, {
             headers: { 'Authorization': `Bearer ${token}` },
             credentials: 'include',
          });
          if (response.ok) {
            const data = await response.json();
            setWeddings(data.weddings || data);
          }
        } catch (e) {
          console.error("Failed to fetch weddings", e);
        } finally {
          setFetchingWeddings(false);
        }
      };
      fetchWeddings();
    }
  }, [apiBaseUrl, token, weddingId, open]);

  // Reset transient state every time the modal opens. Previously we only
  // reset on close, which left stale paymentLink / createdPaymentRequest /
  // selectedWeddingId visible if `open` toggled false→true via the parent
  // without going through handleClose.
  React.useEffect(() => {
    if (open) {
      setAmount('');
      setDescription('');
      setPaymentLink('');
      setCreatedPaymentRequest(null);
      setSelectedWeddingId(weddingId || '');
    }
  }, [open, weddingId]);

  // Resolve the wedding title to display in copy. Prefer the explicit prop;
  // otherwise look up the row the user picked. Without this fallback,
  // copy/markup like "Create a payment request for {weddingTitle}" renders
  // as a half-finished sentence when the modal is opened from the billing
  // page (no preselected wedding).
  const resolvedWeddingId = weddingId || selectedWeddingId;
  const resolvedWeddingTitle =
    weddingTitle ||
    weddings.find((w) => w._id === resolvedWeddingId)?.title ||
    '';

  const handleCreatePayment = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      toast.error('Please enter a valid amount');
      return;
    }

    const finalWeddingId = weddingId || selectedWeddingId;
    if (!finalWeddingId) {
      toast.error('Please select the wedding this payment request belongs to');
      return;
    }

    const selectedWedding = weddings.find(w => w._id === finalWeddingId);
    const finalWeddingTitle = weddingTitle || selectedWedding?.title || 'Wedding Services';

    try {
      setLoading(true);

      if (!token) {
        toast.error('Please log in to create payment requests');
        return;
      }

      const response = await fetch(
        `${apiBaseUrl}/stripe/create-payment-intent`,
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
            wedding_id: finalWeddingId || undefined,
            description: description || `Payment for ${finalWeddingTitle}`,
            metadata: {
              wedding_title: finalWeddingTitle,
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
      const publicToken = paymentIntent.public_token;

      if (!publicToken) {
        throw new Error('Payment request token was not returned');
      }

      const link = `${window.location.origin}/pay/${publicToken}`;
      setPaymentLink(link);

      toast.success('Payment request created successfully!');

      setCreatedPaymentRequest(paymentIntent);
      // Notify the parent exactly once, on successful creation. We used to
      // call this from handleClose, which fired on every close (including
      // cancel) and could fire with a stale createdPaymentRequest if the
      // open prop toggled outside the dialog's own flow.
      onPaymentCreated?.(paymentIntent);

      const copiedToClipboard = await copyPaymentLink(link);
      if (copiedToClipboard) {
        toast.success('Payment link copied to clipboard!');
      } else {
        toast.info('Payment link is ready. Copy it from the dialog.');
      }
    } catch (error: any) {
      console.error('Payment creation error:', error);
      toast.error(error.message || 'Failed to create payment request');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    // State reset happens in the open-transition effect; handleClose just
    // delegates to the parent. (Reset-on-close was unsafe because parents
    // can flip `open` back to false without calling this handler.)
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Request a payment</DialogTitle>
          <DialogDescription>
            {resolvedWeddingTitle
              ? `Create a payment request for ${resolvedWeddingTitle}.`
              : 'Create a payment request for one of your couples.'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {!paymentLink ? (
            <>
              {!weddingId && (
                <div className="space-y-2">
                  <Label htmlFor="wedding">Wedding</Label>
                  <select
                    id="wedding"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    value={selectedWeddingId}
                    onChange={(e) => setSelectedWeddingId(e.target.value)}
                    disabled={fetchingWeddings}
                  >
                    <option value="">Choose a wedding…</option>
                    {weddings.map((w) => (
                      <option key={w._id} value={w._id}>
                        {w.title}
                      </option>
                    ))}
                  </select>
                  <p className="text-sm text-gray-500">
                    Tied to one wedding so the couple sees the right invoice.
                  </p>
                </div>
              )}

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
                  Couples see this on their payment page.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description (Optional)</Label>
                <Textarea
                  id="description"
                  placeholder="e.g., Final balance — Davis wedding"
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
                  Link ready to share
                </h4>
                <p className="text-sm text-green-700 dark:text-green-300 mb-3">
                  Send it to your couple to collect ${parseFloat(amount).toFixed(2)}.
                </p>
                <div className="bg-white dark:bg-gray-800 p-3 rounded border break-all text-sm font-mono">
                  {paymentLink}
                </div>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={async () => {
                    const copiedToClipboard = await copyPaymentLink(paymentLink);
                    if (copiedToClipboard) {
                      toast.success('Link copied!');
                    } else {
                      toast.error('Clipboard access is unavailable. Copy the link manually.');
                    }
                  }}
                >
                  Copy Link
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => {
                    // Fall back to a generic subject when no wedding has
                    // been resolved — prevents "Payment Request for "
                    // with a trailing space landing in the recipient's
                    // inbox.
                    const subject = resolvedWeddingTitle
                      ? `Payment Request for ${resolvedWeddingTitle}`
                      : 'Payment Request';
                    window.open(
                      `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(`Please complete your payment using this link: ${paymentLink}`)}`,
                      '_blank',
                    );
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
              <Button onClick={handleCreatePayment} disabled={loading || !amount || (!weddingId && !selectedWeddingId)}>
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
