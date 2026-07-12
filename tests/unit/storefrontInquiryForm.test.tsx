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
      <StorefrontInquiryForm identifier="studio & co" fetchImpl={fetchImpl} />,
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
    const fetchImpl: typeof fetch = async () => responses.shift() as Response;
    const view = render(
      <StorefrontInquiryForm identifier="studio.example" fetchImpl={fetchImpl} />,
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
  });
});
