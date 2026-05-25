import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  getPlannerMessageToastTargetUrl,
  getPlannerRealtimeNotificationKind,
} from '../../app/admin/components/PlannerActionToastListener';

describe('PlannerActionToastListener notification routing', () => {
  it('treats inbox message notifications as toast-worthy realtime events', () => {
    assert.equal(getPlannerRealtimeNotificationKind('couple_message'), 'message');
    assert.equal(getPlannerRealtimeNotificationKind('guest_message'), 'message');
    assert.equal(getPlannerRealtimeNotificationKind('support_ticket_response'), 'message');
  });

  it('preserves the existing checklist action notification branches', () => {
    assert.equal(getPlannerRealtimeNotificationKind('wedding_created'), 'wedding_created');
    assert.equal(getPlannerRealtimeNotificationKind('couple_portal_accepted'), 'couple_portal_accepted');
    assert.equal(getPlannerRealtimeNotificationKind('billing_notice'), null);
  });

  it('keeps unified inbox deep links but replaces legacy message routes', () => {
    assert.equal(
      getPlannerMessageToastTargetUrl({
        type: 'guest_message',
        wedding_id: 'wedding/needs encoding',
        action_url: '/admin/communications/inbox?conversation=sms_support&ticket_id=sms-1&wedding_id=wedding%2Fneeds%20encoding',
      }),
      '/admin/communications/inbox?conversation=sms_support&ticket_id=sms-1&wedding_id=wedding%2Fneeds%20encoding',
    );
    assert.equal(
      getPlannerMessageToastTargetUrl({
        type: 'guest_message',
        wedding_id: 'wedding/needs encoding',
        action_url: '/admin/planner/weddings/wedding/needs encoding/messages',
      }),
      '/admin/communications/inbox?wedding_id=wedding%2Fneeds%20encoding',
    );
  });
});
