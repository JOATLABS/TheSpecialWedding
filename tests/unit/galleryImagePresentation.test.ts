import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  getGalleryImageAlt,
  getGalleryImageLabel,
} from '../../app/admin/gallery/upload/galleryImagePresentation';

describe('gallery image presentation', () => {
  it('prefers approved display metadata over storage implementation details', () => {
    const image = {
      key: 'gallery/sofia-and-daniel/20270125-terrace-portrait.webp',
      display_name: 'Garden terrace portrait',
      alt: 'Sofia and Daniel on the garden terrace',
    };

    assert.equal(getGalleryImageLabel(image, 0), 'Garden terrace portrait');
    assert.equal(getGalleryImageAlt(image, 0), 'Sofia and Daniel on the garden terrace');
  });

  it('humanizes a storage key when explicit presentation metadata is unavailable', () => {
    const image = {
      key: 'gallery/sofia-and-daniel/20270125-reception-table.webp',
    };

    assert.equal(getGalleryImageLabel(image, 2), 'Reception table');
    assert.equal(getGalleryImageAlt(image, 2), 'Reception table');
  });

  it('never exposes a slash-delimited path as the visible fallback', () => {
    const label = getGalleryImageLabel({ key: '../private/capture' }, 3);

    assert.equal(label, 'Capture');
    assert.doesNotMatch(label, /[\\/]/);
  });
});
