import assert from 'node:assert/strict';
import { after, afterEach, before, describe, it, mock } from 'node:test';
import React from 'react';
import { cleanup, render, waitFor } from '@testing-library/react';

import { installDom } from './testDom';

let UmamiAnalyticsForPath:
  | typeof import('../../app/components/analytics/UmamiAnalyticsBoundary').UmamiAnalyticsForPath
  | undefined;
let domHandle: ReturnType<typeof installDom> | null = null;
let originalFetch: typeof globalThis.fetch;

const CONFIG = {
  websiteId: 'privacy-test-site',
  src: 'https://analytics.example.test/script.js',
};

describe('Umami analytics route privacy boundary', () => {
  before(async () => {
    domHandle = installDom();
    originalFetch = globalThis.fetch;
    ({ UmamiAnalyticsForPath } = await import(
      '../../app/components/analytics/UmamiAnalyticsBoundary'
    ));
  });

  afterEach(() => {
    cleanup();
    document.querySelectorAll('script[data-website-id]').forEach((script) => script.remove());
    mock.restoreAll();
    globalThis.fetch = originalFetch;
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('withholds the configured tracker and runtime config request on tokenized paths', async () => {
    assert.ok(UmamiAnalyticsForPath);
    let fetchCalls = 0;
    globalThis.fetch = (async () => {
      fetchCalls += 1;
      return new Response(null, { status: 204 });
    }) as typeof fetch;

    render(
      <UmamiAnalyticsForPath
        config={CONFIG}
        pathname="/domain-instructions/a-secret-token"
      />,
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(document.querySelector('script[data-website-id]'), null);
    assert.equal(fetchCalls, 0);
  });

  it('fails closed before the pathname is available', async () => {
    assert.ok(UmamiAnalyticsForPath);
    let fetchCalls = 0;
    globalThis.fetch = (async () => {
      fetchCalls += 1;
      return new Response(null, { status: 204 });
    }) as typeof fetch;

    render(<UmamiAnalyticsForPath config={CONFIG} pathname={null} />);

    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(document.querySelector('script[data-website-id]'), null);
    assert.equal(fetchCalls, 0);
  });

  it('loads configured analytics with the privacy guard on an ordinary route', async () => {
    assert.ok(UmamiAnalyticsForPath);
    render(<UmamiAnalyticsForPath config={CONFIG} pathname="/admin/packages" />);

    await waitFor(() => {
      const script = document.querySelector<HTMLScriptElement>(
        'script[data-website-id="privacy-test-site"]',
      );
      assert.ok(script);
      assert.equal(script.dataset.beforeSend, '__tswUmamiBeforeSend');
      assert.equal(script.getAttribute('referrerpolicy'), 'no-referrer');
    });
  });

  it('applies the same guard to the runtime fallback on an ordinary route', async () => {
    assert.ok(UmamiAnalyticsForPath);
    const calls: string[] = [];
    globalThis.fetch = (async (input: string | URL | Request) => {
      calls.push(String(input));
      return Response.json({
        configured: true,
        websiteId: 'runtime-privacy-site',
        src: 'https://runtime-analytics.example.test/script.js',
      });
    }) as typeof fetch;

    render(<UmamiAnalyticsForPath config={null} pathname="/features" />);

    await waitFor(() => {
      assert.deepEqual(calls, ['/api/public/analytics-config']);
      const script = document.querySelector<HTMLScriptElement>(
        'script[data-website-id="runtime-privacy-site"]',
      );
      assert.ok(script);
      assert.equal(script.dataset.beforeSend, '__tswUmamiBeforeSend');
      assert.equal(script.getAttribute('referrerpolicy'), 'no-referrer');
    });
  });
});
