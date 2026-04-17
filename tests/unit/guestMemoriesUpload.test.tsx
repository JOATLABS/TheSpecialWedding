import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { installDom } from './testDom';

let GuestMemoriesUploadClient: typeof import('../../app/[slug]/upload/[uploadToken]/upload-client').default;
let domHandle: ReturnType<typeof installDom> | null = null;
let originalShowPickerDescriptor: PropertyDescriptor | undefined;
type InputPrototypeWithOptionalShowPicker = HTMLInputElement & {
  showPicker?: () => void;
};

function removeShowPickerPrototype() {
  Reflect.deleteProperty(
    window.HTMLInputElement.prototype as InputPrototypeWithOptionalShowPicker,
    'showPicker'
  );
}

const contextPayload = {
  wedding: {
    slug: 'james-and-mel',
    couple_names: 'James and Mel',
    date: '2027-03-16T00:00:00.000Z',
  },
  guest_media: {
    enabled: true,
    upload_closes_at: '2027-03-16T23:59:59.000Z',
    link_status: 'open' as const,
    storage_ready: true,
    stream_configured: true,
  },
  events: [
    { value: 'ceremony', label: 'Ceremony' },
    { value: 'not_sure', label: 'Not sure' },
  ],
  limits: {
    max_files_per_batch: 25,
    max_image_size_bytes: 10 * 1024 * 1024,
    max_video_size_bytes: 100 * 1024 * 1024,
    max_batch_size_bytes: 250 * 1024 * 1024,
    accepted_types: ['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/quicktime'],
    not_sure_value: 'not_sure',
  },
};

describe('GuestMemoriesUploadClient upload picker', () => {
  before(async () => {
    domHandle = installDom();
    originalShowPickerDescriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'showPicker');
    ({ default: GuestMemoriesUploadClient } = await import('../../app/[slug]/upload/[uploadToken]/upload-client'));
  });

  beforeEach(() => {
    mock.restoreAll();
    mock.method(globalThis, 'fetch', async () => ({
      ok: true,
      status: 200,
      json: async () => contextPayload,
    }) as Response);
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
    if (originalShowPickerDescriptor) {
      Object.defineProperty(window.HTMLInputElement.prototype, 'showPicker', originalShowPickerDescriptor);
    } else {
      removeShowPickerPrototype();
    }
  });

  after(() => {
    domHandle = null;
  });

  async function renderIntoUploadStep() {
    const view = render(
      <GuestMemoriesUploadClient slug="james-and-mel" uploadToken="upload-token" />
    );

    await view.findByText('James and Mel');
    const firstContinue = view.getAllByRole('button', { name: /^continue$/i })[0];
    const user = userEvent.setup({ document: window.document });
    const guestNameInput = view.getByRole('textbox', { name: 'Your display name' }) as HTMLInputElement;
    await user.type(guestNameInput, 'Alex Guest');
    assert.equal(guestNameInput.value, 'Alex Guest');
    await waitFor(() => {
      assert.equal(firstContinue.hasAttribute('disabled'), false);
    });

    fireEvent.click(firstContinue);
    await view.findByText('What part of the celebration did you capture?');
    fireEvent.click(view.getByRole('button', { name: /add media/i }));
    await view.findByText('Upload your photos and videos');

    return view;
  }

  it('prefers showPicker when the browser supports it', async () => {
    const showPickerCalls: unknown[][] = [];
    const clickCalls: unknown[][] = [];
    Object.defineProperty(window.HTMLInputElement.prototype, 'showPicker', {
      configurable: true,
      writable: true,
      value: function (...args: unknown[]) {
        showPickerCalls.push(args);
      },
    });
    mock.method(window.HTMLInputElement.prototype, 'click', function (...args: unknown[]) {
      clickCalls.push(args);
    });

    const view = await renderIntoUploadStep();

    const uploadButton = view.getByRole('button', { name: /tap to add photos or videos/i });
    fireEvent.click(uploadButton);

    assert.equal(showPickerCalls.length, 1);
    assert.equal(clickCalls.length, 0);
  });

  it('falls back to click when showPicker is unavailable', async () => {
    const clickCalls: unknown[][] = [];
    removeShowPickerPrototype();
    mock.method(window.HTMLInputElement.prototype, 'click', function (...args: unknown[]) {
      clickCalls.push(args);
    });

    const view = await renderIntoUploadStep();

    const uploadButton = view.getByRole('button', { name: /tap to add photos or videos/i });
    fireEvent.click(uploadButton);

    assert.equal(clickCalls.length, 1);
  });
});
