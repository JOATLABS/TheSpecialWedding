import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
  buildContractKeyDates,
  buildEditableContractState,
  getContractDetailControlState,
  sortContractRevisionHistory,
} from '../../app/admin/vendors/contracts/contractDetailViewState';

const DETAIL_PAGE_SOURCE = readFileSync(
  resolve(process.cwd(), 'app/admin/vendors/contracts/[id]/page.tsx'),
  'utf8'
);

function makeContract(overrides: Record<string, unknown> = {}) {
  return {
    _id: 'contract_1',
    vendor_name: 'Vendor Co',
    vendor_email: 'vendor@example.com',
    service_category: 'photographer',
    contract_title: 'Photo Contract',
    sections: [{ id: 'scope', title: 'Scope', content: 'Coverage', order: 0 }],
    total_amount: 5000,
    currency: 'USD',
    status: 'draft',
    created_at: '2026-04-10T00:00:00.000Z',
    updated_at: '2026-04-10T00:00:00.000Z',
    ...overrides,
  };
}

describe('vendor contract detail page view state', () => {
  it('marks historical versions as inspect-only', () => {
    const state = getContractDetailControlState(
      makeContract({
        status: 'signed',
        is_current_version: false,
      }) as any,
      {
        current_contract_id: 'contract_2',
        root_contract_id: 'contract_1',
        versions: [],
      }
    );

    assert.equal(state.showHistoricalBanner, true);
    assert.equal(state.paymentsReadOnly, true);
    assert.equal(state.canEdit, false);
    assert.equal(state.canSend, false);
    assert.equal(state.canCreateRevision, false);
  });

  it('allows live revision drafts to remain editable and sendable', () => {
    const state = getContractDetailControlState(
      makeContract({
        status: 'draft',
        is_current_version: false,
        contract_kind: 'revision',
        supersedes_contract_id: 'contract_1',
      }) as any,
      {
        current_contract_id: 'contract_1',
        root_contract_id: 'contract_1',
        versions: [],
      }
    );

    assert.equal(state.canEdit, true);
    assert.equal(state.canSend, true);
    assert.equal(state.canCreateRevision, false);
  });

  it('uses amendment wording for signed current versions', () => {
    const signedState = getContractDetailControlState(
      makeContract({
        status: 'signed',
        is_current_version: true,
      }) as any,
      null
    );

    assert.equal(signedState.defaultRevisionLabel, 'Create Amendment');
    assert.equal(signedState.canCreateRevision, true);
  });

  it('builds key dates in contract lifecycle order', () => {
    const dates = buildContractKeyDates(
      makeContract({
        sent_at: '2026-04-11T00:00:00.000Z',
        viewed_at: '2026-04-12T00:00:00.000Z',
        signed_at: '2026-04-13T00:00:00.000Z',
      }) as any
    );

    assert.deepEqual(
      dates.map((item) => item.label),
      ['Created', 'Sent', 'Viewed', 'Signed']
    );
  });

  it('refresh helper keeps contract, editable fields, and sections aligned', () => {
    const nextState = buildEditableContractState(
      makeContract({
        sections: [{ id: 'updated', title: 'Updated', content: 'New', order: 0 }],
      }) as any
    );

    assert.equal(nextState.contract.contract_title, 'Photo Contract');
    assert.equal(nextState.editedContract.contract_title, 'Photo Contract');
    assert.deepEqual(nextState.editedSections, [
      { id: 'updated', title: 'Updated', content: 'New', order: 0 },
    ]);
  });

  it('sorts revision history newest-first for the sidebar', () => {
    const revisions = sortContractRevisionHistory({
      current_contract_id: 'contract_2',
      root_contract_id: 'contract_1',
      versions: [
        {
          id: 'contract_1',
          version_number: 1,
          contract_kind: 'original',
          status: 'signed',
          is_current_version: false,
          created_at: '2026-04-10T00:00:00.000Z',
        },
        {
          id: 'contract_2',
          version_number: 2,
          contract_kind: 'revision',
          status: 'sent',
          is_current_version: true,
          created_at: '2026-04-11T00:00:00.000Z',
        },
      ],
    } as any);

    assert.deepEqual(
      revisions.map((item) => item.version_number),
      [2, 1]
    );
  });

  it('keeps revision history and activity as separate surfaces in the page source', () => {
    assert.match(DETAIL_PAGE_SOURCE, /Version History/);
    assert.match(DETAIL_PAGE_SOURCE, /Activity Log/);
    assert.match(DETAIL_PAGE_SOURCE, /<PaymentMilestones/);
    assert.doesNotMatch(DETAIL_PAGE_SOURCE, /\bTimeline\b/);
  });
});
