import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com';

let budgetApi: typeof import('../../app/services/budgetApi')['budgetApi'];

const originalFetch = globalThis.fetch;

describe('budgetApi payments', () => {
  before(async () => {
    ({ budgetApi } = await import('../../app/services/budgetApi'));
  });

  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      delete (globalThis as typeof globalThis & { fetch?: typeof fetch }).fetch;
    }
  });

  after(() => {
    budgetApi = undefined as unknown as typeof budgetApi;
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

describe('budgetApi templates', () => {
  before(async () => {
    ({ budgetApi } = await import('../../app/services/budgetApi'));
  });

  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      delete (globalThis as any).fetch;
    }
  });

  after(() => {
    budgetApi = undefined as unknown as typeof budgetApi;
  });

  it('normalises template payloads from the API response', async () => {
    const rawTemplates = [
      {
        _id: { $oid: '507f1f77bcf86cd799439011' },
        name: 'Destination Delight',
        wedding_type: 'destination',
        target_budget_min: 40000,
        target_budget_max: 85000,
        guest_count_range: { min: 80, max: 180 },
        categories: [
          { name: 'Venue & Catering', percentage: 45, priority: 1 },
          { name: 'Design & Decor', percentage: 20, priority: 2 },
        ],
        created_by: 'planner@example.com',
        is_public: true,
        created_at: '2025-02-01T00:00:00.000Z',
        updated_at: '2025-02-01T00:00:00.000Z',
      },
    ];

    const fetchMock = mock.fn(async () =>
      new Response(
        JSON.stringify({ templates: rawTemplates }),
        { status: 200 }
      )
    );

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const templates = await budgetApi.getBudgetTemplates('secret-token');

    assert.equal(fetchMock.mock.callCount(), 1);
    assert.equal(templates.length, 1);
    assert.equal(templates[0].id, '507f1f77bcf86cd799439011');
    assert.equal(templates[0].guest_count_range.max, 180);
    assert.equal(templates[0].categories[0].name, 'Venue & Catering');
  });

  it('creates a template with validation-friendly payloads and surfaces API errors', async () => {
    const successResponse = {
      template: {
        id: 'template_123',
        name: 'Modern Minimalist',
        wedding_type: 'modern',
        target_budget_min: 20000,
        target_budget_max: 48000,
        guest_count_range: { min: 50, max: 120 },
        categories: [
          { name: 'Venue', percentage: 40, priority: 1 },
          { name: 'Design', percentage: 30, priority: 2 },
          { name: 'Entertainment', percentage: 15, priority: 3 },
          { name: 'Beauty', percentage: 15, priority: 3 },
        ],
        is_public: false,
        created_at: '2025-02-01T00:00:00.000Z',
        updated_at: '2025-02-01T00:00:00.000Z',
      },
    };

    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(input.toString(), 'https://api.example.com/admin/budget/templates');
      assert.equal(init?.method, 'POST');
      const headers = init?.headers as Record<string, string> | undefined;
      assert.equal(headers?.Authorization ?? headers?.authorization, 'Bearer secret-token');

      const body = JSON.parse(init?.body as string);
      assert.equal(body.name, 'Modern Minimalist');
      assert.equal(body.categories.length, 4);
      assert.equal(body.categories[0].percentage, 40);

      return new Response(JSON.stringify(successResponse), { status: 201 });
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const template = await budgetApi.createBudgetTemplate('secret-token', {
      name: 'Modern Minimalist',
      wedding_type: 'modern',
      target_budget_min: 20000,
      target_budget_max: 48000,
      guest_count_range: { min: 50, max: 120 },
      categories: [
        { name: 'Venue', percentage: 40, priority: 1 },
        { name: 'Design', percentage: 30, priority: 2 },
        { name: 'Entertainment', percentage: 15, priority: 3 },
        { name: 'Beauty', percentage: 15, priority: 3 },
      ],
    });

    assert.equal(template.id, 'template_123');
    assert.equal(template.categories[1].priority, 2);

    const errorFetch = mock.fn(async () =>
      new Response(JSON.stringify({ detail: 'Category percentages must total 100%' }), { status: 400 })
    );

    globalThis.fetch = errorFetch as unknown as typeof fetch;

    await assert.rejects(
      budgetApi.createBudgetTemplate('secret-token', {
        name: 'Broken Template',
        wedding_type: 'modern',
        target_budget_min: 10000,
        target_budget_max: 20000,
        guest_count_range: { min: 20, max: 40 },
        categories: [
          { name: 'Venue', percentage: 40, priority: 1 },
          { name: 'Decor', percentage: 30, priority: 2 },
        ],
      }),
      /Category percentages must total 100%/
    );
  });
});
