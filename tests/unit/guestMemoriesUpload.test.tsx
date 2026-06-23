import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { installDom } from './testDom';

let GuestMemoriesUploadClient: typeof import('../../app/[slug]/upload/[uploadToken]/upload-client').default;
let domHandle: ReturnType<typeof installDom> | null = null;
let originalShowPickerDescriptor: PropertyDescriptor | undefined;
let originalCreateObjectUrlDescriptor: PropertyDescriptor | undefined;
let originalRevokeObjectUrlDescriptor: PropertyDescriptor | undefined;
type InputPrototypeWithOptionalShowPicker = HTMLInputElement & {
  showPicker?: () => void;
};

function removeShowPickerPrototype() {
  Reflect.deleteProperty(
    window.HTMLInputElement.prototype as InputPrototypeWithOptionalShowPicker,
    'showPicker'
  );
}

async function setControlledInputValue(input: HTMLInputElement, value: string) {
  const user = userEvent.setup({ document: window.document });
  await user.clear(input);
  await user.click(input);
  await user.paste(value);
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

describe('GuestMemoriesUploadClient upload picker', { concurrency: false }, () => {
  before(async () => {
    domHandle = installDom();
    originalShowPickerDescriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'showPicker');
    originalCreateObjectUrlDescriptor = Object.getOwnPropertyDescriptor(URL, 'createObjectURL');
    originalRevokeObjectUrlDescriptor = Object.getOwnPropertyDescriptor(URL, 'revokeObjectURL');
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
    if (originalCreateObjectUrlDescriptor) {
      Object.defineProperty(URL, 'createObjectURL', originalCreateObjectUrlDescriptor);
    } else {
      Reflect.deleteProperty(URL, 'createObjectURL');
    }
    if (originalRevokeObjectUrlDescriptor) {
      Object.defineProperty(URL, 'revokeObjectURL', originalRevokeObjectUrlDescriptor);
    } else {
      Reflect.deleteProperty(URL, 'revokeObjectURL');
    }
  });

  after(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    domHandle?.cleanup();
    domHandle = null;
  });

  async function renderIntoUploadStep() {
    const view = render(
      <GuestMemoriesUploadClient slug="james-and-mel" uploadToken="upload-token" />
    );

    await view.findByText('James and Mel');
    const guestNameInput = view.getByRole('textbox', { name: 'Your display name' }) as HTMLInputElement;
    await setControlledInputValue(guestNameInput, 'Alex Guest');
    assert.equal(guestNameInput.value, 'Alex Guest');
    const firstContinue = view.getAllByRole('button', { name: /^continue$/i })[0];
    await waitFor(() => {
      assert.equal(
        view.getAllByRole('button', { name: /^continue$/i })[0].hasAttribute('disabled'),
        false,
      );
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
    const view = await renderIntoUploadStep();

    mock.method(window.HTMLInputElement.prototype, 'click', function (...args: unknown[]) {
      clickCalls.push(args);
    });
    const uploadButton = view.getByRole('button', { name: /tap to add photos or videos/i });
    fireEvent.click(uploadButton);

    assert.equal(showPickerCalls.length, 1);
    assert.equal(clickCalls.length, 0);
  });

  it('falls back to click when showPicker is unavailable', async () => {
    const clickCalls: unknown[][] = [];
    removeShowPickerPrototype();
    const view = await renderIntoUploadStep();

    mock.method(window.HTMLInputElement.prototype, 'click', function (...args: unknown[]) {
      clickCalls.push(args);
    });
    const uploadButton = view.getByRole('button', { name: /tap to add photos or videos/i });
    fireEvent.click(uploadButton);

    assert.equal(clickCalls.length, 1);
  });

  it('keeps failed files available for retry instead of clearing the batch', async () => {
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: () => 'blob:guest-memory-preview',
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: () => {},
    });

    mock.restoreAll();
    mock.method(globalThis, 'fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/guest-media/public/') && !url.includes('/upload-plan') && !url.includes('/finalize')) {
        return {
          ok: true,
          status: 200,
          json: async () => contextPayload,
        } as Response;
      }
      if (url.includes('/upload-plan')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            upload_batch_id: 'batch-1',
            assets: [
              {
                asset_id: 'asset-1',
                upload_url: 'https://uploads.example.test/asset-1',
                key: 'guest-media/test/asset-1.jpg',
                content_type: 'image/jpeg',
                media_type: 'image',
                event_type: 'ceremony',
                filename: 'failed-photo.jpg',
              },
            ],
          }),
        } as Response;
      }
      if (init?.method === 'PUT') {
        return {
          ok: false,
          status: 500,
          text: async () => 'storage error',
        } as Response;
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    const view = await renderIntoUploadStep();
    const fileInput = view.container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['guest-memory'], 'failed-photo.jpg', { type: 'image/jpeg' });

    fireEvent.change(fileInput, { target: { files: [file] } });
    await view.findByText('failed-photo.jpg');

    fireEvent.click(view.getByRole('button', { name: 'Share with the couple' }));

    await view.findByText('Needs retry');
    await view.findByText('Upload failed with status 500');
    assert.ok(view.getByRole('button', { name: 'Retry failed upload(s)' }));
    assert.ok(view.queryByRole('heading', { name: 'Thank you for sharing the moment.' }) === null);
  });
});
