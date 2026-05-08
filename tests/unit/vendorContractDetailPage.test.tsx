import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';

import { installDom } from './testDom';
import type {
  VendorContract,
  VendorContractFormDataResponse,
} from '../../app/services/vendorContractsApi';

type DetailPageModule = typeof import('../../app/admin/vendors/contracts/[id]/ContractDetailPageClient');

let ContractDetailPageRuntime: DetailPageModule['default'];
let toast: typeof import('sonner').toast;
let domHandle: ReturnType<typeof installDom> | null = null;

function makeContract(overrides: Record<string, unknown> = {}) {
  return {
    _id: 'contract_1',
    wedding_id: 'wedding_1',
    vendor_name: 'Vendor Co',
    vendor_email: 'vendor@example.com',
    service_category: 'photographer',
    custom_service_category: undefined,
    contract_title: 'Photo Contract',
    contract_number: 'VC-101',
    sections: [{ id: 'scope', title: 'Scope', content: 'Coverage', order: 0 }],
    total_amount: 5000,
    deposit_amount: 1500,
    currency: 'USD',
    status: 'draft',
    created_at: '2026-04-10T00:00:00.000Z',
    updated_at: '2026-04-10T00:00:00.000Z',
    ...overrides,
  } as VendorContract;
}

type DetailRuntimeOverrides = NonNullable<
  Parameters<DetailPageModule['default']>[0]
>['runtimeOverrides'];

function makeServices(overrides: Partial<NonNullable<DetailRuntimeOverrides>['services']> = {}) {
  return {
    getCategoryLabel: () => 'Photographer',
    getContract: async () => makeContract(),
    getContractRevisions: async () => ({
      current_contract_id: 'contract_1',
      root_contract_id: 'contract_1',
      versions: [],
    }),
    getContractActivity: async () => ({
      contract_id: 'contract_1',
      root_contract_id: 'contract_1',
      items: [],
    }),
    updateContract: async () => makeContract(),
    sendContract: async () => ({ sent_to: 'vendor@example.com' }),
    createContractRevision: async () => ({ _id: 'contract_2' }),
    duplicateContract: async () => makeContract({ _id: 'contract_dup' }),
    getContractFormData: async () => ({
      vendor_submissions: [],
      available_fields: {},
      suggested_contract_fields: {},
    }),
    applyFormDataToContract: async () => makeContract(),
    ...overrides,
  } as NonNullable<NonNullable<DetailRuntimeOverrides>['services']>;
}

function PaymentMilestonesStub(props: any) {
  return (
    <div data-testid="payment-milestones">
      PaymentMilestones stub readOnly={String(Boolean(props.readOnly))}
    </div>
  );
}

describe('ContractDetailPage runtime', () => {
  before(async () => {
    domHandle = installDom();
    ({ default: ContractDetailPageRuntime } = await import('../../app/admin/vendors/contracts/[id]/ContractDetailPageClient'));
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

  it('renders historical versions as inspect-only and passes readOnly payments mode', async () => {
    const services = makeServices({
      getContract: async () =>
        makeContract({
          status: 'signed',
          is_current_version: false,
          version_number: 1,
          contract_kind: 'original',
        }),
    });

    const view = render(
      <ContractDetailPageRuntime
        runtimeOverrides={{
          token: 'admin-token',
          contractId: 'contract_1',
          router: { push: () => undefined },
          services,
          PaymentMilestonesComponent: PaymentMilestonesStub as any,
        }}
      />
    );

    await view.findByRole('heading', { name: 'Photo Contract' });
    view.getByText('This is a historical contract version.');
    assert.equal(view.queryByRole('button', { name: 'Edit' }), null);
    assert.equal(view.queryByRole('button', { name: 'Send to Vendor' }), null);
    assert.equal(view.queryByRole('button', { name: /Create Revision|Create Amendment/ }), null);

    fireEvent.click(view.getByRole('button', { name: 'Payments' }));
    await view.findByTestId('payment-milestones');
    view.getByText('PaymentMilestones stub readOnly=true');
  });

  it('shows revision history in the sidebar and activity in the activity tab for current contracts', async () => {
    const services = makeServices({
      getContract: async () =>
        makeContract({
          status: 'sent',
          is_current_version: true,
          version_number: 2,
          contract_kind: 'revision',
          sent_at: '2026-04-11T12:00:00.000Z',
        }),
      getContractRevisions: async () => ({
        current_contract_id: 'contract_1',
        root_contract_id: 'contract_1',
        versions: [
          {
            id: 'contract_1',
            contract_number: 'VC-101',
            version_number: 2,
            contract_kind: 'revision',
            status: 'sent',
            is_current_version: true,
            created_at: '2026-04-11T00:00:00.000Z',
          },
          {
            id: 'contract_0',
            contract_number: 'VC-100',
            version_number: 1,
            contract_kind: 'original',
            status: 'signed',
            is_current_version: false,
            created_at: '2026-04-10T00:00:00.000Z',
          },
        ],
      }),
      getContractActivity: async () => ({
        contract_id: 'contract_1',
        root_contract_id: 'contract_1',
        items: [
          {
            id: 'activity_1',
            contract_id: 'contract_1',
            root_contract_id: 'contract_1',
            activity_type: 'contract_sent',
            title: 'Contract sent',
            description: 'Sent to vendor@example.com',
            actor: {
              type: 'planner',
              identifier: 'planner@example.com',
              display_name: 'Planner Name',
            },
            metadata: {},
            created_at: '2026-04-11T12:00:00.000Z',
          },
        ],
      }),
    });

    const view = render(
      <ContractDetailPageRuntime
        runtimeOverrides={{
          token: 'admin-token',
          contractId: 'contract_1',
          router: { push: () => undefined },
          services,
          PaymentMilestonesComponent: PaymentMilestonesStub as any,
        }}
      />
    );

    await view.findByRole('heading', { name: 'Photo Contract' });
    view.getByText('Version History');
    assert.ok(view.getAllByText('Version 2').length >= 1);
    assert.ok(view.getAllByText('Version 1').length >= 1);
    view.getByRole('button', { name: 'Create Revision' });
    assert.equal(view.queryByRole('button', { name: 'Send to Vendor' }), null);

    fireEvent.click(view.getByRole('button', { name: 'Activity' }));
    await view.findByText('Contract sent');
    view.getByText('Sent to vendor@example.com');
    view.getByText('Planner Name');
    assert.equal(view.queryByText('Version History'), null);
  });

  it('shows send controls for live drafts and hides revision creation until after send', async () => {
    const services = makeServices({
      getContract: async () =>
        makeContract({
          status: 'draft',
          is_current_version: true,
          version_number: 1,
          contract_kind: 'original',
        }),
    });

    const view = render(
      <ContractDetailPageRuntime
        runtimeOverrides={{
          token: 'admin-token',
          contractId: 'contract_1',
          router: { push: () => undefined },
          services,
          PaymentMilestonesComponent: PaymentMilestonesStub as any,
        }}
      />
    );

    await view.findByRole('heading', { name: 'Photo Contract' });
    view.getByRole('button', { name: 'Edit' });
    view.getByRole('button', { name: 'Send to Vendor' });
    assert.equal(view.queryByRole('button', { name: /Create Revision|Create Amendment/ }), null);
  });

  it('applies vendor form data and refreshes the editable contract state from the returned contract', async () => {
    const services = makeServices({
      getContract: async () =>
        makeContract({
          contract_title: 'Original Contract Title',
        }),
      getContractFormData: async () => ({
        vendor_submissions: [
          {
            _id: 'submission_1',
            form_name: 'Vendor Intake',
            submitted_at: '2026-04-10T00:00:00.000Z',
            source: 'vendor_form',
            data: { venue_name: 'Updated Venue' },
          },
        ],
        available_fields: {},
        suggested_contract_fields: {
          '{{venue_name}}': {
            source_field: 'venue_name',
            value: 'Updated Venue',
          },
        },
      } satisfies VendorContractFormDataResponse),
      applyFormDataToContract: async () =>
        makeContract({
          contract_title: 'Updated Contract Title',
        }),
    });

    const view = render(
      <ContractDetailPageRuntime
        runtimeOverrides={{
          token: 'admin-token',
          contractId: 'contract_1',
          router: { push: () => undefined },
          services,
          PaymentMilestonesComponent: PaymentMilestonesStub as any,
        }}
      />
    );

    await view.findByRole('heading', { name: 'Original Contract Title' });
    fireEvent.click(view.getByRole('button', { name: 'View & Apply Form Data' }));

    await waitFor(() => {
      view.getByRole('heading', { name: 'Updated Contract Title' });
    });
  });
});
