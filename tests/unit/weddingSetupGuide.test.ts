import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import type { Wedding } from '../../app/types/wedding';
import {
  buildWeddingSetupSummary,
  isWeddingSetupTab,
} from '../../app/admin/weddings/setupGuide';

const buildWedding = (overrides: Partial<Wedding> = {}): Wedding => ({
  id: 'wedding_1',
  slug: 'ava-and-noah',
  couple_names: 'Ava and Noah',
  date: '2026-08-15',
  events: [
    {
      type: 'ceremony',
      date: '2026-08-15',
      details: {
        time: '4:00 PM',
        venue_name: 'The Garden Hall',
      },
    },
  ],
  rsvp_config: {
    greeting: 'Join us in celebrating our special day.',
    help_text: 'Use the help button if your invitation link is missing.',
    phone_numbers: [],
    hide_phone_numbers: true,
    help_button_label: 'Get Help',
  },
  privacy_settings: {
    privacy_mode: 'public',
    guest_auth_required: false,
    password_protection: '',
    allow_guest_sharing: false,
    require_phone_verification: false,
    require_name_verification: false,
  },
  registries: [],
  faqs: [],
  theme_config: {
    primary_color: '#1e3a5f',
    secondary_color: '#d4af37',
    accent_color: '#c8847e',
    background_style: 'gradient',
    font_style: 'elegant',
  },
  our_story: {
    text: '',
    image_url: '',
    image_shape: 'circle',
  },
  wedding_party: [],
  wedding_party_sync: {
    sync_enabled: false,
    sync_mode: 'manual',
  },
  ...overrides,
});

describe('wedding setup guide rules', () => {
  it('counts guest-facing essentials as ready', () => {
    const summary = buildWeddingSetupSummary(buildWedding(), {
      canViewCoupleTab: false,
      vendorAssignmentCount: 0,
    });

    assert.equal(summary.requiredTotal, 4);
    assert.equal(summary.requiredComplete, 4);
    assert.equal(summary.progressPercent, 100);
    assert.equal(summary.nextStep, null);
  });

  it('requires a password before password access is ready', () => {
    const summary = buildWeddingSetupSummary(
      buildWedding({
        privacy_settings: {
          privacy_mode: 'password',
          guest_auth_required: false,
          password_protection: '',
          allow_guest_sharing: false,
          require_phone_verification: false,
          require_name_verification: false,
        },
      }),
      {
        canViewCoupleTab: false,
        vendorAssignmentCount: 0,
      },
    );

    const privacyStep = summary.steps.find((step) => step.tab === 'privacy');

    assert.equal(privacyStep?.status, 'attention');
    assert.equal(summary.nextStep?.tab, 'privacy');
  });

  it('keeps optional feature tabs visible without blocking launch readiness', () => {
    const summary = buildWeddingSetupSummary(buildWedding(), {
      canViewCoupleTab: true,
      vendorAssignmentCount: 0,
    });

    const optionalTabs = summary.steps
      .filter((step) => !step.required)
      .map((step) => step.tab);

    assert.deepEqual(optionalTabs, [
      'vendors',
      'registry',
      'faq',
      'story',
      'couple',
    ]);
    assert.equal(summary.requiredComplete, summary.requiredTotal);
  });

  it('guards dashboard tab handoff query values', () => {
    assert.equal(isWeddingSetupTab('privacy'), true);
    assert.equal(isWeddingSetupTab('billing'), false);
    assert.equal(isWeddingSetupTab(null), false);
  });
});
