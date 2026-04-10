import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
  buildPaymentMilestonesQuery,
  calculatePaymentMilestonesSummary,
  canAddPaymentMilestones,
  canRecordPaymentForMilestone,
  canSendPaymentLinkForMilestone,
  getPaymentMilestonesEmptyStateMessage,
} from '../../app/admin/vendors/components/paymentMilestonesViewState';

const PAYMENT_MILESTONES_SOURCE = readFileSync(
  resolve(process.cwd(), 'app/admin/vendors/components/PaymentMilestones.tsx'),
  'utf8'
);

describe('payment milestones contract view state', () => {
  it('builds contract-scoped fetch params without requiring a wedding id', () => {
    assert.deepEqual(buildPaymentMilestonesQuery('contract_1', undefined), {
      contract_id: 'contract_1',
      wedding_id: undefined,
    });
  });

  it('calculates totals and remaining balance correctly', () => {
    const summary = calculatePaymentMilestonesSummary([
      { amount: 2000, paid_amount: 500 } as any,
      { amount: 3000, paid_amount: 3000 } as any,
    ]);

    assert.deepEqual(summary, {
      totalDue: 5000,
      totalPaid: 3500,
      totalRemaining: 1500,
    });
  });

  it('uses the contract-specific empty state copy when only contract scope is present', () => {
    assert.equal(
      getPaymentMilestonesEmptyStateMessage('contract_1', undefined),
      'No payment milestones for this contract yet'
    );
    assert.equal(
      getPaymentMilestonesEmptyStateMessage(undefined, 'wedding_1'),
      'No payment milestones yet'
    );
  });

  it('disables add, pay, and send-link actions in read-only mode', () => {
    const milestone = { status: 'pending' } as any;

    assert.equal(canAddPaymentMilestones(true, 'contract_1'), false);
    assert.equal(canRecordPaymentForMilestone(true, milestone), false);
    assert.equal(
      canSendPaymentLinkForMilestone(true, 'couple@example.com', milestone),
      false
    );
  });

  it('keeps payment link actions gated behind both milestone status and couple email', () => {
    assert.equal(
      canSendPaymentLinkForMilestone(false, 'couple@example.com', { status: 'pending' } as any),
      true
    );
    assert.equal(
      canSendPaymentLinkForMilestone(false, undefined, { status: 'pending' } as any),
      false
    );
    assert.equal(
      canSendPaymentLinkForMilestone(false, 'couple@example.com', { status: 'paid' } as any),
      false
    );
  });

  it('keeps milestone update callbacks and contract query helpers wired in the component source', () => {
    assert.match(PAYMENT_MILESTONES_SOURCE, /buildPaymentMilestonesQuery\(contractId, weddingId\)/);
    assert.match(PAYMENT_MILESTONES_SOURCE, /if \(onMilestoneUpdated\) onMilestoneUpdated\(\);/);
    assert.match(PAYMENT_MILESTONES_SOURCE, /canSendPaymentLinkForMilestone/);
  });
});
