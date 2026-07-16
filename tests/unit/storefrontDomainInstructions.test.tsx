import assert from 'node:assert/strict';
import { after, afterEach, before, describe, it, mock } from 'node:test';
import React from 'react';
import { cleanup, render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { DomainInstruction } from '../../app/domain-instructions/domainInstructionData';
import { loadDomainInstructions } from '../../app/domain-instructions/domainInstructionData';
import { installDom } from './testDom';

const TOKEN = 'a'.repeat(43);
const NOW = new Date('2026-07-15T18:00:00.000Z');

const apiPayload = {
  hostname: 'events.customer.example',
  provider: {
    name: 'Cloudflare',
    zone: 'customer.example',
    control_panel_url: 'https://dash.cloudflare.com/example/dns',
  },
  records: [
    {
      type: 'TXT',
      name: '_tsw-storefront.events.customer.example',
      relative_host: '_tsw-storefront.events',
      value: 'tsw-verification=unique-token',
      ttl: 300,
      purpose: 'application_ownership',
      proxy: null,
    },
    {
      type: 'CNAME',
      name: 'events.customer.example',
      relative_host: 'events',
      value: 'domains.thespecialwedding.com',
      ttl: 300,
      purpose: 'storefront_routing',
      proxy: 'dns_only',
    },
  ],
  note: 'Please send a screenshot after saving both records.',
  expires_at: '2026-07-22T18:00:00.000Z',
};

let DomainInstructionsView:
  | React.ComponentType<{ instruction: DomainInstruction }>
  | undefined;
let DomainInstructionsPage:
  | ((props: { params: Promise<{ token: string }> }) => Promise<React.ReactElement>)
  | undefined;
let domHandle: ReturnType<typeof installDom> | null = null;
let originalInternalApiBaseUrl: string | undefined;
let originalFetch: typeof globalThis.fetch;

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('public storefront DNS instructions', () => {
  before(async () => {
    domHandle = installDom();
    originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
    originalFetch = globalThis.fetch;
    const viewModule = await import(
      '../../app/domain-instructions/[token]/DomainInstructionsView'
    );
    DomainInstructionsView = viewModule.DomainInstructionsView;
    const pageModule = await import('../../app/domain-instructions/[token]/page');
    DomainInstructionsPage = pageModule.default;
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
    globalThis.fetch = originalFetch;
    if (originalInternalApiBaseUrl === undefined) {
      delete process.env.INTERNAL_API_BASE_URL;
    } else {
      process.env.INTERNAL_API_BASE_URL = originalInternalApiBaseUrl;
    }
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('loads the expiring snapshot server-side with no-store and maps only safe public fields', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetchImpl = (async (input: string | URL | Request, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return jsonResponse(apiPayload);
    }) as typeof fetch;

    const result = await loadDomainInstructions(TOKEN, {
      apiBaseUrl: 'https://api.example.test/',
      fetchImpl,
      now: () => NOW,
    });

    assert.equal(result.status, 'ready');
    if (result.status !== 'ready') return;
    assert.equal(calls.length, 1);
    assert.equal(
      calls[0].url,
      `https://api.example.test/api/storefront/domain-instructions/${TOKEN}`,
    );
    const { signal, ...requestInit } = calls[0].init ?? {};
    assert.ok(signal instanceof AbortSignal);
    assert.deepEqual(requestInit, {
      method: 'GET',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    assert.deepEqual(result.instruction.provider, {
      name: 'Cloudflare',
      zone: 'customer.example',
      controlPanelUrl: 'https://dash.cloudflare.com/example/dns',
    });
    assert.deepEqual(result.instruction.records[1], {
      type: 'CNAME',
      fqdn: 'events.customer.example',
      relativeHost: 'events',
      values: ['domains.thespecialwedding.com'],
      ttl: 300,
      purpose: 'storefront_routing',
      proxy: 'dns_only',
    });
    assert.equal('detail' in result.instruction, false);
  });

  it('treats invalid, expired, revoked, and malformed snapshots as closed states', async () => {
    let calls = 0;
    const invalid = await loadDomainInstructions('short-token', {
      apiBaseUrl: 'https://api.example.test',
      fetchImpl: (async () => {
        calls += 1;
        return jsonResponse(apiPayload);
      }) as typeof fetch,
      now: () => NOW,
    });
    assert.equal(invalid.status, 'expired_or_revoked');
    assert.equal(calls, 0);

    for (const status of [404, 410]) {
      const result = await loadDomainInstructions(TOKEN, {
        apiBaseUrl: 'https://api.example.test',
        fetchImpl: (async () => jsonResponse({ detail: 'raw backend error' }, status)) as typeof fetch,
        now: () => NOW,
      });
      assert.equal(result.status, 'expired_or_revoked');
    }

    const expired = await loadDomainInstructions(TOKEN, {
      apiBaseUrl: 'https://api.example.test',
      fetchImpl: (async () =>
        jsonResponse({ ...apiPayload, expires_at: '2026-07-14T18:00:00.000Z' })) as typeof fetch,
      now: () => NOW,
    });
    assert.equal(expired.status, 'expired_or_revoked');

    const malformed = await loadDomainInstructions(TOKEN, {
      apiBaseUrl: 'https://api.example.test',
      fetchImpl: (async () => jsonResponse({ hostname: 'events.customer.example' })) as typeof fetch,
      now: () => NOW,
    });
    assert.equal(malformed.status, 'temporarily_unavailable');

    const partial = await loadDomainInstructions(TOKEN, {
      apiBaseUrl: 'https://api.example.test',
      fetchImpl: (async () =>
        jsonResponse({
          ...apiPayload,
          records: [apiPayload.records[0], { type: 'CNAME', name: 'missing-value.example' }],
        })) as typeof fetch,
      now: () => NOW,
    });
    assert.equal(partial.status, 'temporarily_unavailable');
  });

  it('renders provider-aware records, responsive overflow guards, accessible controls, and copy feedback', async () => {
    assert.ok(DomainInstructionsView);
    const result = await loadDomainInstructions(TOKEN, {
      apiBaseUrl: 'https://api.example.test',
      fetchImpl: (async () => jsonResponse(apiPayload)) as typeof fetch,
      now: () => NOW,
    });
    assert.equal(result.status, 'ready');
    if (result.status !== 'ready') return;

    const copied: string[] = [];
    const user = userEvent.setup({ document: window.document });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: async (value: string) => void copied.push(value) },
    });
    const view = render(React.createElement(DomainInstructionsView, {
      instruction: result.instruction,
    }));

    view.getByRole('heading', { level: 1, name: /add these DNS records/i });
    view.getByRole('heading', { level: 2, name: 'Cloudflare' });
    view.getByText(/DNS zone: customer\.example/i);
    view.getByText('Ownership verification');
    view.getByText('Storefront routing');
    view.getByText('_tsw-storefront.events');
    view.getByText('_tsw-storefront.events.customer.example');
    view.getByText('domains.thespecialwedding.com');
    assert.equal(view.getAllByText('300 seconds').length, 2);
    view.getByText('DNS only / not proxied');
    view.getByText('Not applicable for this record type');
    view.getByText(/link expires Jul 22, 2026/i);

    const providerLink = view.getByRole('link', { name: /open DNS settings/i });
    assert.equal(providerLink.getAttribute('href'), 'https://dash.cloudflare.com/example/dns');
    assert.equal(providerLink.getAttribute('rel'), 'noopener noreferrer');
    assert.equal(providerLink.getAttribute('referrerpolicy'), 'no-referrer');

    const main = view.getByRole('main');
    assert.match(main.className, /overflow-x-hidden/);
    for (const value of view.container.querySelectorAll('code')) {
      assert.match(value.className, /break-all/);
    }
    view.getByRole('button', { name: /copy DNS record 1/i });
    assert.equal(view.getAllByRole('button', { name: /copy full hostname/i }).length, 2);
    assert.equal(view.getAllByRole('button', { name: /copy record value/i }).length, 2);

    await user.click(view.getByRole('button', { name: /copy all DNS records/i }));
    await waitFor(() => assert.equal(copied.length, 1));
    assert.match(copied[0], /Ownership verification/);
    assert.match(copied[0], /domains\.thespecialwedding\.com/);
    assert.match(view.getByRole('status').textContent ?? '', /all DNS records copied/i);
  });

  it('labels missing provider semantics instead of inventing values or links', async () => {
    assert.ok(DomainInstructionsView);
    const result = await loadDomainInstructions(TOKEN, {
      apiBaseUrl: 'https://api.example.test',
      fetchImpl: (async () =>
        jsonResponse({
          ...apiPayload,
          provider: undefined,
          records: [
            {
              type: 'CNAME',
              name: 'events.customer.example',
              value: 'domains.thespecialwedding.com',
              purpose: 'storefront_routing',
            },
          ],
        })) as typeof fetch,
      now: () => NOW,
    });
    assert.equal(result.status, 'ready');
    if (result.status !== 'ready') return;

    const view = render(React.createElement(DomainInstructionsView, {
      instruction: result.instruction,
    }));
    view.getByRole('heading', { name: /provider details unavailable/i });
    view.getByText(/DNS zone: Not included in this secure link/i);
    view.getByText(/some provider-specific details are unavailable/i);
    view.getByText(/not included — use the full hostname below/i);
    view.getByText(/do not change proxy mode without guidance/i);
    assert.equal(view.queryByRole('link', { name: /open DNS settings/i }), null);
  });

  it('renders friendly expired and temporary pages without raw backend JSON', async () => {
    assert.ok(DomainInstructionsPage);
    process.env.INTERNAL_API_BASE_URL = 'https://api.example.test';

    globalThis.fetch = (async () =>
      jsonResponse({ detail: 'secret provider failure payload' }, 404)) as typeof fetch;
    const expiredElement = await DomainInstructionsPage({ params: Promise.resolve({ token: TOKEN }) });
    const expiredView = render(expiredElement);
    expiredView.getByRole('heading', { name: /instruction link is no longer available/i });
    expiredView.getByText(/ask the planner to send a new secure DNS instruction link/i);
    assert.equal(expiredView.queryByText(/secret provider failure payload/i), null);
    cleanup();

    globalThis.fetch = (async () =>
      jsonResponse({ detail: 'raw cloudflare configuration error' }, 503)) as typeof fetch;
    const temporaryElement = await DomainInstructionsPage({ params: Promise.resolve({ token: TOKEN }) });
    const temporaryView = render(temporaryElement);
    temporaryView.getByRole('heading', { name: /could not load these instructions/i });
    temporaryView.getByText(/no DNS changes were made/i);
    temporaryView.getByRole('link', { name: /try again/i });
    assert.equal(temporaryView.queryByText(/raw cloudflare configuration error/i), null);
  });
});
