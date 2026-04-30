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
    const today = new Date();
    const expectedPaymentDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
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

  it('keeps the record-payment modal open on a 409 cross-milestone-intent conflict and does not refetch', async () => {
    let fetchCount = 0;
    let milestoneUpdatedCount = 0;
    let recordPaymentCalls = 0;
    const warningCalls: Array<unknown> = [];
    const messageCalls: Array<unknown> = [];
    const errorCalls: Array<unknown> = [];
    // beforeEach has installed mock.method handlers for toast.success/error.
    // For this test we need to *capture* warning + message + error invocations,
    // so we restore-all (clearing those mocks) and then plant fresh capturing
    // implementations via direct property assignment (sonner's `toast` is an
    // ordinary object built with Object.assign, so its method properties are
    // writable). afterEach calls mock.restoreAll() and cleanup() which keeps
    // the rest of the suite's mocking model intact.
    mock.restoreAll();
    const originalWarning = toast.warning;
    const originalMessage = toast.message;
    const originalError = toast.error;
    (toast as any).warning = (msg: unknown) => {
      warningCalls.push(msg);
      return undefined as any;
    };
    (toast as any).message = (msg: unknown) => {
      messageCalls.push(msg);
      return undefined as any;
    };
    (toast as any).error = (msg: unknown) => {
      errorCalls.push(msg);
      return undefined as any;
    };
    // tsx loads CJS vs ESM copies of sonner separately, so the toast object
    // the component sees (via static `import { toast } from 'sonner'`) is a
    // different reference from the one the test sees (via dynamic
    // `await import('sonner')`). Mirror the overrides onto the CJS copy so
    // the component's catch block hits our capturing functions.
    try {
      const cjs = require('sonner');
      (cjs.toast as any).warning = (toast as any).warning;
      (cjs.toast as any).message = (toast as any).message;
      (cjs.toast as any).error = (toast as any).error;
    } catch {
      // If require fails, the ESM import is the only copy and the test
      // overrides are already in place on it.
    }

    const services = createServices({
      getPaymentMilestones: async () => {
        fetchCount += 1;
        return [
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
        ] as any;
      },
      recordPayment: async () => {
        recordPaymentCalls += 1;
        const err: Error & { status?: number } = new Error(
          'This Stripe payment is already recorded against another milestone'
        );
        err.status = 409;
        throw err;
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
    const fetchCountAfterInitialLoad = fetchCount;

    fireEvent.click(view.getByTitle('Record Payment'));
    fireEvent.click(view.getAllByRole('button', { name: 'Record Payment' })[1]);

    await waitFor(() => {
      assert.equal(warningCalls.length, 1);
    });
    assert.equal(recordPaymentCalls, 1);
    assert.equal(warningCalls[0], 'This payment is recorded against a different milestone');
    assert.equal(messageCalls.length, 0);
    assert.equal(errorCalls.length, 0);
    // No refetch and no callback since this is a real routing conflict.
    assert.equal(fetchCount, fetchCountAfterInitialLoad);
    assert.equal(milestoneUpdatedCount, 0);
    (toast as any).warning = originalWarning;
    (toast as any).message = originalMessage;
    (toast as any).error = originalError;
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
