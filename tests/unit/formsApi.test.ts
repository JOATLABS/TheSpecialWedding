import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

declare const global: typeof globalThis;

process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com';

let formsApi: typeof import('../../app/services/formsApi')['formsApi'];

const originalFetch = global.fetch;

describe('formsApi', () => {
  before(async () => {
    ({ formsApi } = await import('../../app/services/formsApi'));
  });

  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    if (originalFetch) {
      global.fetch = originalFetch;
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (global as any).fetch;
    }
  });

  after(() => {
    formsApi = undefined as unknown as typeof formsApi;
  });

  it('creates a blank form with accessibility-safe defaults', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(input.toString(), 'https://api.example.com/admin/forms');
      assert.equal(init?.method, 'POST');

      const headers = init?.headers as Record<string, string> | undefined;
      assert.equal(headers?.Authorization ?? headers?.authorization, 'Bearer token-123');

      const parsedBody = JSON.parse(init?.body as string);
      assert.equal(parsedBody.name, 'Guest RSVP Intake');
      assert.equal(parsedBody.settings.title, 'Guest RSVP Intake');
      assert.equal(parsedBody.settings.collect_email, true);
      assert.equal(parsedBody.settings.is_public, false);
      assert.deepEqual(parsedBody.fields, []);

      return new Response(JSON.stringify({ id: 'form_123' }), { status: 200 });
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    await formsApi.createBlankForm('token-123', {
      name: 'Guest RSVP Intake',
      description: 'Gather RSVPs and meal preferences.',
      isPublic: false,
      collectEmail: true,
    });

    assert.equal(fetchMock.mock.callCount(), 1);
  });

  it('builds the template creation URL with query parameters', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/forms/from-template/template_a?form_name=Summer+Showcase',
      );
      return new Response(JSON.stringify({ id: 'form_456' }), { status: 200 });
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    await formsApi.createFromTemplate('token-abc', {
      templateId: 'template_a',
      name: 'Summer Showcase',
    });

    assert.equal(fetchMock.mock.callCount(), 1);
  });

  it('duplicates a form with the correct payload', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(input.toString(), 'https://api.example.com/admin/forms/form_789/duplicate');
      assert.equal(init?.method, 'POST');

      const parsedBody = JSON.parse(init?.body as string);
      assert.equal(parsedBody.new_name, 'Vendor Intake Copy');

      return new Response(JSON.stringify({ id: 'form_987' }), { status: 200 });
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    await formsApi.duplicateForm('token-xyz', {
      formId: 'form_789',
      name: 'Vendor Intake Copy',
    });

    assert.equal(fetchMock.mock.callCount(), 1);
  });

  it('marks responses as viewed and forwards the submission count', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(input.toString(), 'https://api.example.com/admin/forms/form_222/views');
      assert.equal(init?.method, 'POST');

      const parsedBody = JSON.parse(init?.body as string);
      assert.equal(parsedBody.scope, 'responses');
      assert.equal(parsedBody.submission_count, 12);

      return new Response(JSON.stringify({ message: 'ok' }), { status: 200 });
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    await formsApi.markScopeViewed('token', 'form_222', 'responses', 12);

    assert.equal(fetchMock.mock.callCount(), 1);
  });

  it('normalises form lists with sensible defaults', async () => {
    const fetchMock = mock.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            id: 'form_1',
            name: 'Feedback',
            settings: { title: 'Feedback', is_public: true },
            submission_count: 4,
            unread_responses: 2,
            created_at: '2025-02-01T12:00:00.000Z',
          },
          {
            id: 'form_2',
            name: 'Vendors',
            settings: { title: 'Vendors', is_public: false },
          },
        ]),
        { status: 200 },
      );
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    const results = await formsApi.fetchForms('token');

    assert.equal(results.length, 2);
    assert.deepEqual(results[0], {
      id: 'form_1',
      name: 'Feedback',
      settings: { title: 'Feedback', description: undefined, is_public: true },
      template_type: undefined,
      wedding_id: undefined,
      submission_count: 4,
      unread_responses: 2,
      created_at: '2025-02-01T12:00:00.000Z',
    });
    assert.equal(results[1].submission_count, 0);
    assert.equal(results[1].unread_responses, 0);
  });
});
