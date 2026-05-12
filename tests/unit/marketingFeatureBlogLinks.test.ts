import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { MARKETING_FEATURES } from '../../app/data/marketingFeatures';
import { fallbackBlogCards } from '../../app/resources/resourcesShared';

describe('marketing feature blog links', () => {
  it('only links to seeded public blog cards', () => {
    const seededPublicSlugs = new Set(fallbackBlogCards.map((post) => post.slug));
    const invalidLinks = MARKETING_FEATURES
      .filter((feature) => feature.blogSlug && !seededPublicSlugs.has(feature.blogSlug))
      .map((feature) => `${feature.id}:${feature.blogSlug}`);

    assert.deepEqual(invalidLinks, []);
  });
});
