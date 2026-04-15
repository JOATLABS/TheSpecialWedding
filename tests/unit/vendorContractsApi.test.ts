import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com';

let vendorContractsApi: typeof import('../../app/services/vendorContractsApi');

const originalFetch = globalThis.fetch;

const contractResponse = {
  _id: 'contract_1',
  wedding_id: 'wedding_1',
  vendor_name: 'Vendor Co',
  vendor_email: 'vendor@example.com',
  service_category: 'photographer',
  contract_title: 'Photo Contract',
  sections: [],
  total_amount: 5000,
  currency: 'USD',
  status: 'draft',
  created_at: '2026-04-08T00:00:00.000Z',
  updated_at: '2026-04-08T00:00:00.000Z',
};

describe('vendorContractsApi request normalization', () => {
  before(async () => {
    vendorContractsApi = await import('../../app/services/vendorContractsApi');
  });

  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      Reflect.deleteProperty(
        globalThis as typeof globalThis & { fetch?: typeof fetch },
        'fetch'
      );
    }
  });

  after(() => {
    vendorContractsApi = undefined as unknown as typeof vendorContractsApi;
  });

  it('createContract sends a JSON body to the vendor contract endpoint', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(input.toString(), 'https://api.example.com/admin/contracts');
      assert.equal(init?.method, 'POST');

      const headers = init?.headers as Record<string, string> | undefined;
      assert.equal(headers?.Authorization ?? headers?.authorization, 'Bearer secret-token');

      const body = JSON.parse(init?.body as string);
      assert.equal(body.wedding_id, 'wedding_1');
      assert.equal(body.vendor_profile_id, 'vendor_1');
      assert.equal(body.total_amount, 5000);
      assert.deepEqual(body.custom_sections, [{ id: 'extra-1', title: 'Extras', content: 'Coverage', order: 0 }]);

      return new Response(JSON.stringify(contractResponse), { status: 200 });
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.createContract('secret-token', {
      wedding_id: 'wedding_1',
      vendor_profile_id: 'vendor_1',
      total_amount: 5000,
      custom_sections: [{ title: 'Extras', content: 'Coverage', order: 0, id: 'extra-1' }],
    });

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result._id, 'contract_1');
  });

  it('updateContract sends the normalized JSON body to the admin contract endpoint', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(input.toString(), 'https://api.example.com/admin/contracts/contract_1');
      assert.equal(init?.method, 'PUT');

      const body = JSON.parse(init?.body as string);
      assert.equal(body.contract_title, 'Updated title');
      assert.equal(body.total_amount, 7200);
      assert.equal(body.service_location, 'Austin, TX');

      return new Response(
        JSON.stringify({
          ...contractResponse,
          contract_title: 'Updated title',
          total_amount: 7200,
          service_location: 'Austin, TX',
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.updateContract('secret-token', 'contract_1', {
      contract_title: 'Updated title',
      total_amount: 7200,
      service_location: 'Austin, TX',
    });

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result.total_amount, 7200);
  });

  it('sendContract sends a JSON body instead of query params', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(input.toString(), 'https://api.example.com/admin/contracts/contract_1/send');
      assert.equal(init?.method, 'POST');

      const body = JSON.parse(init?.body as string);
      assert.equal(body.message, 'Please review');
      assert.deepEqual(body.cc_emails, ['team@example.com']);

      return new Response(
        JSON.stringify({ message: 'Contract sent successfully', sent_to: 'vendor@example.com' }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.sendContract(
      'secret-token',
      'contract_1',
      'Please review',
      ['team@example.com']
    );

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result.sent_to, 'vendor@example.com');
  });

  it('applyFormDataToContract sends the normalized request body and returns the updated contract', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/contracts/contract_1/apply-form-data'
      );
      assert.equal(init?.method, 'POST');

      const body = JSON.parse(init?.body as string);
      assert.equal(body.form_submission_id, 'submission_1');
      assert.deepEqual(body.field_mappings, { portfolio_link: '{{vendor_portfolio}}' });

      return new Response(
        JSON.stringify({
          ...contractResponse,
          form_data_applied: true,
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.applyFormDataToContract(
      'secret-token',
      'contract_1',
      {
        form_submission_id: 'submission_1',
        field_mappings: { portfolio_link: '{{vendor_portfolio}}' },
      }
    );

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result.form_data_applied, true);
  });

  it('getContractFormData returns the normalized response shape', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/contracts/contract_1/form-data'
      );

      return new Response(
        JSON.stringify({
          vendor_submissions: [
            {
              _id: 'submission_1',
              form_name: 'Vendor Intake',
              source: 'vendor_form',
              data: { portfolio_link: 'https://example.com/work' },
            },
          ],
          available_fields: {
            portfolio_link: {
              value: 'https://example.com/work',
              source: 'vendor_form',
              source_id: 'submission_1',
              original_key: 'portfolio_link',
            },
          },
          suggested_contract_fields: {
            '{{vendor_portfolio}}': {
              value: 'https://example.com/work',
              source_field: 'portfolio_link',
            },
          },
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.getContractFormData('secret-token', 'contract_1');

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result.vendor_submissions[0]._id, 'submission_1');
    assert.equal(result.suggested_contract_fields['{{vendor_portfolio}}'].source_field, 'portfolio_link');
  });

  it('recordPayment sends milestone payment data as JSON', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(input.toString(), 'https://api.example.com/admin/milestones/milestone_1/pay');
      assert.equal(init?.method, 'POST');

      const body = JSON.parse(init?.body as string);
      assert.equal(body.amount, 1200);
      assert.equal(body.payment_method, 'card');
      assert.equal(body.notes, 'Paid in full');

      return new Response(
        JSON.stringify({
          _id: 'milestone_1',
          contract_id: 'contract_1',
          wedding_id: 'wedding_1',
          description: 'Deposit',
          amount: 1200,
          currency: 'USD',
          due_date: '2026-04-20T00:00:00.000Z',
          status: 'paid',
          paid_amount: 1200,
          vendor_name: 'Vendor Co',
          vendor_email: 'vendor@example.com',
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.recordPayment('secret-token', 'milestone_1', {
      amount: 1200,
      payment_method: 'card',
      payment_date: '2026-04-08T00:00:00.000Z',
      notes: 'Paid in full',
    });

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result.status, 'paid');
  });

  it('createPaymentMilestones sends the normalized milestone request body', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/contracts/contract_1/milestones'
      );
      assert.equal(init?.method, 'POST');

      const body = JSON.parse(init?.body as string);
      assert.deepEqual(body, {
        milestones: [
          {
            description: 'Deposit',
            amount: 2500,
            due_date: '2026-04-20T00:00:00.000Z',
            percentage_of_total: 50,
          },
        ],
      });

      return new Response(
        JSON.stringify([
          {
            _id: 'milestone_1',
            contract_id: 'contract_1',
            wedding_id: 'wedding_1',
            description: 'Deposit',
            amount: 2500,
            currency: 'USD',
            due_date: '2026-04-20T00:00:00.000Z',
            status: 'pending',
            paid_amount: 0,
            vendor_name: 'Vendor Co',
            vendor_email: 'vendor@example.com',
          },
        ]),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.createPaymentMilestones('secret-token', 'contract_1', [
      {
        description: 'Deposit',
        amount: 2500,
        due_date: '2026-04-20T00:00:00.000Z',
        percentage_of_total: 50,
      },
    ]);

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result[0]._id, 'milestone_1');
  });

  it('updateContractSections sends the full object payload', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/contracts/contract_1/sections'
      );
      assert.equal(init?.method, 'PUT');

      const body = JSON.parse(init?.body as string);
      assert.deepEqual(body.sections, [{ id: 'sec-1', title: 'Scope', content: 'Coverage', order: 0 }]);
      assert.equal(body.terms_and_conditions, 'Terms');
      assert.equal(body.cancellation_policy, 'Cancel');
      assert.equal(body.custom_clauses, 'Custom');

      return new Response(JSON.stringify(contractResponse), { status: 200 });
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.updateContractSections('secret-token', 'contract_1', {
      sections: [{ id: 'sec-1', title: 'Scope', content: 'Coverage', order: 0 }],
      terms_and_conditions: 'Terms',
      cancellation_policy: 'Cancel',
      custom_clauses: 'Custom',
    });

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result._id, 'contract_1');
  });

  it('createContractRevision sends the normalized revision request body', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/contracts/contract_1/revisions'
      );
      assert.equal(init?.method, 'POST');

      const body = JSON.parse(init?.body as string);
      assert.equal(body.revision_kind, 'amendment');
      assert.equal(body.reason, 'Signed scope change');
      assert.equal(body.copy_sections, true);

      return new Response(
        JSON.stringify({
          ...contractResponse,
          _id: 'contract_2',
          version_number: 2,
          contract_kind: 'amendment',
          parent_contract_id: 'contract_1',
          supersedes_contract_id: 'contract_1',
          is_current_version: false,
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.createContractRevision('secret-token', 'contract_1', {
      revision_kind: 'amendment',
      reason: 'Signed scope change',
      copy_sections: true,
    });

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result._id, 'contract_2');
    assert.equal(result.contract_kind, 'amendment');
  });

  it('getContractRevisions returns the revision lineage payload', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/contracts/contract_1/revisions'
      );
      assert.equal(init?.method, undefined);

      return new Response(
        JSON.stringify({
          current_contract_id: 'contract_2',
          root_contract_id: 'contract_1',
          versions: [
            {
              id: 'contract_1',
              contract_number: 'CON-001',
              version_number: 1,
              contract_kind: 'original',
              status: 'signed',
              is_current_version: false,
              created_at: '2026-04-08T00:00:00.000Z',
            },
            {
              id: 'contract_2',
              contract_number: 'CON-001',
              version_number: 2,
              contract_kind: 'revision',
              status: 'sent',
              is_current_version: true,
              created_at: '2026-04-09T00:00:00.000Z',
            },
          ],
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.getContractRevisions('secret-token', 'contract_1');

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result.current_contract_id, 'contract_2');
    assert.equal(result.versions[1].version_number, 2);
  });

  it('getContractActivity returns the normalized activity payload', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/contracts/contract_1/activity'
      );
      assert.equal(init?.method, undefined);

      return new Response(
        JSON.stringify({
          contract_id: 'contract_1',
          root_contract_id: 'contract_1',
          items: [
            {
              id: 'activity_1',
              contract_id: 'contract_1',
              root_contract_id: 'contract_1',
              activity_type: 'contract_sent',
              title: 'Contract sent',
              description: 'Sent to vendor@example.com for review and signature.',
              actor: {
                type: 'planner',
                identifier: 'planner@example.com',
                display_name: 'planner@example.com',
              },
              metadata: {
                cc_emails: [],
              },
              created_at: '2026-04-09T00:00:00.000Z',
            },
          ],
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.getContractActivity('secret-token', 'contract_1');

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result.items[0].activity_type, 'contract_sent');
    assert.equal(result.items[0].actor.type, 'planner');
  });

  it('getPublicContract uses the canonical path-token route', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/vendor-contract/public/contracts/contract_1/raw-token'
      );
      assert.equal(init?.cache, 'no-store');

      return new Response(
        JSON.stringify({
          _id: 'contract_1',
          contract_title: 'Photo Contract',
          vendor_name: 'Vendor Co',
          vendor_email: 'vendor@example.com',
          service_category: 'photographer',
          sections: [],
          total_amount: 5000,
          currency: 'USD',
          status: 'sent',
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.getPublicContract('contract_1', 'raw-token');

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result._id, 'contract_1');
  });

  it('getPublicContract surfaces superseded-version errors cleanly', async () => {
    const fetchMock = mock.fn(async () => new Response(JSON.stringify({ detail: 'replaced' }), { status: 410 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await assert.rejects(
      () => vendorContractsApi.getPublicContract('contract_1', 'raw-token'),
      /This contract version has been replaced/
    );
  });

  it('signPublicContract uses the canonical path-token sign route', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/vendor-contract/public/contracts/contract_1/raw-token/sign'
      );
      assert.equal(init?.method, 'POST');

      const body = JSON.parse(init?.body as string);
      assert.equal(body.signer_name, 'Vendor Owner');
      assert.equal(body.signer_email, 'vendor@example.com');

      return new Response(
        JSON.stringify({
          message: 'Contract signed successfully',
          signed_at: '2026-04-10T00:00:00.000Z',
        }),
        { status: 200 }
      );
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await vendorContractsApi.signPublicContract(
      'contract_1',
      'raw-token',
      'Vendor Owner',
      'vendor@example.com'
    );

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(result.message, 'Contract signed successfully');
  });

  it('signPublicContract surfaces superseded-version errors cleanly', async () => {
    const fetchMock = mock.fn(async () => new Response(JSON.stringify({ detail: 'replaced' }), { status: 410 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await assert.rejects(
      () =>
        vendorContractsApi.signPublicContract(
          'contract_1',
          'raw-token',
          'Vendor Owner',
          'vendor@example.com'
        ),
      /This contract version has been replaced/
    );
  });
});
