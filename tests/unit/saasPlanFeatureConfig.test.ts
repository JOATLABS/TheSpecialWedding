import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  buildPlanFeatureState,
  formatFeatureListInput,
  getPlanFeatureEntries,
  parseFeatureListInput,
} from '../../app/admin/saas/planFeatureConfig';

test('buildPlanFeatureState preserves seeded and unknown feature flags', () => {
  const state = buildPlanFeatureState({
    guest_management: true,
    email_invitations: true,
    wedding_website: true,
    timeline_builder: true,
    qr_checkin: true,
    vendor_collaboration: true,
    future_seeded_flag: true,
  });

  assert.equal(state.guest_management, true);
  assert.equal(state.email_invitations, true);
  assert.equal(state.wedding_website, true);
  assert.equal(state.timeline_builder, true);
  assert.equal(state.qr_checkin, true);
  assert.equal(state.vendor_collaboration, true);
  assert.equal(state.future_seeded_flag, true);
  assert.equal(state.white_label, false);
});

test('getPlanFeatureEntries orders known flags and keeps extra flags visible', () => {
  const entries = getPlanFeatureEntries({
    future_seeded_flag: true,
    qr_checkin: true,
    guest_management: true,
  });

  const keys = entries.map((entry) => entry.key);
  assert.equal(keys.indexOf('guest_management') < keys.indexOf('qr_checkin'), true);
  assert.equal(keys.includes('future_seeded_flag'), true);
});

test('feature list input round-trips one highlight per line', () => {
  const input = formatFeatureListInput([
    'Up to 10 weddings',
    'QR check-in & live counts',
    'Priority support',
  ]);

  assert.equal(
    input,
    'Up to 10 weddings\nQR check-in & live counts\nPriority support',
  );
  assert.deepEqual(parseFeatureListInput(`\n${input}\n\n`), [
    'Up to 10 weddings',
    'QR check-in & live counts',
    'Priority support',
  ]);
});
