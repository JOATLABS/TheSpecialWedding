import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { NextRequest } from 'next/server';

import { resolveStorefrontRewriteHost } from '../../app/utils/storefrontHost';
import { proxy } from '../../proxy';

interface IdnaHostnameFixture {
  input: string;
  ascii: string;
}

const idnaHostnameFixtures = JSON.parse(
  readFileSync('tests/fixtures/storefront_idna_hostnames.json', 'utf8'),
) as IdnaHostnameFixture[];

test('normalizes a custom hostname only for the root storefront request', () => {
  assert.equal(resolveStorefrontRewriteHost('  Studio.Example.COM.  ', '/'), 'studio.example.com');
  assert.equal(resolveStorefrontRewriteHost('studio.example.com:443', '/'), 'studio.example.com');
  assert.equal(resolveStorefrontRewriteHost('münchen.example', '/'), 'xn--mnchen-3ya.example');
  assert.equal(resolveStorefrontRewriteHost('studio.example.com', '/packages'), null);
});

test('normalizes the shared UTS-46 hostname fixtures used by the backend', () => {
  for (const fixture of idnaHostnameFixtures) {
    assert.equal(resolveStorefrontRewriteHost(fixture.input, '/'), fixture.ascii, fixture.input);
  }
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

test('uses backend-compatible runtime platform hosts and configured app origins', () => {
  const config = {
    platformDomains: '["platform.example.net", "api.example.net"]',
    frontendUrl: 'https://staging.frontend.example.org/admin',
    apiBaseUrl: 'https://api.staging.example.org/v1',
    cnameTarget: 'storefronts.example.org',
  };

  for (const host of [
    'platform.example.net',
    'www.platform.example.net',
    'api.example.net',
    'staging.frontend.example.org',
    'api.staging.example.org',
    'storefronts.example.org',
  ]) {
    assert.equal(resolveStorefrontRewriteHost(host, '/', config), null, host);
  }

  assert.equal(
    resolveStorefrontRewriteHost('studio.example.com', '/', config),
    'studio.example.com',
  );
  assert.equal(
    resolveStorefrontRewriteHost('platform.example.net', '/', {
      platformDomains: 'platform.example.net, api.example.net',
    }),
    null,
  );
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
  assert.doesNotMatch(source, /x-forwarded-host/);
  assert.match(source, /request\.headers\.get\(['"]host['"]\)/);
  assert.match(source, /STOREFRONT_PLATFORM_DOMAINS/);
  assert.match(source, /FRONTEND_URL/);
  assert.match(source, /encodeURIComponent\(storefrontHost\)/);
  assert.match(source, /NextResponse\.rewrite/);
});

test('the Next proxy ignores spoofed or mismatched forwarded hosts', () => {
  const platformRequest = new NextRequest('https://thespecialwedding.io/', {
    headers: {
      host: 'thespecialwedding.io',
      'x-forwarded-host': 'studio.example.com',
    },
  });
  const platformResponse = proxy(platformRequest);
  assert.equal(platformResponse.headers.get('x-middleware-rewrite'), null);

  const customRequest = new NextRequest('https://studio.example.com/', {
    headers: {
      host: 'studio.example.com',
      'x-forwarded-host': 'attacker.example.net',
    },
  });
  const customResponse = proxy(customRequest);
  assert.match(
    customResponse.headers.get('x-middleware-rewrite') ?? '',
    /\/storefront\/studio\.example\.com$/,
  );
});

test('a custom storefront host cannot render another tenant slug path', () => {
  const customRequest = new NextRequest(
    'https://studio.example.com/storefront/another-planner',
    {
      headers: { host: 'studio.example.com' },
    },
  );
  const customResponse = proxy(customRequest);

  assert.equal(customResponse.status, 404);
  assert.equal(customResponse.headers.get('x-middleware-rewrite'), null);

  const platformRequest = new NextRequest(
    'https://thespecialwedding.io/storefront/another-planner',
    {
      headers: { host: 'thespecialwedding.io' },
    },
  );
  const platformResponse = proxy(platformRequest);

  assert.notEqual(platformResponse.status, 404);
  assert.equal(platformResponse.headers.get('x-middleware-rewrite'), null);
});
