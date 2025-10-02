import { describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import { fetchFormResponsesCsv } from '../../app/services/formExport';

describe('fetchFormResponsesCsv', () => {
  const baseUrl = 'https://api.example.com/';
  const formId = 'form_123';
  const token = 'token-abc';

  it('builds the correct request url with filters and parses filename', async () => {
    const mockedFetch = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const responseHeaders = new Headers({
        'content-type': 'text/csv',
        'content-disposition': 'attachment; filename="custom-name.csv"',
      });

      const body = 'id,name\n1,Alice';
      return new Response(body, { status: 200, headers: responseHeaders });
    });

    const result = await fetchFormResponsesCsv({
      baseUrl,
      formId,
      token,
      options: {
        dateFrom: '2024-01-01',
        dateTo: '2024-01-31',
        includeMetadata: false,
      },
      fetchImpl: mockedFetch as unknown as typeof fetch,
    });

    assert.equal(mockedFetch.mock.callCount(), 1);

    const firstCall = mockedFetch.mock.calls[0];
    assert.ok(firstCall);
    const [requestUrl, requestInit] = firstCall.arguments as [RequestInfo | URL, RequestInit | undefined];
    assert.ok(typeof requestUrl === 'string');
    assert.match(requestUrl as string, /date_from=2024-01-01/);
    assert.match(requestUrl as string, /date_to=2024-01-31/);
    assert.match(requestUrl as string, /include_metadata=false/);

    const init = requestInit;
    assert.equal(init?.method, 'GET');

    const headers = init?.headers;
    if (headers instanceof Headers) {
      assert.equal(headers.get('Authorization'), `Bearer ${token}`);
    } else if (Array.isArray(headers)) {
      const authHeader = headers.find(([key]) => key.toLowerCase() === 'authorization');
      assert.ok(authHeader);
      assert.equal(authHeader[1], `Bearer ${token}`);
    } else if (headers) {
      const normalized = headers as Record<string, string>;
      const direct = normalized['Authorization'] ?? normalized['authorization'];
      assert.equal(direct, `Bearer ${token}`);
    } else {
      assert.fail('Expected authorization header to be set');
    }

    assert.equal(result.filename, 'custom-name.csv');
    assert.equal(result.contentType, 'text/csv');
    assert.equal(await result.blob.text(), 'id,name\n1,Alice');
  });

  it('falls back to generated filename when header missing', async () => {
    const mockedFetch = mock.fn(async () => {
      return new Response('data', { status: 200 });
    });

    const result = await fetchFormResponsesCsv({
      baseUrl,
      formId,
      token,
      fetchImpl: mockedFetch as unknown as typeof fetch,
    });

    assert.ok(result.filename.startsWith(`form_${formId}_responses_`));
    assert.equal(await result.blob.text(), 'data');
  });

  it('throws an error when the request fails', async () => {
    const mockedFetch = mock.fn(async () => {
      return new Response('error', { status: 500 });
    });

    await assert.rejects(
      fetchFormResponsesCsv({
        baseUrl,
        formId,
        token,
        fetchImpl: mockedFetch as unknown as typeof fetch,
      }),
      /Failed to export responses/,
    );
  });
});
