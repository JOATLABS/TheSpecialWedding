"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Loader2, DollarSign, Plus, Send, Calendar, CheckCircle2, Clock, AlertCircle, CreditCard } from 'lucide-react';
import { toast } from 'sonner';
import { formatAdminDate, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import {
  createPaymentLink,
  sendPaymentLink,
} from '@/services/vendorManagementApi';
import {
  getPaymentMilestones,
  createPaymentMilestones,
  recordPayment,
  getPaymentStatusColor,
  type PaymentMilestone,
} from '@/services/vendorContractsApi';

interface PaymentMilestonesProps {
  token: string;
  contractId?: string;
  weddingId?: string;
  vendorName?: string;
  vendorEmail?: string;
  coupleEmail?: string;
  coupleNames?: string;
  plannerEmail?: string;
  plannerName?: string;
  totalAmount?: number;
  readOnly?: boolean;
  onMilestoneUpdated?: () => void;
}

export function PaymentMilestones({
  token,
  contractId,
  weddingId,
  vendorName,
  vendorEmail,
  coupleEmail,
  coupleNames,
  plannerEmail,
  plannerName,
  totalAmount,
  readOnly = false,
  onMilestoneUpdated,
}: PaymentMilestonesProps) {
  const [milestones, setMilestones] = useState<PaymentMilestone[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [showRecordPaymentModal, setShowRecordPaymentModal] = useState(false);
  const [showSendLinkModal, setShowSendLinkModal] = useState(false);
  const [selectedMilestone, setSelectedMilestone] = useState<PaymentMilestone | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // New milestone form
  const [newMilestones, setNewMilestones] = useState<Array<{
    description: string;
    amount: string;
    due_date: string;
  }>>([{ description: '', amount: '', due_date: '' }]);

  // Record payment form
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('stripe');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [paymentNotes, setPaymentNotes] = useState('');

  const fetchMilestones = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getPaymentMilestones(token, { contract_id: contractId, wedding_id: weddingId });
      setMilestones(data);
    } catch (error) {
      console.error('Error fetching milestones:', error);
    } finally {
      setLoading(false);
    }
  }, [token, contractId, weddingId]);

  // Fetch milestones
  useEffect(() => {
    fetchMilestones();
  }, [fetchMilestones]);

  const handleAddMilestone = () => {
    setNewMilestones([...newMilestones, { description: '', amount: '', due_date: '' }]);
  };

  const handleRemoveMilestone = (index: number) => {
    setNewMilestones(newMilestones.filter((_, i) => i !== index));
  };

  const handleMilestoneChange = (index: number, field: string, value: string) => {
    const updated = [...newMilestones];
    updated[index] = { ...updated[index], [field]: value };
    setNewMilestones(updated);
  };

  const handleCreateMilestones = async () => {
    if (!contractId) {
      toast.error('Contract ID is required');
      return;
    }

    const validMilestones = newMilestones.filter(m => m.description && m.amount && m.due_date);
    if (validMilestones.length === 0) {
      toast.error('Please add at least one valid milestone');
      return;
    }

    try {
      setActionLoading(true);
      await createPaymentMilestones(
        token,
        contractId,
        validMilestones.map(m => ({
          description: m.description,
          amount: parseFloat(m.amount),
          due_date: m.due_date,
        }))
      );
      toast.success(`Created ${validMilestones.length} milestone(s)`);
      setShowAddModal(false);
      setNewMilestones([{ description: '', amount: '', due_date: '' }]);
      fetchMilestones();
      if (onMilestoneUpdated) onMilestoneUpdated();
    } catch (error: any) {
      toast.error(error.message || 'Failed to create milestones');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRecordPayment = async () => {
    if (!selectedMilestone) return;

    const amount = parseFloat(paymentAmount);
    if (!amount || amount <= 0) {
      toast.error('Please enter a valid amount');
      return;
    }

    try {
      setActionLoading(true);
      await recordPayment(token, selectedMilestone._id, {
        amount,
        payment_method: paymentMethod,
        payment_date: paymentDate,
        notes: paymentNotes,
      });
      toast.success('Payment recorded successfully');
      setShowRecordPaymentModal(false);
      resetPaymentForm();
      fetchMilestones();
      if (onMilestoneUpdated) onMilestoneUpdated();
    } catch (error: any) {
      toast.error(error.message || 'Failed to record payment');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendPaymentLink = async () => {
    if (!selectedMilestone || !coupleEmail) {
      toast.error('Couple email is required to send payment link');
      return;
    }

    try {
      setActionLoading(true);

      const paymentLink = await createPaymentLink(token, {
        payer_type: 'couple',
        payer_email: coupleEmail,
        payer_name: coupleNames || 'The Couple',
        recipient_type: 'vendor',
        recipient_email: vendorEmail || selectedMilestone.vendor_email,
        recipient_name: vendorName || selectedMilestone.vendor_name,
        amount: selectedMilestone.amount - selectedMilestone.paid_amount,
        description: selectedMilestone.description,
        due_date: selectedMilestone.due_date,
        wedding_id: weddingId,
        contract_id: contractId,
        milestone_id: selectedMilestone._id,
      });

      await sendPaymentLink(token, paymentLink._id);
      toast.success(`Payment link sent to ${coupleEmail}`);
      setShowSendLinkModal(false);
      setSelectedMilestone(null);
    } catch (error: any) {
      toast.error(error.message || 'Failed to send payment link');
    } finally {
      setActionLoading(false);
    }
  };

  const resetPaymentForm = () => {
    setSelectedMilestone(null);
    setPaymentAmount('');
    setPaymentMethod('stripe');
    setPaymentDate(new Date().toISOString().split('T')[0]);
    setPaymentNotes('');
  };

  const getStatusIcon = (status: PaymentMilestone['status']) => {
    switch (status) {
      case 'paid':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'overdue':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'due':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'partial':
        return <CreditCard className="h-4 w-4 text-blue-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const formatCurrency = (amount: number, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
    }).format(amount);
  };

  const formatDateLocal = (dateStr: string) => {
    return formatAdminDate(dateStr, DEFAULT_TIMEZONE);
  };

  // Calculate totals
  const totalDue = milestones.reduce((sum, m) => sum + m.amount, 0);
  const totalPaid = milestones.reduce((sum, m) => sum + m.paid_amount, 0);
  const totalRemaining = totalDue - totalPaid;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div>
            <div className="text-sm text-gray-500">Total Due</div>
            <div className="text-lg font-semibold">{formatCurrency(totalDue)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Paid</div>
            <div className="text-lg font-semibold text-green-600">{formatCurrency(totalPaid)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Remaining</div>
            <div className="text-lg font-semibold text-orange-600">{formatCurrency(totalRemaining)}</div>
          </div>
        </div>
        {!readOnly && contractId && (
          <Button onClick={() => setShowAddModal(true)} variant="outline" size="sm">
            <Plus className="h-4 w-4 mr-1" />
            Add Milestone
          </Button>
        )}
      </div>

      {/* Progress Bar */}
      {totalDue > 0 && (
        <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="absolute h-full bg-green-500 transition-all duration-300"
            style={{ width: `${Math.min((totalPaid / totalDue) * 100, 100)}%` }}
          />
        </div>
      )}

      {/* Milestones List */}
      {milestones.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <Calendar className="h-10 w-10 mx-auto text-gray-400 mb-2" />
          <p className="text-gray-500">
            {contractId && !weddingId
              ? 'No payment milestones for this contract yet'
              : 'No payment milestones yet'}
          </p>
          {!readOnly && contractId && (
            <Button onClick={() => setShowAddModal(true)} variant="ghost" size="sm" className="mt-2">
              Add your first milestone
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {milestones.map((milestone) => (
            <div
              key={milestone._id}
              className="flex items-center justify-between p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
            >
              <div className="flex items-center gap-4">
                {getStatusIcon(milestone.status)}
                <div>
                  <div className="font-medium">{milestone.description}</div>
                  <div className="text-sm text-gray-500">
                    Due: {formatDateLocal(milestone.due_date)}
                    {milestone.vendor_name && ` • ${milestone.vendor_name}`}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="font-semibold">{formatCurrency(milestone.amount)}</div>
                  {milestone.paid_amount > 0 && milestone.paid_amount < milestone.amount && (
                    <div className="text-sm text-green-600">
                      Paid: {formatCurrency(milestone.paid_amount)}
                    </div>
                  )}
                </div>

                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getPaymentStatusColor(milestone.status)}`}>
                  {milestone.status.charAt(0).toUpperCase() + milestone.status.slice(1)}
                </span>

                {!readOnly && milestone.status !== 'paid' && (
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setSelectedMilestone(milestone);
                        setPaymentAmount(String(milestone.amount - milestone.paid_amount));
                        setShowRecordPaymentModal(true);
                      }}
                      title="Record Payment"
                    >
                      <CreditCard className="h-4 w-4" />
                    </Button>
                    {coupleEmail && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setSelectedMilestone(milestone);
                          setShowSendLinkModal(true);
                        }}
                        title="Send Payment Link"
                      >
                        <Send className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Milestones Modal */}
      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Add Payment Milestones</DialogTitle>
            <DialogDescription>
              Create payment schedule milestones for this contract
              {totalAmount && ` (Total: ${formatCurrency(totalAmount)})`}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4 max-h-96 overflow-y-auto">
            {newMilestones.map((milestone, index) => (
              <div key={index} className="p-4 border rounded-lg space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Milestone {index + 1}</span>
                  {newMilestones.length > 1 && (
                    <button
                      onClick={() => handleRemoveMilestone(index)}
                      className="text-red-500 hover:text-red-700 text-sm"
                    >
                      Remove
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <Label>Description</Label>
                    <Input
                      placeholder="e.g., Deposit, Final Payment..."
                      value={milestone.description}
                      onChange={(e) => handleMilestoneChange(index, 'description', e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>Amount</Label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <Input
                        type="number"
                        step="0.01"
                        placeholder="0.00"
                        className="pl-9"
                        value={milestone.amount}
                        onChange={(e) => handleMilestoneChange(index, 'amount', e.target.value)}
                      />
                    </div>
                  </div>
                  <div>
                    <Label>Due Date</Label>
                    <Input
                      type="date"
                      value={milestone.due_date}
                      onChange={(e) => handleMilestoneChange(index, 'due_date', e.target.value)}
                    />
                  </div>
                </div>
              </div>
            ))}

            <Button variant="outline" onClick={handleAddMilestone} className="w-full">
              <Plus className="h-4 w-4 mr-2" />
              Add Another Milestone
            </Button>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateMilestones} disabled={actionLoading}>
              {actionLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Milestones'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Record Payment Modal */}
      <Dialog open={showRecordPaymentModal} onOpenChange={setShowRecordPaymentModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Record Payment</DialogTitle>
            <DialogDescription>
              {selectedMilestone?.description} - {selectedMilestone && formatCurrency(selectedMilestone.amount)}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Payment Amount</Label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="number"
                  step="0.01"
                  className="pl-9"
                  value={paymentAmount}
                  onChange={(e) => setPaymentAmount(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Payment Method</Label>
              <select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg bg-white dark:bg-gray-800"
              >
                <option value="stripe">Stripe</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="check">Check</option>
                <option value="cash">Cash</option>
                <option value="venmo">Venmo</option>
                <option value="zelle">Zelle</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div className="space-y-2">
              <Label>Payment Date</Label>
              <Input
                type="date"
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Notes (Optional)</Label>
              <Input
                placeholder="Payment reference, confirmation number, etc."
                value={paymentNotes}
                onChange={(e) => setPaymentNotes(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRecordPaymentModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleRecordPayment} disabled={actionLoading}>
              {actionLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Recording...
                </>
              ) : (
                'Record Payment'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Send Payment Link Modal */}
      <Dialog open={showSendLinkModal} onOpenChange={setShowSendLinkModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Send Payment Link</DialogTitle>
            <DialogDescription>
              Send a secure payment link to the couple for this milestone
            </DialogDescription>
          </DialogHeader>

          {selectedMilestone && (
            <div className="space-y-4 py-4">
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-500">Milestone:</span>
                  <span className="font-medium">{selectedMilestone.description}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Amount Due:</span>
                  <span className="font-semibold">
                    {formatCurrency(selectedMilestone.amount - selectedMilestone.paid_amount)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Send to:</span>
                  <span>{coupleEmail}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Recipient:</span>
                  <span>{vendorName || selectedMilestone.vendor_name}</span>
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 text-sm p-3 rounded-md">
                The couple will receive an email with a secure Stripe payment link.
                Once paid, the milestone will be automatically marked as completed.
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSendLinkModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleSendPaymentLink} disabled={actionLoading}>
              {actionLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4 mr-2" />
                  Send Payment Link
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
