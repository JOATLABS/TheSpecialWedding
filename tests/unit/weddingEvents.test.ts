import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  ALL_WEDDING_EVENTS,
  getWeddingEventLabel,
  getWeddingReminderEventOptions,
} from '../../app/utils/weddingEvents';

describe('wedding reminder event options', () => {
  it('keeps All as the first reminder event choice', () => {
    const options = getWeddingReminderEventOptions([
      { type: 'traditional' },
      { type: 'white_wedding' },
      { type: 'reception' },
    ]);

    assert.deepEqual(options.slice(0, 4), [
      { value: ALL_WEDDING_EVENTS, label: 'All' },
      { value: 'traditional', label: 'Traditional Ceremony' },
      { value: 'white_wedding', label: 'White Wedding' },
      { value: 'reception', label: 'Reception' },
    ]);
  });

  it('still offers All when a wedding has no saved event list yet', () => {
    const options = getWeddingReminderEventOptions();

    assert.equal(options[0]?.value, ALL_WEDDING_EVENTS);
    assert.equal(options[0]?.label, 'All');
    assert.equal(options[1]?.value, 'traditional');
  });

  it('labels all-event reminders as All Events in recipient copy', () => {
    assert.equal(getWeddingEventLabel(ALL_WEDDING_EVENTS), 'All Events');
  });
});
