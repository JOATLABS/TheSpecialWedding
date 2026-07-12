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
const publicSource = readFileSync('app/storefront/[domain]/page.tsx', 'utf8');

describe('storefront server and shipped consumer compatibility', () => {
  it('uses authenticated admin paths and an allowlisted settings payload', () => {
    assert.match(modalSource, /\/admin\/storefront\/settings/);
    assert.doesNotMatch(modalSource, /\/api\/storefront\/settings/);
    assert.match(modalSource, /const savePayload = \{/);
    assert.doesNotMatch(modalSource, /'POST', settings\)/);
    assert.match(modalSource, /settings\.slug/);

    assert.match(domainSource, /\/admin\/storefront\/custom-domain/);
    assert.doesNotMatch(domainSource, /\/api\/storefront\/custom-domain/);
  });

  it('renders the strict public package and contact DTO without legacy fields', () => {
    assert.match(publicSource, /pkg\.total_amount/);
    assert.match(publicSource, /pkg\.services/);
    assert.match(publicSource, /storefront\.contact_email/);
    assert.match(publicSource, /storefront\.contact_phone/);
    assert.doesNotMatch(publicSource, /pkg\.price/);
    assert.doesNotMatch(publicSource, /pkg\.features/);
    assert.doesNotMatch(publicSource, /planner\.email/);
    assert.doesNotMatch(publicSource, /planner\.support_phone/);
  });
});
