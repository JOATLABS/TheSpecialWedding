import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { resolveStorefrontRewriteHost } from '../../app/utils/storefrontHost';

test('normalizes a custom hostname only for the root storefront request', () => {
  assert.equal(resolveStorefrontRewriteHost('  Studio.Example.COM.  ', '/'), 'studio.example.com');
  assert.equal(resolveStorefrontRewriteHost('studio.example.com:443', '/'), 'studio.example.com');
  assert.equal(resolveStorefrontRewriteHost('münchen.example', '/'), 'xn--mnchen-3ya.example');
  assert.equal(resolveStorefrontRewriteHost('studio.example.com', '/packages'), null);
});

test('never rewrites platform, API, staging, or local development hosts', () => {
  for (const host of [
    'thespecialwedding.io',
    'www.thespecialwedding.io',
    'api.thespecialwedding.io',
    'staging.thespecialwedding.io',
    'thespecialwedding.com',
    'cname.thespecialwedding.com',
    'localhost',
    'localhost:3000',
    'planner.localhost:3000',
    '127.0.0.1:3000',
    '[::1]:3000',
  ]) {
    assert.equal(resolveStorefrontRewriteHost(host, '/'), null, host);
  }
});

test('fails closed for missing, ambiguous, IP, and malformed host headers', () => {
  for (const host of [
    null,
    '',
    'one.example, two.example',
    '192.0.2.20',
    '[2001:db8::1]',
    'single-label',
    '-bad.example',
    'bad_.example',
    'https://studio.example.com',
    'user@studio.example.com',
    'studio.example.com/path',
    'studio.example.com?forward=elsewhere',
    'studio.example.com#fragment',
    '%65xample.com',
  ]) {
    assert.equal(resolveStorefrontRewriteHost(host, '/'), null, String(host));
  }
});

test('the Next proxy rewrites only the resolved custom host to its storefront identifier', () => {
  const source = readFileSync('proxy.ts', 'utf8');

  assert.match(source, /resolveStorefrontRewriteHost/);
  assert.match(source, /x-forwarded-host/);
  assert.match(source, /encodeURIComponent\(storefrontHost\)/);
  assert.match(source, /NextResponse\.rewrite/);
});
