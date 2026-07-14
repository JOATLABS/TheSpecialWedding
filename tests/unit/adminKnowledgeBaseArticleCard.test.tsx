import { after, afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, render } from '@testing-library/react';

import { installDom } from './testDom';

let ArticleCard: typeof import('../../app/admin/components/kb/ArticleCard').default;
let domHandle: ReturnType<typeof installDom> | null = null;

const article = {
  id: 'kb-capture-1',
  _id: 'kb-capture-1',
  title: 'Planner Command Center: Your First 30 Minutes',
  slug: 'planner-command-center',
  excerpt: 'Start the wedding workspace with a connected first-session checklist.',
  category: 'getting-started',
  tags: ['planner'],
  status: 'published',
  is_official: true,
  featured: true,
  author_name: 'Amina Cole',
  author_email: 'amina@studio.thespecialwedding.io',
  view_count: 12,
  helpful_count: 4,
  not_helpful_count: 0,
  estimated_read_minutes: 2,
  created_at: '2026-07-12T10:00:00Z',
  updated_at: '2026-07-12T10:00:00Z',
};

describe('admin knowledge-base article card', () => {
  before(async () => {
    domHandle = installDom();
    ({ default: ArticleCard } = await import('../../app/admin/components/kb/ArticleCard'));
  });

  afterEach(() => cleanup());

  after(() => {
    domHandle?.cleanup();
  });

  it('does not render a fake image placeholder when the article has no card image', () => {
    const view = render(<ArticleCard article={article} onClick={() => undefined} />);

    assert.equal(view.container.querySelector('img'), null);
    assert.equal(view.container.querySelector('.h-24'), null);
    assert.ok(view.getByText(article.title));
  });

  it('renders real article media when a card image is supplied', () => {
    const view = render(
      <ArticleCard
        article={{ ...article, card_image: '/knowledgebase/planner-command-center.webp' }}
        onClick={() => undefined}
      />,
    );

    const image = view.getByRole('img', { name: article.title });
    assert.equal(image.getAttribute('src'), '/knowledgebase/planner-command-center.webp');
  });
});
