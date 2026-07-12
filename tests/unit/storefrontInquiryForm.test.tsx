import { after, afterEach, before, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';

import { installDom } from './testDom';

let StorefrontInquiryForm: typeof import('../../app/storefront/StorefrontInquiryForm.client').default;
let domHandle: ReturnType<typeof installDom> | null = null;

describe('StorefrontInquiryForm', () => {
  before(async () => {
    domHandle = installDom();
    ({ default: StorefrontInquiryForm } = await import(
      '../../app/storefront/StorefrontInquiryForm.client'
    ));
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('associates every field label and submits the allowlisted public payload', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetchImpl: typeof fetch = async (input, init) => {
      calls.push({ url: String(input), init });
      return {
        ok: true,
        status: 201,
        json: async () => ({
          success: true,
          inquiry_id: 'inquiry-1',
          message: 'Your inquiry was sent.',
        }),
      } as Response;
    };

    const view = render(
      <StorefrontInquiryForm
        identifier="studio & co"
        fetchImpl={fetchImpl}
        createIdempotencyKey={() => 'inquiry-key-first-submit'}
      />,
    );

    fireEvent.change(view.getByLabelText('Name'), { target: { value: 'Alex Rivera' } });
    fireEvent.change(view.getByLabelText('Email'), { target: { value: 'alex@example.com' } });
    fireEvent.change(view.getByLabelText('Phone (optional)'), { target: { value: '+1 405 555 0101' } });
    fireEvent.change(view.getByLabelText('Wedding date (optional)'), { target: { value: '2027-05-22' } });
    fireEvent.change(view.getByLabelText('How can we help?'), { target: { value: 'We need full planning.' } });
    fireEvent.click(view.getByRole('button', { name: 'Send inquiry' }));

    await view.findByText('Your inquiry was sent.');
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.url, '/api/proxy/api/storefront/studio%20%26%20co/inquiries');
    assert.equal(calls[0]?.init?.method, 'POST');
    assert.deepEqual(JSON.parse(String(calls[0]?.init?.body)), {
      name: 'Alex Rivera',
      email: 'alex@example.com',
      phone: '+1 405 555 0101',
      wedding_date: '2027-05-22',
      message: 'We need full planning.',
      idempotency_key: 'inquiry-key-first-submit',
    });
  });

  it('shows required-field feedback before making a request', async () => {
    const fetchImpl = mock.fn<typeof fetch>();
    const view = render(
      <StorefrontInquiryForm identifier="studio.example" fetchImpl={fetchImpl} />,
    );

    fireEvent.submit(view.getByRole('button', { name: 'Send inquiry' }).closest('form')!);

    assert.notEqual(await view.findByText('Enter your name, email, and a message.'), null);
    assert.equal(fetchImpl.mock.callCount(), 0);
  });

  it('retains entered values and exposes a retryable rate-limit error', async () => {
    const calls: Array<{ body: Record<string, unknown> }> = [];
    const responses = [
      {
        ok: false,
        status: 429,
        json: async () => ({ detail: 'Rate limit exceeded' }),
      },
      {
        ok: true,
        status: 201,
        json: async () => ({
          success: true,
          inquiry_id: 'inquiry-2',
          message: 'Thanks — we will be in touch.',
        }),
      },
    ];
    const fetchImpl: typeof fetch = async (_input, init) => {
      calls.push({ body: JSON.parse(String(init?.body)) as Record<string, unknown> });
      return responses.shift() as Response;
    };
    const view = render(
      <StorefrontInquiryForm
        identifier="studio.example"
        fetchImpl={fetchImpl}
        createIdempotencyKey={() => 'inquiry-key-unchanged-retry'}
      />,
    );

    fireEvent.change(view.getByLabelText('Name'), { target: { value: 'Taylor' } });
    fireEvent.change(view.getByLabelText('Email'), { target: { value: 'taylor@example.com' } });
    fireEvent.change(view.getByLabelText('How can we help?'), { target: { value: 'Month-of coordination.' } });
    fireEvent.click(view.getByRole('button', { name: 'Send inquiry' }));

    await view.findByText(/too many inquiries/i);
    assert.equal((view.getByLabelText('Name') as HTMLInputElement).value, 'Taylor');
    assert.equal((view.getByLabelText('How can we help?') as HTMLTextAreaElement).value, 'Month-of coordination.');

    fireEvent.click(view.getByRole('button', { name: 'Try again' }));
    await waitFor(() => {
      assert.notEqual(view.queryByText('Thanks — we will be in touch.'), null);
    });
    assert.equal(calls.length, 2);
    assert.equal(calls[0]?.body.idempotency_key, 'inquiry-key-unchanged-retry');
    assert.equal(calls[1]?.body.idempotency_key, 'inquiry-key-unchanged-retry');
  });

  it('creates a new idempotency key only after failed form values change', async () => {
    const keys = ['inquiry-key-before-edit', 'inquiry-key-after-edit'];
    const calls: Array<Record<string, unknown>> = [];
    const fetchImpl: typeof fetch = async (_input, init) => {
      calls.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
      if (calls.length === 1) {
        return {
          ok: false,
          status: 503,
          json: async () => ({ detail: 'Please retry.' }),
        } as Response;
      }
      return {
        ok: true,
        status: 201,
        json: async () => ({
          success: true,
          inquiry_id: 'inquiry-after-edit',
          message: 'Thanks — we will be in touch.',
        }),
      } as Response;
    };
    const view = render(
      <StorefrontInquiryForm
        identifier="studio.example"
        fetchImpl={fetchImpl}
        createIdempotencyKey={() => keys.shift() ?? 'unexpected-extra-key'}
      />,
    );

    fireEvent.change(view.getByLabelText('Name'), { target: { value: 'Taylor' } });
    fireEvent.change(view.getByLabelText('Email'), { target: { value: 'taylor@example.com' } });
    fireEvent.change(view.getByLabelText('How can we help?'), { target: { value: 'Month-of coordination.' } });
    fireEvent.click(view.getByRole('button', { name: 'Send inquiry' }));
    await view.findByText('Please retry.');

    fireEvent.input(view.getByLabelText('How can we help?'), {
      target: { value: 'Full planning instead.' },
    });
    fireEvent.click(view.getByRole('button', { name: 'Send inquiry' }));
    await view.findByText('Thanks — we will be in touch.');

    assert.equal(calls[0]?.idempotency_key, 'inquiry-key-before-edit');
    assert.equal(calls[1]?.idempotency_key, 'inquiry-key-after-edit');
  });

  it('does not reuse a key when values changed before an in-flight attempt failed', async () => {
    const keys = ['inquiry-key-in-flight', 'inquiry-key-after-in-flight-edit'];
    const calls: Array<Record<string, unknown>> = [];
    let settleFirst: ((response: Response) => void) | undefined;
    const firstResponse = new Promise<Response>((resolve) => {
      settleFirst = resolve;
    });
    const fetchImpl: typeof fetch = async (_input, init) => {
      calls.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
      if (calls.length === 1) return firstResponse;
      return {
        ok: true,
        status: 201,
        json: async () => ({
          success: true,
          inquiry_id: 'inquiry-after-in-flight-edit',
          message: 'Thanks — we will be in touch.',
        }),
      } as Response;
    };
    const view = render(
      <StorefrontInquiryForm
        identifier="studio.example"
        fetchImpl={fetchImpl}
        createIdempotencyKey={() => keys.shift() ?? 'unexpected-extra-key'}
      />,
    );

    fireEvent.change(view.getByLabelText('Name'), { target: { value: 'Taylor' } });
    fireEvent.change(view.getByLabelText('Email'), { target: { value: 'taylor@example.com' } });
    fireEvent.change(view.getByLabelText('How can we help?'), { target: { value: 'Month-of coordination.' } });
    fireEvent.click(view.getByRole('button', { name: 'Send inquiry' }));
    await waitFor(() => assert.equal(calls.length, 1));

    fireEvent.input(view.getByLabelText('How can we help?'), {
      target: { value: 'Full planning instead.' },
    });
    settleFirst?.({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Please retry.' }),
    } as Response);
    await view.findByText('Please retry.');
    fireEvent.click(view.getByRole('button', { name: 'Try again' }));
    await view.findByText('Thanks — we will be in touch.');

    assert.equal(calls[0]?.idempotency_key, 'inquiry-key-in-flight');
    assert.equal(calls[1]?.idempotency_key, 'inquiry-key-after-in-flight-edit');
  });
});
