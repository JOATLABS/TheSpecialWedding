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
});
