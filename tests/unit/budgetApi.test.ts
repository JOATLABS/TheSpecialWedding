import { afterEach, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com';

const { budgetApi } = await import('../../app/services/budgetApi');

const originalFetch = globalThis.fetch;

describe('budgetApi payments', () => {
  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (globalThis as any).fetch;
    }
  });

  it('records a payment with the correct request payload and headers', async () => {
    const responseBody = {
      payment: {
        id: 'pay_123',
        category_id: 'cat_1',
        amount: 1200,
        payment_method: 'card',
        payment_date: '2025-02-01T00:00:00.000Z',
        status: 'completed',
        created_at: '2025-02-01T00:00:00.000Z',
      },
    };

    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(init?.method, 'POST');
      assert.ok(init?.body);

      const parsedBody = JSON.parse(init?.body as string);
      assert.equal(parsedBody.amount, 1200);
      assert.equal(parsedBody.payment_method, 'card');

      const headers = init?.headers as Record<string, string> | undefined;
      assert.equal(headers?.Authorization ?? headers?.authorization, 'Bearer secret-token');

      assert.equal(
        input.toString(),
        'https://api.example.com/admin/budget/category/cat_1/payment'
      );

      return new Response(JSON.stringify(responseBody), { status: 200 });
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await budgetApi.recordPayment('secret-token', 'cat_1', {
      amount: 1200,
      payment_method: 'card',
      payment_date: '2025-02-01T00:00:00.000Z',
      status: 'completed',
    });

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.deepEqual(result, responseBody.payment);
  });

  it('throws a friendly error when recording a payment fails', async () => {
    const fetchMock = mock.fn(async () => new Response('error', { status: 500 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await assert.rejects(
      budgetApi.recordPayment('secret-token', 'cat_2', {
        amount: 500,
        payment_method: 'cash',
        payment_date: '2025-02-02T00:00:00.000Z',
      }),
      /Failed to record payment/
    );
  });

  it('fetches payment history and returns the parsed array', async () => {
    const payments = [
      {
        id: 'pay_1',
        category_id: 'cat_1',
        amount: 800,
        payment_method: 'transfer',
        payment_date: '2025-02-10T00:00:00.000Z',
        status: 'completed',
        created_at: '2025-02-10T00:00:00.000Z',
      },
    ];

    const fetchMock = mock.fn(async (input: RequestInfo | URL) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/admin/weddings/wed_1/payments'
      );

      return new Response(JSON.stringify({ payments }), { status: 200 });
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await budgetApi.getPaymentHistory('secret-token', 'wed_1');
    assert.equal(fetchMock.mock.callCount(), 1);
    assert.deepEqual(result, payments);
  });

  it('returns an empty array when the history payload is malformed', async () => {
    const fetchMock = mock.fn(async () => new Response(JSON.stringify({ foo: 'bar' }), { status: 200 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await budgetApi.getPaymentHistory('secret-token', 'wed_2');
    assert.deepEqual(result, []);
  });
});
