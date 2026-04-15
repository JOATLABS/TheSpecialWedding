import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';

import { installDom } from './testDom';

let PrivacyModeSelector: typeof import('../../app/admin/weddings/[id]/PrivacyModeSelector')['PrivacyModeSelector'];
let normalizePrivacySettingsForMode: typeof import('../../app/admin/weddings/[id]/privacySettings')['normalizePrivacySettingsForMode'];
let domHandle: ReturnType<typeof installDom> | null = null;

describe('planner wedding privacy settings', () => {
  before(async () => {
    domHandle = installDom();
    ({ PrivacyModeSelector } = await import('../../app/admin/weddings/[id]/PrivacyModeSelector'));
    ({ normalizePrivacySettingsForMode } = await import('../../app/admin/weddings/[id]/privacySettings'));
  });

  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('normalizes incompatible fields when public access is selected', () => {
    const result = normalizePrivacySettingsForMode(
      {
        privacy_mode: 'private',
        guest_auth_required: true,
        password_protection: 'secret', // pragma: allowlist secret
        allow_guest_sharing: true,
        require_phone_verification: true,
        require_name_verification: true,
      },
      'public',
    );

    assert.deepEqual(result, {
      privacy_mode: 'public',
      guest_auth_required: false,
      password_protection: '',
      allow_guest_sharing: false,
      require_phone_verification: false,
      require_name_verification: false,
    });
  });

  it('renders compact privacy mode buttons instead of a native select', () => {
    const onChange = mock.fn((_mode: string) => undefined);
    const view = render(
      <PrivacyModeSelector value="private" onChange={onChange} />
    );

    assert.equal(view.queryByRole('combobox'), null);

    fireEvent.click(view.getByRole('radio', { name: /public/i }));

    assert.equal(onChange.mock.calls.length, 1);
    assert.equal(onChange.mock.calls[0].arguments[0], 'public');
  });
});
