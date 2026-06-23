import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { buildEventReminderEmailPayload } from '../../app/admin/communications/components/reminderPayloads';

describe('communications reminder payloads', () => {
  it('uses the planner-edited event message as the email body', () => {
    const payload = buildEventReminderEmailPayload({
      weddingSlug: 'summer-wedding',
      eventType: 'reception',
      customMessage: '  Updated reception reminder  ',
      emailSubject: '  New subject  ',
      targetGroup: 'guests',
    });

    assert.deepEqual(payload, {
      wedding_slug: 'summer-wedding',
      event_type: 'reception',
      custom_subject: 'New subject',
      custom_html: 'Updated reception reminder',
      target_group: 'guests',
    });
  });

  it('falls back to the backend default email body when the visible message is empty', () => {
    const payload = buildEventReminderEmailPayload({
      weddingSlug: 'summer-wedding',
      eventType: 'all',
      customMessage: '   ',
      emailSubject: '',
      targetGroup: 'all',
    });

    assert.equal(payload.custom_html, null);
    assert.equal(payload.custom_subject, null);
  });
});
