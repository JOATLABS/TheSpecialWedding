import { before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

let MarkdownArticle: typeof import('../../app/components/blog/MarkdownArticle').default;

function renderArticle(content: string): string {
  return renderToStaticMarkup(React.createElement(MarkdownArticle, { content }));
}

describe('MarkdownArticle', () => {
  before(async () => {
    ({ default: MarkdownArticle } = await import('../../app/components/blog/MarkdownArticle'));
  });

  it('renders markdown headings and lists', () => {
    const html = renderArticle('# Pricing guide\n\n- One\n- Two');

    assert.match(html, /<h1[^>]*>Pricing guide<\/h1>/);
    assert.match(html, /<li>One<\/li>/);
    assert.match(html, /<li>Two<\/li>/);
  });

  it('renders editorial html without showing literal tags', () => {
    const html = renderArticle('<p>Intro</p><h3>Section</h3><p><strong>Bold</strong> text.</p>');

    assert.match(html, /<p>Intro<\/p>/);
    assert.match(html, /<h3[^>]*>Section<\/h3>/);
    assert.match(html, /<strong>Bold<\/strong>/);
    assert.doesNotMatch(html, /&lt;p&gt;/);
    assert.doesNotMatch(html, /&lt;h3&gt;/);
  });

  it('strips unsafe html blocks and javascript urls', () => {
    const html = renderArticle(
      '<p>Safe intro</p><script>alert("x")</script><style>body{display:none;}</style><a href="javascript:alert(1)">Bad link</a>'
    );

    assert.match(html, /Safe intro/);
    assert.match(html, /Bad link/);
    assert.doesNotMatch(html, /script/i);
    assert.doesNotMatch(html, /style/i);
    assert.doesNotMatch(html, /alert\(/);
    assert.doesNotMatch(html, /javascript:/i);
  });
});
