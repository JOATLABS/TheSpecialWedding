import { describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

import {
  extractGuestActivityItems,
  loadGuestActivityItems,
} from '../../app/admin/utils/guestActivityResponse';

describe('guest activity response normalization', () => {
  it('reads activities from the standard API response envelope', () => {
    const activities = extractGuestActivityItems({
      success: true,
      data: {
        activities: [
          {
            id: 'activity_1',
            type: 'rsvp_received',
            message: 'Alex RSVPed',
            timestamp: '2026-04-28T15:00:00.000Z',
          },
        ],
        total: 1,
      },
    });

    assert.equal(activities?.length, 1);
    assert.equal(activities?.[0].id, 'activity_1');
  });

  it('rejects malformed success payloads instead of converting them to empty activity', async () => {
    const fetchMock = mock.fn(async () => (
      new Response(JSON.stringify({ success: true, data: { total: 0 } }), { status: 200 })
    ));

    await assert.rejects(
      () =>
        loadGuestActivityItems({
          apiBaseUrl: 'https://api.example.com',
          token: 'secret-token',
          guestId: 'guest_1',
          fetchImpl: fetchMock as unknown as typeof fetch,
        }),
      /Unexpected guest activity response/
    );
  });

  it('rejects explicit failure envelopes even if they include an empty activity field', async () => {
    const fetchMock = mock.fn(async () => (
      new Response(JSON.stringify({ success: false, data: { activities: [] } }), { status: 200 })
    ));

    await assert.rejects(
      () =>
        loadGuestActivityItems({
          apiBaseUrl: 'https://api.example.com',
          token: 'secret-token',
          guestId: 'guest_1',
          fetchImpl: fetchMock as unknown as typeof fetch,
        }),
      /Unexpected guest activity response/
    );
  });

  it('rejects non-2xx responses so callers can retry instead of caching an empty row', async () => {
    const fetchMock = mock.fn(async () => (
      new Response(JSON.stringify({ detail: 'nope' }), { status: 500 })
    ));

    await assert.rejects(
      () =>
        loadGuestActivityItems({
          apiBaseUrl: 'https://api.example.com',
          token: 'secret-token',
          guestId: 'guest_1',
          fetchImpl: fetchMock as unknown as typeof fetch,
        }),
      /Failed to fetch guest activity/
    );

    assert.equal(fetchMock.mock.callCount(), 1);
  });
});
