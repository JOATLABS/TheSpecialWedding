import { describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

import { fetchGalleryImagesForWedding } from '../../app/admin/gallery/upload/galleryImageListClient';

describe('fetchGalleryImagesForWedding', () => {
  it('publishes one complete image list only after every wedding folder succeeds', async () => {
    const calls: string[] = [];
    const fetchMock = mock.fn(async (input: RequestInfo | URL) => {
      const url = input.toString();
      calls.push(url);
      const prefix = new URL(url).searchParams.get('prefix');
      return new Response(
        JSON.stringify([{ key: `${prefix}photo.webp`, url: `https://media.example/${calls.length}` }]),
        { status: 200, headers: { 'content-type': 'application/json' } }
      );
    });

    const images = await fetchGalleryImagesForWedding({
      baseUrl: 'https://api.example.test',
      token: 'planner-token',
      weddingSlug: 'sofia-and-daniel',
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    assert.deepEqual(
      calls.map((url) => new URL(url).searchParams.get('prefix')),
      [
        'gallery/sofia-and-daniel/',
        'our-story/sofia-and-daniel/',
        'wedding-party/sofia-and-daniel/',
      ]
    );
    assert.deepEqual(
      images.map((image) => image.key),
      [
        'gallery/sofia-and-daniel/photo.webp',
        'our-story/sofia-and-daniel/photo.webp',
        'wedding-party/sofia-and-daniel/photo.webp',
      ]
    );
  });

  it('rejects the entire load when any folder returns a non-OK response', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL) => {
      const prefix = new URL(input.toString()).searchParams.get('prefix');
      if (prefix?.startsWith('our-story/')) {
        return new Response(JSON.stringify({ detail: 'storage unavailable' }), {
          status: 503,
          headers: { 'content-type': 'application/json' },
        });
      }
      return new Response(JSON.stringify([{ key: `${prefix}photo.webp` }]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    });

    await assert.rejects(
      fetchGalleryImagesForWedding({
        baseUrl: 'https://api.example.test',
        token: 'planner-token',
        weddingSlug: 'sofia-and-daniel',
        fetchImpl: fetchMock as unknown as typeof fetch,
      }),
      /Our Story images could not be loaded \(503\): storage unavailable/
    );
  });

  it('rejects a successful response whose payload is not an image list', async () => {
    const fetchMock = mock.fn(async () =>
      new Response(JSON.stringify({ detail: 'unexpected shape' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    );

    await assert.rejects(
      fetchGalleryImagesForWedding({
        baseUrl: 'https://api.example.test',
        token: 'planner-token',
        weddingSlug: 'sofia-and-daniel',
        fetchImpl: fetchMock as unknown as typeof fetch,
      }),
      /Public Gallery images returned an invalid response/
    );
  });
});
