import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const VENDOR_PROFILE_PAGE = readFileSync('app/vendors/[id]/page.tsx', 'utf8');

describe('public vendor profile copyright', () => {
  it('renders the copyright year from the runtime clock', () => {
    assert.match(
      VENDOR_PROFILE_PAGE,
      /© \{new Date\(\)\.getFullYear\(\)\} The Special Wedding/,
    );
    assert.doesNotMatch(VENDOR_PROFILE_PAGE, /© 2024 The Special Wedding/);
  });
});
