import { after, afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';

import { installDom } from './testDom';

let PublicContractPageRuntime: typeof import('../../app/vendor-contract/[id]/PublicContractPageClient').default;
let domHandle: ReturnType<typeof installDom> | null = null;

function makeContract(overrides: Record<string, unknown> = {}) {
  return {
    _id: 'contract_1',
    contract_title: 'Photography Agreement',
    contract_number: 'VC-100',
    vendor_name: 'Vendor Co',
    vendor_email: 'vendor@example.com',
    planner_name: 'Planner Name',
    planner_company: 'Planner Co',
    couple_names: 'Alex and Sam',
    service_category: 'photographer',
    sections: [{ id: 'scope', title: 'Scope', content: 'Capture the full wedding day.', order: 0 }],
    total_amount: 5000,
    currency: 'USD',
    status: 'sent',
    ...overrides,
  };
}

describe('PublicContractPageClient', () => {
  before(async () => {
    domHandle = installDom();
    ({ default: PublicContractPageRuntime } = await import('../../app/vendor-contract/[id]/PublicContractPageClient'));
  });

  afterEach(() => {
    cleanup();
  });

  after(() => {
    domHandle = null;
  });

  it('renders the shared preview through the canonical path-token fetch flow', async () => {
    const calls: Array<{ url: string; method?: string; cache?: RequestCache }> = [];
    const fetchImpl: typeof fetch = async (input, init) => {
      calls.push({ url: String(input), method: init?.method, cache: init?.cache });
      return {
        ok: true,
        status: 200,
        json: async () => makeContract(),
      } as Response;
    };

    const view = render(
      <PublicContractPageRuntime
        runtimeOverrides={{
          contractId: 'contract_1',
          routeToken: 'path-token',
          queryToken: 'legacy-query-token',
          fetchImpl,
        }}
      />
    );

    await view.findByText('Photography Agreement');
    view.getByText('Capture the full wedding day.');
    assert.equal(calls[0]?.url, '/api/proxy/vendor-contract/public/contracts/contract_1/path-token');
    assert.equal(calls[0]?.cache, 'no-store');
  });

  it('renders the signed confirmation when the initial contract fetch is already signed', async () => {
    const fetchImpl: typeof fetch = async () =>
      ({
        ok: true,
        status: 200,
        json: async () =>
          makeContract({
            status: 'signed',
            signed_at: '2026-04-10T12:30:00.000Z',
            signed_by_name: 'Vendor Co',
          }),
      }) as Response;

    const view = render(
      <PublicContractPageRuntime
        runtimeOverrides={{
          contractId: 'contract_1',
          routeToken: 'signed-token',
          fetchImpl,
        }}
      />
    );

    await view.findByText('Contract Signed!');
    view.getByText('Vendor Co');
  });

  it('shows the replaced-version state and hides signing controls for superseded links', async () => {
    const fetchImpl: typeof fetch = async () =>
      ({
        ok: false,
        status: 410,
        json: async () => ({}),
      }) as Response;

    const view = render(
      <PublicContractPageRuntime
        runtimeOverrides={{
          contractId: 'contract_1',
          routeToken: 'replaced-token',
          fetchImpl,
        }}
      />
    );

    await view.findByText('Contract Version Replaced');
    view.getByText(/Please use the newest contract link sent by the wedding planner/i);
    assert.equal(view.queryByRole('button', { name: 'Sign Contract' }), null);
  });

  it('shows the expired-or-invalid-token error state for denied access', async () => {
    const fetchImpl: typeof fetch = async () =>
      ({
        ok: false,
        status: 403,
        json: async () => ({}),
      }) as Response;

    const view = render(
      <PublicContractPageRuntime
        runtimeOverrides={{
          contractId: 'contract_1',
          routeToken: 'expired-token',
          fetchImpl,
        }}
      />
    );

    await view.findByText('Unable to Load Contract');
    view.getByText('Access denied. This link may have expired or is invalid.');
  });

  it('supports the happy-path signing flow and refreshes into the signed state', async () => {
    const calls: Array<{ url: string; method?: string; body?: string; cache?: RequestCache }> = [];
    const responses = [
      {
        ok: true,
        status: 200,
        json: async () => makeContract(),
      },
      {
        ok: true,
        status: 200,
        json: async () => ({ success: true }),
      },
      {
        ok: true,
        status: 200,
        json: async () =>
          makeContract({
            status: 'signed',
            signed_at: '2026-04-10T12:30:00.000Z',
            signed_by_name: 'Vendor Co',
          }),
      },
    ];

    const fetchImpl: typeof fetch = async (input, init) => {
      calls.push({
        url: String(input),
        method: init?.method,
        body: init?.body as string | undefined,
        cache: init?.cache,
      });
      const next = responses.shift();
      if (!next) {
        throw new Error('Unexpected fetch call');
      }

      return next as Response;
    };

    const view = render(
      <PublicContractPageRuntime
        runtimeOverrides={{
          contractId: 'contract_1',
          routeToken: 'sign-token',
          fetchImpl,
        }}
      />
    );

    await view.findByText('Photography Agreement');
    fireEvent.click(view.getAllByRole('button', { name: 'Sign Contract' })[0]);

    fireEvent.change(view.getByPlaceholderText('Enter your full name'), {
      target: { value: 'Vendor Co' },
    });
    fireEvent.change(view.getByPlaceholderText('Enter your email'), {
      target: { value: 'vendor@example.com' },
    });
    fireEvent.click(view.getByLabelText(/I have read and agree to the terms/i));
    fireEvent.click(view.getAllByRole('button', { name: 'Sign Contract' })[1]);

    await view.findByText('Contract Signed!');
    assert.equal(calls[1]?.url, '/api/proxy/vendor-contract/public/contracts/contract_1/sign-token/sign');
    assert.equal(calls[1]?.method, 'POST');
    assert.equal(calls[1]?.cache, 'no-store');
    assert.match(calls[1]?.body || '', /"signer_name":"Vendor Co"/);
  });

  it('treats an already-signed sign response as an idempotent signed state', async () => {
    const responses = [
      {
        ok: true,
        status: 200,
        json: async () => makeContract(),
      },
      {
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'Contract has already been signed',
        }),
      },
      {
        ok: true,
        status: 200,
        json: async () =>
          makeContract({
            status: 'signed',
            signed_at: '2026-04-10T12:30:00.000Z',
            signed_by_name: 'Vendor Co',
          }),
      },
    ];

    const fetchImpl: typeof fetch = async () => {
      const next = responses.shift();
      if (!next) {
        throw new Error('Unexpected fetch call');
      }

      return next as Response;
    };

    const view = render(
      <PublicContractPageRuntime
        runtimeOverrides={{
          contractId: 'contract_1',
          routeToken: 'sign-token',
          fetchImpl,
        }}
      />
    );

    await view.findByText('Photography Agreement');
    fireEvent.click(view.getAllByRole('button', { name: 'Sign Contract' })[0]);

    fireEvent.change(view.getByPlaceholderText('Enter your full name'), {
      target: { value: 'Vendor Co' },
    });
    fireEvent.change(view.getByPlaceholderText('Enter your email'), {
      target: { value: 'vendor@example.com' },
    });
    fireEvent.click(view.getByLabelText(/I have read and agree to the terms/i));
    fireEvent.click(view.getAllByRole('button', { name: 'Sign Contract' })[1]);

    await view.findByText('Contract Signed!');
    assert.equal(view.queryByText('Contract has already been signed'), null);
  });

  it('surfaces backend sign failures instead of a fake connection message', async () => {
    const responses = [
      {
        ok: true,
        status: 200,
        json: async () => makeContract(),
      },
      {
        ok: false,
        status: 503,
        json: async () => ({
          detail: 'Vendor contract signing requires MongoDB transaction support',
        }),
      },
    ];

    const fetchImpl: typeof fetch = async () => {
      const next = responses.shift();
      if (!next) {
        throw new Error('Unexpected fetch call');
      }

      return next as Response;
    };

    const view = render(
      <PublicContractPageRuntime
        runtimeOverrides={{
          contractId: 'contract_1',
          routeToken: 'sign-token',
          fetchImpl,
        }}
      />
    );

    await view.findByText('Photography Agreement');
    fireEvent.click(view.getAllByRole('button', { name: 'Sign Contract' })[0]);

    fireEvent.change(view.getByPlaceholderText('Enter your full name'), {
      target: { value: 'Vendor Co' },
    });
    fireEvent.change(view.getByPlaceholderText('Enter your email'), {
      target: { value: 'vendor@example.com' },
    });
    fireEvent.click(view.getByLabelText(/I have read and agree to the terms/i));
    fireEvent.click(view.getAllByRole('button', { name: 'Sign Contract' })[1]);

    await view.findByText('Unable to Load Contract');
    view.getByText('Vendor contract signing requires MongoDB transaction support');
  });
});
