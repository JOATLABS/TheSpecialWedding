import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  formatAIChatError,
  getAIWidgetPanelSizeClasses,
  getAIWidgetPositionClasses,
  isInboxComposerSurface,
} from '../../app/components/ai/AIChatWidget';

describe('AIChatWidget route-aware chrome', () => {
  it('moves the launcher and panel away from the communications inbox composer', () => {
    assert.equal(isInboxComposerSurface('/admin/communications/inbox'), true);
    assert.equal(isInboxComposerSurface('/admin/communications/inbox?wedding_id=1'), true);
    assert.match(getAIWidgetPositionClasses('/admin/communications/inbox', false), /bottom-24/);
    assert.match(getAIWidgetPositionClasses('/admin/communications/inbox', true), /bottom-24/);
    assert.match(getAIWidgetPanelSizeClasses('/admin/communications/inbox'), /100svh-8rem/);
  });

  it('keeps the compact default dock on non-inbox pages', () => {
    assert.equal(isInboxComposerSurface('/admin/planner'), false);
    assert.match(getAIWidgetPositionClasses('/admin/planner', false), /bottom-6/);
    assert.match(getAIWidgetPanelSizeClasses('/admin/planner'), /100svh-3rem/);
  });

  it('normalizes duplicate retry copy from AI errors', () => {
    assert.equal(
      formatAIChatError('AI generation failed: AI returned an unexpected response. Please try again.'),
      'AI returned an unexpected response. Please try again.'
    );
    assert.equal(
      formatAIChatError('AI returned an empty response'),
      'AI returned an empty response. Please try again.'
    );
  });
});
