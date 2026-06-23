import { after, afterEach, before, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, render } from '@testing-library/react';

import { EventLocationSection } from '../../app/components/landing-page/EventLocationSection';
import { installDom } from './testDom';

let domHandle: ReturnType<typeof installDom> | null = null;

const weddingWithLocation = {
  slug: 'peace-emmanuel',
  couple_names: 'Peace & Emmanuel',
  theme_config: {},
  events: [
    {
      type: 'traditional',
      date: '2027-02-13',
      details: {
        time: '5:00 PM',
        location: '123 Wedding Lane, Oklahoma City, OK',
        venue_name: 'The Celebration Hall',
      },
    },
  ],
};

describe('EventLocationSection map fallback', () => {
  before(() => {
    domHandle = installDom();
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('keeps directions links visible when the secure map URL cannot be created', async () => {
    mock.method(globalThis, 'fetch', async () => ({
      ok: false,
      status: 503,
      json: async () => ({ error: 'Maps service unavailable' }),
    }) as Response);

    const view = render(<EventLocationSection wedding={weddingWithLocation as any} />);

    await view.findByText('Map unavailable');

    assert.equal(
      view.getByRole('heading', { name: 'The Celebration Hall' }).textContent,
      'The Celebration Hall',
    );
    assert.equal(
      view.getByRole('link', { name: 'Open in Google Maps' }).getAttribute('href'),
      'https://www.google.com/maps/search/?api=1&query=123%20Wedding%20Lane%2C%20Oklahoma%20City%2C%20OK',
    );
    assert.equal(
      view.getByRole('link', { name: 'Open in Apple Maps' }).getAttribute('href'),
      'https://maps.apple.com/?q=123%20Wedding%20Lane%2C%20Oklahoma%20City%2C%20OK',
    );
  });
});
