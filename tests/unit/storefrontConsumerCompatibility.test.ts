import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const modalSource = readFileSync(
  'app/admin/packages/StorefrontSettingsModal.tsx',
  'utf8'
);
const domainSource = readFileSync(
  'app/admin/components/storefront/CustomDomainManager.tsx',
  'utf8'
);
const adminApiSource = readFileSync('app/services/storefrontApi.ts', 'utf8');
const publicSource = readFileSync('app/storefront/[domain]/page.tsx', 'utf8');
const publicViewSource = readFileSync(
  'app/components/storefront/StorefrontView.tsx',
  'utf8'
);

describe('storefront server and shipped consumer compatibility', () => {
  it('uses authenticated admin paths and an allowlisted settings payload', () => {
    assert.match(adminApiSource, /\/admin\/storefront\/settings/);
    assert.doesNotMatch(adminApiSource, /\/api\/storefront\/settings/);
    assert.match(modalSource, /toSettingsCandidate/);
    assert.match(modalSource, /buildStorefrontSettingsPatch/);
    assert.doesNotMatch(modalSource, /'POST', draft\)/);
    assert.match(modalSource, /saved\.slug/);

    assert.match(adminApiSource, /\/admin\/storefront\/custom-domain/);
    assert.doesNotMatch(adminApiSource, /\/api\/storefront\/custom-domain/);
    assert.match(domainSource, /preflightCustomDomain/);
    assert.match(domainSource, /claimCustomDomain/);
  });

  it('renders the strict public package and contact DTO without legacy fields', () => {
    assert.match(publicSource, /StorefrontView/);
    assert.match(publicViewSource, /pkg\.total_amount/);
    assert.match(publicViewSource, /pkg\.services/);
    assert.match(publicViewSource, /storefront\.contact_email/);
    assert.match(publicViewSource, /storefront\.contact_phone/);
    assert.doesNotMatch(publicViewSource, /pkg\.price/);
    assert.doesNotMatch(publicViewSource, /pkg\.features/);
    assert.doesNotMatch(publicViewSource, /planner\.email/);
    assert.doesNotMatch(publicViewSource, /planner\.support_phone/);
  });
});
