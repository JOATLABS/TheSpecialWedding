import { afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';

let resolveMediaUrl: typeof import('../../app/utils/mediaUrl').resolveMediaUrl;

const originalMediaDomain = process.env.NEXT_PUBLIC_MEDIA_DOMAIN;

describe('resolveMediaUrl', () => {
  before(async () => {
    ({ resolveMediaUrl } = await import('../../app/utils/mediaUrl'));
  });

  afterEach(() => {
    if (originalMediaDomain === undefined) {
      delete process.env.NEXT_PUBLIC_MEDIA_DOMAIN;
      return;
    }

    process.env.NEXT_PUBLIC_MEDIA_DOMAIN = originalMediaDomain;
  });

  it('passes through absolute and browser-native media urls unchanged', () => {
    assert.equal(
      resolveMediaUrl('https://media.example.com/gallery/couple.jpg'),
      'https://media.example.com/gallery/couple.jpg',
    );
    assert.equal(
      resolveMediaUrl('blob:https://staging.thespecialwedding.io/image'),
      'blob:https://staging.thespecialwedding.io/image',
    );
    assert.equal(
      resolveMediaUrl('data:image/png;base64,abc123'),
      'data:image/png;base64,abc123',
    );
  });

  it('prefixes raw storage keys with the configured media domain', () => {
    process.env.NEXT_PUBLIC_MEDIA_DOMAIN = 'https://media.example.com/';

    assert.equal(
      resolveMediaUrl('gallery/jordan-and-alex/hero.jpg'),
      'https://media.example.com/gallery/jordan-and-alex/hero.jpg',
    );
    assert.equal(
      resolveMediaUrl('/our-story/jordan-and-alex/story.jpg'),
      'https://media.example.com/our-story/jordan-and-alex/story.jpg',
    );
  });

  it('preserves repository-owned static demo media without treating it as an R2 key', () => {
    process.env.NEXT_PUBLIC_MEDIA_DOMAIN = 'https://media.example.com/';

    assert.equal(
      resolveMediaUrl('/demo-gallery/elegant-couple-stairs.svg'),
      '/demo-gallery/elegant-couple-stairs.svg',
    );
    assert.equal(
      resolveMediaUrl('/demo-gallery/sofia-daniel-terrace.webp'),
      '/demo-gallery/sofia-daniel-terrace.webp',
    );
  });

  it('rejects unapproved or traversing repository demo-media paths', () => {
    process.env.NEXT_PUBLIC_MEDIA_DOMAIN = 'https://media.example.com/';

    assert.equal(resolveMediaUrl('/demo-gallery/unapproved.svg'), undefined);
    assert.equal(resolveMediaUrl('/demo-gallery/../api/private'), undefined);
    assert.equal(resolveMediaUrl('/demo-gallery/%2e%2e/api/private'), undefined);
  });

  it('returns the normalized key when no public media domain is configured', () => {
    delete process.env.NEXT_PUBLIC_MEDIA_DOMAIN;

    assert.equal(
      resolveMediaUrl(' wedding-party/jordan-and-alex/alex.jpg '),
      'wedding-party/jordan-and-alex/alex.jpg',
    );
    assert.equal(resolveMediaUrl('   '), undefined);
  });
});
