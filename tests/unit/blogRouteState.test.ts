import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  buildBlogRouteSearch,
  getBlogRouteState,
} from '../../app/admin/components/blog/blogRouteState';

describe('blog route state', () => {
  it('restores edit mode from a blog article query param', () => {
    const state = getBlogRouteState(new URLSearchParams('tab=blog&blogArticle=article-123'));

    assert.deepEqual(state, {
      viewMode: 'edit',
      articleId: 'article-123',
    });
  });

  it('restores create mode only when no article id is present', () => {
    const state = getBlogRouteState(new URLSearchParams('tab=blog&blogMode=create'));

    assert.deepEqual(state, { viewMode: 'create' });
  });

  it('writes edit mode while preserving unrelated support page params', () => {
    const search = buildBlogRouteSearch('tab=tickets&page=2&blogMode=create', {
      viewMode: 'edit',
      articleId: 'abc',
    });
    const params = new URLSearchParams(search);

    assert.equal(params.get('tab'), 'blog');
    assert.equal(params.get('page'), '2');
    assert.equal(params.get('blogArticle'), 'abc');
    assert.equal(params.get('blogMode'), null);
  });

  it('clears editor params when returning to the blog list', () => {
    const search = buildBlogRouteSearch('tab=blog&blogArticle=abc&blogMode=create', {
      viewMode: 'list',
    });
    const params = new URLSearchParams(search);

    assert.equal(params.get('tab'), 'blog');
    assert.equal(params.get('blogArticle'), null);
    assert.equal(params.get('blogMode'), null);
  });
});
