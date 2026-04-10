import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';

import { installDom } from './testDom';
import type { PaymentMilestonesServices } from '../../app/admin/vendors/components/PaymentMilestones';
import type {
  PaymentMilestone,
  PaymentMilestoneInput,
  RecordVendorMilestonePaymentRequest,
} from '../../app/services/vendorContractsApi';
import type { PaymentLink } from '../../app/services/vendorManagementApi';

type PaymentMilestonesModule = typeof import('../../app/admin/vendors/components/PaymentMilestones');

let PaymentMilestones: PaymentMilestonesModule['PaymentMilestones'];
let toast: typeof import('sonner').toast;
let domHandle: ReturnType<typeof installDom> | null = null;

function createServices(overrides: Partial<PaymentMilestonesServices> = {}) {
  return {
    getPaymentMilestones: async () => [] as PaymentMilestone[],
    createPaymentMilestones: async () => [],
    recordPayment: async () =>
      ({
        _id: 'milestone_1',
        contract_id: 'contract_1',
        wedding_id: 'wedding_1',
        description: 'Deposit',
        amount: 1500,
        currency: 'USD',
        due_date: '2026-05-01',
        status: 'paid',
        paid_amount: 1500,
        vendor_name: 'Vendor Co',
        vendor_email: 'vendor@example.com',
      }) as PaymentMilestone,
    createPaymentLink: async () =>
      ({
        _id: 'payment_link_1',
        payer_type: 'couple',
        payer_email: 'couple@example.com',
        payer_name: 'Alex and Sam',
        recipient_type: 'vendor',
        recipient_email: 'vendor@example.com',
        recipient_name: 'Vendor Co',
        amount: 1500,
        currency: 'USD',
        description: 'Deposit',
        status: 'draft',
        created_at: '2026-04-10T00:00:00.000Z',
      }) as PaymentLink,
    sendPaymentLink: async () => ({ message: 'Sent', sent_to: 'couple@example.com' }),
    ...overrides,
  } satisfies PaymentMilestonesServices;
}

describe('PaymentMilestones', () => {
  before(async () => {
    domHandle = installDom();
    ({ PaymentMilestones } = await import('../../app/admin/vendors/components/PaymentMilestones'));
    ({ toast } = await import('sonner'));
  });

  beforeEach(() => {
    mock.restoreAll();
    mock.method(toast, 'success', () => undefined);
    mock.method(toast, 'error', () => undefined);
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
  });

  after(() => {
    domHandle = null;
  });

  it('uses the contract-scoped fetch path and renders the contract empty state', async () => {
    const getPaymentMilestonesCalls: Array<Record<string, string | undefined>> = [];
    const services = createServices({
      getPaymentMilestones: async (
        _token: string,
        query?: { contract_id?: string; wedding_id?: string; status?: string }
      ) => {
        getPaymentMilestonesCalls.push({
          contract_id: query?.contract_id,
          wedding_id: query?.wedding_id,
        });
        return [];
      },
    });

    const view = render(
      <PaymentMilestones
        token="admin-token"
        contractId="contract_1"
        readOnly
        services={services}
      />
    );

    await view.findByText('No payment milestones for this contract yet');
    assert.deepEqual(getPaymentMilestonesCalls, [{ contract_id: 'contract_1', wedding_id: undefined }]);
    assert.equal(view.queryByRole('button', { name: 'Add Milestone' }), null);
  });

  it('creates contract milestones and fires the update callback', async () => {
    let fetchCount = 0;
    const createCalls: Array<unknown> = [];
    let milestoneUpdatedCount = 0;
    const services = createServices({
      getPaymentMilestones: async () => {
        fetchCount += 1;
        if (fetchCount === 1) {
          return [];
        }

        return [
          {
            _id: 'milestone_1',
            description: 'Deposit',
            amount: 1500,
            due_date: '2026-05-01',
            paid_amount: 0,
            status: 'pending',
            vendor_name: 'Vendor Co',
            vendor_email: 'vendor@example.com',
          },
        ] as any;
      },
      createPaymentMilestones: async (
        _token: string,
        contractId: string,
        milestones: PaymentMilestoneInput[]
      ) => {
        createCalls.push({ contractId, milestones });
        return [];
      },
    });

    const view = render(
      <PaymentMilestones
        token="admin-token"
        contractId="contract_1"
        totalAmount={5000}
        initialNewMilestones={[
          { description: 'Deposit', amount: '1500', due_date: '2026-05-01' },
        ]}
        onMilestoneUpdated={() => {
          milestoneUpdatedCount += 1;
        }}
        services={services}
      />
    );

    await view.findByText('No payment milestones for this contract yet');
    fireEvent.click(view.getByRole('button', { name: 'Add your first milestone' }));
    await view.findByText('Add Payment Milestones');
    fireEvent.click(view.getByRole('button', { name: 'Create Milestones' }));

    await waitFor(() => {
      assert.equal(createCalls.length, 1);
    });
    assert.deepEqual(createCalls[0], {
      contractId: 'contract_1',
      milestones: [
        {
          description: 'Deposit',
          amount: 1500,
          due_date: '2026-05-01',
        },
      ],
    });

    await view.findByText('Deposit');
    assert.equal(milestoneUpdatedCount, 1);
  });

  it('records payments, fires the update callback, and gates payment-link actions without couple email', async () => {
    const recordCalls: Array<unknown> = [];
    let milestoneUpdatedCount = 0;
    const expectedPaymentDate = new Date().toISOString().split('T')[0];
    const services = createServices({
      getPaymentMilestones: async () =>
        [
          {
            _id: 'milestone_1',
            description: 'Final Payment',
            amount: 3500,
            due_date: '2026-06-01',
            paid_amount: 0,
            status: 'pending',
            vendor_name: 'Vendor Co',
            vendor_email: 'vendor@example.com',
          },
        ] as any,
      recordPayment: async (
        _token: string,
        milestoneId: string,
        payload: RecordVendorMilestonePaymentRequest
      ) => {
        recordCalls.push({ milestoneId, payload });
        return { _id: milestoneId } as any;
      },
    });

    const view = render(
      <PaymentMilestones
        token="admin-token"
        contractId="contract_1"
        vendorName="Vendor Co"
        vendorEmail="vendor@example.com"
        onMilestoneUpdated={() => {
          milestoneUpdatedCount += 1;
        }}
        services={services}
      />
    );

    await view.findByText('Final Payment');
    assert.equal(view.queryByTitle('Send Payment Link'), null);

    fireEvent.click(view.getByTitle('Record Payment'));
    fireEvent.click(view.getAllByRole('button', { name: 'Record Payment' })[1]);

    await waitFor(() => {
      assert.equal(recordCalls.length, 1);
    });
    assert.deepEqual(recordCalls[0], {
      milestoneId: 'milestone_1',
      payload: {
        amount: 3500,
        payment_method: 'stripe',
        payment_date: expectedPaymentDate,
        notes: '',
      },
    });
    assert.equal(milestoneUpdatedCount, 1);
  });

  it('disables operational payment actions in read-only mode', async () => {
    const services = createServices({
      getPaymentMilestones: async () =>
        [
          {
            _id: 'milestone_1',
            description: 'Deposit',
            amount: 1500,
            due_date: '2026-05-01',
            paid_amount: 0,
            status: 'pending',
            vendor_name: 'Vendor Co',
            vendor_email: 'vendor@example.com',
          },
        ] as any,
    });

    const view = render(
      <PaymentMilestones
        token="admin-token"
        contractId="contract_1"
        readOnly
        services={services}
      />
    );

    await view.findByText('Deposit');
    assert.equal(view.queryByRole('button', { name: 'Add Milestone' }), null);
    assert.equal(view.queryByTitle('Record Payment'), null);
    assert.equal(view.queryByTitle('Send Payment Link'), null);
  });
});
