import type { PaymentMilestone } from '@/services/vendorContractsApi';

export interface PaymentMilestonesSummary {
  totalDue: number;
  totalPaid: number;
  totalRemaining: number;
}

export function buildPaymentMilestonesQuery(
  contractId?: string,
  weddingId?: string
): {
  contract_id?: string;
  wedding_id?: string;
} {
  return {
    contract_id: contractId,
    wedding_id: weddingId,
  };
}

export function calculatePaymentMilestonesSummary(
  milestones: PaymentMilestone[]
): PaymentMilestonesSummary {
  const totalDue = milestones.reduce((sum, milestone) => sum + milestone.amount, 0);
  const totalPaid = milestones.reduce((sum, milestone) => sum + milestone.paid_amount, 0);

  return {
    totalDue,
    totalPaid,
    totalRemaining: totalDue - totalPaid,
  };
}

export function getPaymentMilestonesEmptyStateMessage(
  contractId?: string,
  weddingId?: string
): string {
  if (contractId && !weddingId) {
    return 'No payment milestones for this contract yet';
  }

  return 'No payment milestones yet';
}

export function canAddPaymentMilestones(readOnly: boolean, contractId?: string): boolean {
  return !readOnly && !!contractId;
}

export function canRecordPaymentForMilestone(
  readOnly: boolean,
  milestone: Pick<PaymentMilestone, 'status'>
): boolean {
  return !readOnly && milestone.status !== 'paid';
}

export function canSendPaymentLinkForMilestone(
  readOnly: boolean,
  coupleEmail: string | undefined,
  milestone: Pick<PaymentMilestone, 'status'>
): boolean {
  return canRecordPaymentForMilestone(readOnly, milestone) && !!coupleEmail;
}
