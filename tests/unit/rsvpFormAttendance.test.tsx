import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';

import { WeddingContext } from '../../app/contexts/WeddingContext';
import { installDom } from './testDom';

let RSVPForm: typeof import('../../app/components/RSVPForm').default;
let domHandle: ReturnType<typeof installDom> | null = null;

const wedding = {
  id: 'wedding-1',
  slug: 'felix-angelina',
  couple_names: 'Felix and Angelina',
  theme_config: {
    accent_color: '#D4A5A5',
    secondary_color: '#E9C46A',
  },
  events: [
    {
      type: 'after_party',
      custom_type_label: 'After Party',
      date: '',
      details: {},
    },
  ],
};

describe('RSVPForm attendance choice', () => {
  before(async () => {
    domHandle = installDom();
    ({ default: RSVPForm } = await import('../../app/components/RSVPForm'));
  });

  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('requires an event selection when the guest says they will attend', async () => {
    const fetchCalls: Array<Record<string, unknown>> = [];
    mock.method(globalThis, 'fetch', async (_url: string, init?: RequestInit) => {
      fetchCalls.push(JSON.parse(String(init?.body || '{}')) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({ message: 'RSVP submitted successfully' }),
      } as Response;
    });

    const view = render(
      <WeddingContext.Provider value={wedding as any}>
        <RSVPForm
          guest={{
            id: 'guest-1',
            name: 'Neraaj',
            phone: '4053148119',
            plus_one_allowed: false,
            number_of_plus_ones_allowed: 0,
          }}
          slug="felix-angelina"
        />
      </WeddingContext.Provider>,
    );

    fireEvent.click(view.getByLabelText(/i will attend/i));
    assert.equal((view.getByLabelText(/after party/i) as HTMLInputElement).checked, false);

    fireEvent.click(view.getByRole('button', { name: /confirm rsvp/i }));

    assert.equal(fetchCalls.length, 0);
    assert.notEqual(await view.findByText(/select at least one event/i), null);
  });

  it('submits selected custom event ids when the guest says they will attend', async () => {
    const fetchCalls: Array<Record<string, unknown>> = [];
    mock.method(globalThis, 'fetch', async (_url: string, init?: RequestInit) => {
      fetchCalls.push(JSON.parse(String(init?.body || '{}')) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({ message: 'RSVP submitted successfully' }),
      } as Response;
    });

    const view = render(
      <WeddingContext.Provider value={wedding as any}>
        <RSVPForm
          guest={{
            id: 'guest-1',
            name: 'Neraaj',
            phone: '4053148119',
            plus_one_allowed: false,
            number_of_plus_ones_allowed: 0,
          }}
          slug="felix-angelina"
        />
      </WeddingContext.Provider>,
    );

    fireEvent.click(view.getByLabelText(/i will attend/i));
    fireEvent.click(view.getByLabelText(/after party/i));
    fireEvent.click(view.getByRole('button', { name: /confirm rsvp/i }));

    await waitFor(() => {
      assert.equal(fetchCalls.length, 1);
    });
    assert.equal(fetchCalls[0].attendance_choice, undefined);
    assert.deepEqual(fetchCalls[0].attending, ['after_party']);
    assert.notEqual(await view.findByText(/calendar invite has been downloaded/i), null);
  });

  it('submits an explicit decline without carrying event selections forward', async () => {
    const fetchCalls: Array<Record<string, unknown>> = [];
    mock.method(globalThis, 'fetch', async (_url: string, init?: RequestInit) => {
      fetchCalls.push(JSON.parse(String(init?.body || '{}')) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({ message: 'RSVP submitted successfully' }),
      } as Response;
    });

    const view = render(
      <WeddingContext.Provider value={wedding as any}>
        <RSVPForm
          guest={{
            id: 'guest-1',
            name: 'Neraaj',
            phone: '4053148119',
            plus_one_allowed: false,
            number_of_plus_ones_allowed: 0,
          }}
          slug="felix-angelina"
        />
      </WeddingContext.Provider>,
    );

    fireEvent.click(view.getByLabelText(/i will attend/i));
    fireEvent.click(view.getByLabelText(/after party/i));
    fireEvent.click(view.getByLabelText(/i cannot attend/i));
    assert.equal((view.getByLabelText(/after party/i) as HTMLInputElement).checked, false);
    fireEvent.click(view.getByRole('button', { name: /confirm rsvp/i }));

    await waitFor(() => {
      assert.equal(fetchCalls.length, 1);
    });
    assert.equal(fetchCalls[0].attendance_choice, undefined);
    assert.deepEqual(fetchCalls[0].attending, []);
    assert.notEqual(await view.findByText(/cannot attend/i), null);
    assert.equal(view.queryByText(/download calendar invite again/i), null);
  });
});
