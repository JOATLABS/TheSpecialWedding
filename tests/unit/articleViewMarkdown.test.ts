import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { stripDuplicateArticleTitleHeading } from '../../app/admin/components/kb/ArticleView';

describe('stripDuplicateArticleTitleHeading', () => {
  it('removes a first markdown h1 when it repeats the article title', () => {
    const body = stripDuplicateArticleTitleHeading(
      'Using the Seating Planner and Venue Floor Plan',
      '# Using the Seating Planner and Venue Floor Plan\n\nThe seating planner helps planners.'
    );

    assert.equal(body, 'The seating planner helps planners.');
  });

  it('keeps a first h1 when it is real article content', () => {
    const content = '# Before You Begin\n\nUse the checklist.';

    assert.equal(stripDuplicateArticleTitleHeading('Using the Seating Planner', content), content);
  });

  it('handles empty article content', () => {
    assert.equal(stripDuplicateArticleTitleHeading('Using the Seating Planner', null), '');
  });
});
