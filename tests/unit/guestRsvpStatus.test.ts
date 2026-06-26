import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  GUEST_RSVP_STATUS_FILTER_OPTIONS,
  getGuestRsvpDisplayStatus,
  getGuestRsvpExportLabel,
  getGuestRsvpStatusLabel,
  getRsvpAttendingList,
} from '../../app/admin/utils/guestRsvpStatus';

describe('guest RSVP status helpers', () => {
  it('classifies dynamic RSVP event selections for visible badges and exports', () => {
    const guest = { invite_sent: true };

    assert.equal(
      getGuestRsvpDisplayStatus(guest, { attending: ['after_party'] }),
      'confirmed',
    );
    assert.equal(
      getGuestRsvpDisplayStatus(guest, { attending: [] }),
      'declined',
    );
    assert.equal(
      getGuestRsvpExportLabel(guest, { attending: [] }),
      'Declined',
    );
  });

  it('keeps legacy event selections aligned with the original declined contract', () => {
    const guest = { invite_sent: true };

    assert.equal(
      getGuestRsvpDisplayStatus(guest, { attending: [] }),
      'declined',
    );
    assert.equal(
      getGuestRsvpDisplayStatus(guest, {
        attending: { custom_brunch: false, after_party: false },
      }),
      'declined',
    );
    assert.equal(
      getGuestRsvpDisplayStatus(guest, {
        attending: { custom_brunch: false, after_party: true },
      }),
      'confirmed',
    );
    assert.equal(
      getGuestRsvpExportLabel(guest, { attending: [] }),
      'Declined',
    );
  });

  it('distinguishes missing RSVP state from declined RSVP state', () => {
    assert.equal(getGuestRsvpDisplayStatus({ invite_sent: true }, null), 'pending');
    assert.equal(
      getGuestRsvpDisplayStatus({ invite_sent: false }, null),
      'not_invited',
    );
    assert.equal(
      getGuestRsvpDisplayStatus({ invite_sent: true }, { attending: null }),
      'pending',
    );
  });

  it('exposes confirmed and declined as first-class table filters', () => {
    const values = GUEST_RSVP_STATUS_FILTER_OPTIONS.map((option) => option.value);

    assert.deepEqual(values, [
      'all',
      'responded',
      'confirmed',
      'declined',
      'pending',
      'not_invited',
    ]);
    assert.equal(getGuestRsvpStatusLabel('declined'), 'Declined');
    assert.deepEqual(getRsvpAttendingList({ attending: ['after_party'] }), [
      'after_party',
    ]);
  });
});
