import assert from 'node:assert/strict';
import { after, afterEach, before, describe, it } from 'node:test';
import React from 'react';
import { cleanup, render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { installDom } from './testDom';

let ReviewQueue: typeof import('../../app/admin/platform/StorefrontDomainReviewQueue').default;
let domHandle: ReturnType<typeof installDom> | null = null;

const summary = {
  review_id: 'sfor_opaque_review_reference_0123456789abcdef0123456789abcdef0123',
  review_type: 'o2o_cutover',
  hostname: 'events.customer.example',
  application_status: 'operator_review',
  action: 'operator_review',
  revision: 7,
  updated_at: '2026-07-15T18:00:00Z',
  support_id: 'sfd_support_1',
  allowed_actions: ['approve_o2o_cutover'],
};

const detail = {
  ...summary,
  planner_id: '507f1f77bcf86cd799439011',
  attempt_id: 'claim-attempt-1',
  intent: 'migration',
  ownership_status: 'verified',
  routing_dns_status: 'pending',
  provider_hostname_status: 'not_started',
  ssl_status: 'not_started',
  https_status: 'not_started',
  authoritative_dns_provider: 'cloudflare',
  authoritative_nameservers: ['ada.ns.cloudflare.com'],
  provider_candidate_ids: [],
  provider_lookup_status: 'not_required',
  provider_lookup_message: null,
  provider_lookup_support_id: null,
  error_code: 'cloudflare_o2o_migration_requires_assistance',
  error_message: 'Ownership is verified and an assisted cutover is required.',
  customer_action: 'Review the exact provider evidence before approval.',
};

describe('StorefrontDomainReviewQueue', () => {
  before(async () => {
    domHandle = installDom();
    ({ default: ReviewQueue } = await import(
      '../../app/admin/platform/StorefrontDomainReviewQueue'
    ));
  });

  afterEach(() => cleanup());

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('loads an opaque review target and submits only the exact fenced decision', async () => {
    const calls: Array<{ url: string; method: string; body?: unknown }> = [];
    let resolved = false;
    const fetchImpl: typeof fetch = async (input, init) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url, method, body });
      if (url.includes('/operator/reviews?')) {
        return Response.json({ items: resolved ? [] : [summary], has_more: false });
      }
      if (url.endsWith(`/operator/reviews/${summary.review_id}`)) {
        return Response.json(detail);
      }
      if (url.endsWith('/operator/o2o/approve') && method === 'POST') {
        resolved = true;
        return Response.json({
          operation_id: 'operator-receipt-1',
          decision: 'approved',
        });
      }
      return Response.json({ error: { message: 'Unexpected test request' } }, { status: 500 });
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      <ReviewQueue token="root-token" fetchImpl={fetchImpl} />,
    );

    await user.click(await view.findByRole('button', { name: /events\.customer\.example/i }));
    await view.findByText('507f1f77bcf86cd799439011');
    const approve = view.getByRole('button', { name: /approve o2o cutover/i });
    assert.equal((approve as HTMLButtonElement).disabled, true);

    await user.type(
      view.getByLabelText(/decision reason/i),
      'Ownership and provider evidence were independently reviewed.',
    );
    await user.click(
      view.getByLabelText(/reviewed this exact owner, hostname, attempt, revision/i),
    );
    assert.equal((approve as HTMLButtonElement).disabled, false);
    await user.click(approve);

    await waitFor(() => {
      assert.match(
        view.getByRole('status').textContent ?? '',
        /receipt operator-receipt-1 was recorded/i,
      );
    });
    assert.deepEqual(
      calls.find((call) => call.url.endsWith('/operator/o2o/approve')),
      {
        url: '/api/proxy/admin/storefront/custom-domain/operator/o2o/approve',
        method: 'POST',
        body: {
          planner_id: detail.planner_id,
          hostname: detail.hostname,
          attempt_id: detail.attempt_id,
          revision: detail.revision,
          reason: 'Ownership and provider evidence were independently reviewed.',
        },
      },
    );
    await view.findByText(/no storefront domains currently require operator review/i);
  });

  it('does not render raw non-envelope backend diagnostics', async () => {
    const raw = 'Cloudflare token secret-token failed at 10.0.0.4';
    const fetchImpl: typeof fetch = async () =>
      Response.json({ detail: raw }, { status: 503 });
    const view = render(
      <ReviewQueue token="root-token" fetchImpl={fetchImpl} />,
    );

    await view.findByRole('alert');
    assert.equal(view.container.textContent?.includes(raw), false);
    assert.match(
      view.getByRole('alert').textContent ?? '',
      /review request failed/i,
    );
  });

  it('ignores reverse-order detail responses and keeps the latest selected review', async () => {
    const secondSummary = {
      ...summary,
      review_id: 'sfor_second_opaque_reference_0123456789abcdef0123456789abcdef0123',
      hostname: 'weddings.second.example',
    };
    const secondDetail = {
      ...detail,
      ...secondSummary,
      planner_id: '507f1f77bcf86cd799439099',
    };
    let resolveFirst: ((response: Response) => void) | undefined;
    let resolveSecond: ((response: Response) => void) | undefined;
    const firstResponse = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    const secondResponse = new Promise<Response>((resolve) => {
      resolveSecond = resolve;
    });
    const fetchImpl: typeof fetch = async (input) => {
      const url = String(input);
      if (url.includes('/operator/reviews?')) {
        return Response.json({ items: [summary, secondSummary], has_more: false });
      }
      if (url.endsWith(`/operator/reviews/${summary.review_id}`)) return firstResponse;
      if (url.endsWith(`/operator/reviews/${secondSummary.review_id}`)) return secondResponse;
      return Response.json({ error: { message: 'Unexpected test request' } }, { status: 500 });
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(<ReviewQueue token="root-token" fetchImpl={fetchImpl} />);

    await user.click(await view.findByRole('button', { name: /events\.customer\.example/i }));
    await user.click(view.getByRole('button', { name: /weddings\.second\.example/i }));
    resolveSecond?.(Response.json(secondDetail));
    await view.findByText('507f1f77bcf86cd799439099');
    resolveFirst?.(Response.json(detail));
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.equal(view.queryByText(detail.planner_id), null);
    assert.ok(view.getByText(secondDetail.planner_id));
  });

  it('clears a stale selection when the refreshed queue no longer contains it', async () => {
    let queueLoads = 0;
    const fetchImpl: typeof fetch = async (input) => {
      const url = String(input);
      if (url.includes('/operator/reviews?')) {
        queueLoads += 1;
        return Response.json({
          items: queueLoads === 1 ? [summary] : [],
          has_more: false,
        });
      }
      if (url.endsWith(`/operator/reviews/${summary.review_id}`)) {
        return Response.json(detail);
      }
      return Response.json({ error: { message: 'Unexpected test request' } }, { status: 500 });
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(<ReviewQueue token="root-token" fetchImpl={fetchImpl} />);

    await user.click(await view.findByRole('button', { name: /events\.customer\.example/i }));
    await view.findByText(detail.planner_id);
    await user.click(view.getByRole('button', { name: /refresh reviews/i }));

    await view.findByText(/no storefront domains currently require operator review/i);
    assert.equal(view.queryByText(detail.planner_id), null);
    assert.match(
      view.getByText(/select a review to inspect/i).textContent ?? '',
      /select a review/i,
    );
  });

  it('shows safe provider-evidence outage state and support id', async () => {
    const outageDetail = {
      ...detail,
      review_type: 'ambiguous_create',
      allowed_actions: ['adopt_ambiguous_create'],
      provider_lookup_status: 'unavailable',
      provider_lookup_message:
        'Cloudflare could not be reached for independent identity evidence.',
      provider_lookup_support_id: 'sfd_safe_support_id',
    };
    const fetchImpl: typeof fetch = async (input) => {
      const url = String(input);
      if (url.includes('/operator/reviews?')) {
        return Response.json({ items: [{ ...summary, ...outageDetail }], has_more: false });
      }
      return Response.json(outageDetail);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(<ReviewQueue token="root-token" fetchImpl={fetchImpl} />);

    await user.click(await view.findByRole('button', { name: /events\.customer\.example/i }));

    assert.match(
      (await view.findByText(/cloudflare could not be reached/i)).textContent ?? '',
      /independent identity evidence/i,
    );
    assert.ok(view.getByText(/sfd_safe_support_id/i));
    assert.equal(
      (view.getByRole('button', { name: /adopt ambiguous create/i }) as HTMLButtonElement)
        .disabled,
      true,
    );
  });
});
