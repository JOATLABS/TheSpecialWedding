import { after, afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';

import { installDom } from './testDom';

let LandingGalleryPreview: typeof import('../../app/components/landing-page/LandingGalleryPreview').LandingGalleryPreview;
let domHandle: ReturnType<typeof installDom> | null = null;

describe('public wedding gallery preview', () => {
  before(async () => {
    domHandle = installDom();
    ({ LandingGalleryPreview } = await import('../../app/components/landing-page/LandingGalleryPreview'));
  });

  afterEach(() => cleanup());

  after(() => {
    domHandle?.cleanup();
  });

  it('shows a deliberate loading state instead of claiming the gallery is empty', () => {
    const view = render(<LandingGalleryPreview images={[]} loading />);

    assert.ok(view.getByText('Loading gallery…'));
    assert.equal(view.queryByText('Photos will be added soon!'), null);
  });

  it('shows empty copy only after gallery loading has completed', () => {
    const view = render(<LandingGalleryPreview images={[]} loading={false} />);

    assert.ok(view.getByText('Photos will be added soon!'));
    assert.equal(view.queryByText('Loading gallery…'), null);
  });

  it('shows a retryable error without claiming a failed gallery is empty', () => {
    let retryCount = 0;
    const view = render(
      <LandingGalleryPreview
        images={[]}
        loading={false}
        error
        onRetry={() => {
          retryCount += 1;
        }}
      />,
    );

    assert.ok(view.getByRole('alert'));
    assert.ok(view.getByText('Gallery temporarily unavailable'));
    assert.equal(view.queryByText('Photos will be added soon!'), null);

    fireEvent.click(view.getByRole('button', { name: 'Try gallery again' }));
    assert.equal(retryCount, 1);
  });

  it('removes a broken image without hiding the healthy preview images', () => {
    const view = render(
      <LandingGalleryPreview
        images={[
          { key: 'first', url: '/demo-gallery/first.webp' },
          { key: 'second', url: '/demo-gallery/second.webp' },
        ]}
        loading={false}
      />,
    );

    fireEvent.error(view.getByAltText('Wedding gallery photo 1'));

    assert.equal(view.queryByAltText('Wedding gallery photo 1'), null);
    assert.ok(view.getByAltText('Wedding gallery photo 2'));
    assert.equal(view.queryByText('Gallery photos could not be displayed'), null);
  });

  it('renders the approved privacy-safe image description when provided', () => {
    const view = render(
      <LandingGalleryPreview
        images={[{
          key: 'terrace',
          url: '/demo-gallery/sofia-daniel-terrace.webp',
          alt: 'Fictional newlyweds on the glasshouse garden terrace',
        }]}
        loading={false}
      />,
    );

    assert.ok(
      view.getByAltText('Fictional newlyweds on the glasshouse garden terrace'),
    );
    assert.equal(view.queryByAltText('Wedding gallery photo 1'), null);
  });

  it('shows a recoverable state when every preview image fails', () => {
    let retryCount = 0;
    const view = render(
      <LandingGalleryPreview
        images={[{ key: 'only', url: '/demo-gallery/only.webp' }]}
        loading={false}
        onRetry={() => {
          retryCount += 1;
        }}
      />,
    );

    fireEvent.error(view.getByAltText('Wedding gallery photo 1'));

    assert.ok(view.getByRole('alert'));
    assert.ok(view.getByText('Gallery photos could not be displayed'));
    assert.equal(view.queryByText('Photos will be added soon!'), null);

    fireEvent.click(view.getByRole('button', { name: 'Try gallery again' }));
    assert.equal(retryCount, 1);
    assert.ok(view.getByAltText('Wedding gallery photo 1'));
  });

  it('retries previously failed URLs when a fresh gallery result arrives', () => {
    const firstResult = [{ key: 'first', url: '/demo-gallery/first.webp' }];
    const view = render(
      <LandingGalleryPreview images={firstResult} loading={false} />,
    );

    fireEvent.error(view.getByAltText('Wedding gallery photo 1'));
    assert.equal(view.queryByAltText('Wedding gallery photo 1'), null);

    view.rerender(
      <LandingGalleryPreview images={[...firstResult]} loading={false} />,
    );
    assert.ok(view.getByAltText('Wedding gallery photo 1'));
  });
});
