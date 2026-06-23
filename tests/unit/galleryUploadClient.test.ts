import { afterEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

import { uploadGalleryFileViaPresignedUrl } from '../../app/admin/gallery/upload/galleryUploadClient';

const originalFetch = globalThis.fetch;

afterEach(() => {
  mock.restoreAll();
  if (originalFetch) {
    globalThis.fetch = originalFetch;
  }
});

describe('uploadGalleryFileViaPresignedUrl', () => {
  it('requests a presigned URL and uploads the file directly to storage', async () => {
    const file = new File(['image-bytes'], 'hero image.jpg', { type: 'image/jpeg' });
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ input, init });
      if (calls.length === 1) {
        return new Response(
          JSON.stringify({
            upload_url: 'https://r2.example/upload?signature=abc',
            key: 'gallery/planner-1/jane-john/hero.jpg',
          }),
          {
            status: 200,
            headers: { 'content-type': 'application/json' },
          }
        );
      }
      return new Response('', { status: 200 });
    });

    const result = await uploadGalleryFileViaPresignedUrl({
      baseUrl: 'https://api.example.com',
      token: 'admin-token',
      file,
      weddingSlug: 'jane-john',
      folder: 'gallery',
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    assert.deepEqual(result, { key: 'gallery/planner-1/jane-john/hero.jpg' });
    assert.equal(fetchMock.mock.callCount(), 2);
    assert.equal(
      calls[0].input.toString(),
      'https://api.example.com/admin/gallery/upload-url?filename=hero+image.jpg&wedding_slug=jane-john&folder=gallery'
    );
    assert.equal(
      (calls[0].init?.headers as Record<string, string>).Authorization,
      'Bearer admin-token'
    );
    assert.equal(calls[1].input.toString(), 'https://r2.example/upload?signature=abc');
    assert.equal(calls[1].init?.method, 'PUT');
    assert.equal(calls[1].init?.body, file);
    assert.equal(
      (calls[1].init?.headers as Record<string, string>).Authorization,
      undefined
    );
    assert.equal(
      (calls[1].init?.headers as Record<string, string>)['Content-Type'],
      'image/jpeg'
    );
  });

  it('surfaces presign failures before attempting storage upload', async () => {
    const file = new File(['image-bytes'], 'hero.jpg', { type: 'image/jpeg' });
    const fetchMock = mock.fn(async () =>
      new Response(JSON.stringify({ detail: 'Access denied' }), {
        status: 403,
        headers: { 'content-type': 'application/json' },
      })
    );

    await assert.rejects(
      uploadGalleryFileViaPresignedUrl({
        baseUrl: 'https://api.example.com',
        token: 'admin-token',
        file,
        weddingSlug: 'jane-john',
        folder: 'gallery',
        fetchImpl: fetchMock as unknown as typeof fetch,
      }),
      /Access denied/
    );
    assert.equal(fetchMock.mock.callCount(), 1);
  });

  it('surfaces direct storage upload failures', async () => {
    const file = new File(['image-bytes'], 'hero.jpg', { type: 'image/jpeg' });
    let callIndex = 0;
    const fetchMock = mock.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => {
      callIndex += 1;
      if (callIndex === 1) {
        return new Response(
          JSON.stringify({
            upload_url: 'https://r2.example/upload?signature=abc',
            key: 'gallery/jane-john/hero.jpg',
          }),
          {
            status: 200,
            headers: { 'content-type': 'application/json' },
          }
        );
      }
      return new Response('R2 unavailable', { status: 503 });
    });

    await assert.rejects(
      uploadGalleryFileViaPresignedUrl({
        baseUrl: 'https://api.example.com',
        token: 'admin-token',
        file,
        weddingSlug: 'jane-john',
        folder: 'gallery',
        fetchImpl: fetchMock as unknown as typeof fetch,
      }),
      /R2 unavailable/
    );
    assert.equal(fetchMock.mock.callCount(), 2);
  });
});
