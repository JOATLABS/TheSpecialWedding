import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { installDom } from './testDom';

let RSVPHelpBlock: typeof import('../../app/components/landing-page/RSVPHelpBlock')['RSVPHelpBlock'];
let GuestHelpRequestModal: typeof import('../../app/components/GuestHelpRequestModal').default;
let domHandle: ReturnType<typeof installDom> | null = null;

describe('public RSVP help request UI', () => {
  before(async () => {
    domHandle = installDom();
    ({ RSVPHelpBlock } = await import('../../app/components/landing-page/RSVPHelpBlock'));
    ({ default: GuestHelpRequestModal } = await import('../../app/components/GuestHelpRequestModal'));
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

  it('hides planner phone numbers and opens the help action when configured private', () => {
    const onRequestHelp = mock.fn();
    const view = render(
      <RSVPHelpBlock
        rsvpConfig={{
          help_text: 'Need RSVP support?',
          phone_numbers: ['682-234-9448'],
          hide_phone_numbers: true,
          help_button_label: 'Get Help',
        }}
        onRequestHelp={onRequestHelp}
      />
    );

    assert.equal(view.queryByText(/682-234-9448/), null);

    fireEvent.click(view.getByRole('button', { name: /get help/i }));

    assert.equal(onRequestHelp.mock.calls.length, 1);
  });

  it('keeps visible phone numbers display-only when planner unhides them', () => {
    const onRequestHelp = mock.fn();
    const view = render(
      <RSVPHelpBlock
        rsvpConfig={{
          help_text: 'Call if needed.',
          phone_numbers: ['682-234-9448'],
          hide_phone_numbers: false,
          help_button_label: 'Get Help',
        }}
        onRequestHelp={onRequestHelp}
      />
    );

    assert.notEqual(view.getByText(/682-234-9448/), null);
    assert.equal(view.queryByRole('button', { name: /get help/i }), null);
    assert.equal(view.queryByRole('link', { name: /682-234-9448/ }), null);
    assert.equal(onRequestHelp.mock.calls.length, 0);
  });

  it('validates and submits the guest help modal to the public endpoint', async () => {
    const fetchCalls: Array<{ url: string; body: Record<string, unknown> }> = [];
    mock.method(globalThis, 'fetch', async (url: string, init?: RequestInit) => {
      fetchCalls.push({
        url,
        body: JSON.parse(String(init?.body || '{}')) as Record<string, unknown>,
      });
      return {
        ok: true,
        json: async () => ({ success: true }),
      } as Response;
    });

    const view = render(
      <GuestHelpRequestModal
        isOpen
        onClose={() => undefined}
        slug="peace-emmanuel"
        coupleName="Peace & Emmanuel"
      />
    );

    fireEvent.click(view.getByRole('button', { name: /text me/i }));
    assert.notEqual(await view.findByText(/enter your full name/i), null);

    const user = userEvent.setup({ document: window.document });
    await user.type(view.getByLabelText(/full name/i), 'Ayo Guest');
    await user.type(view.getByLabelText(/phone number/i), '(682) 234-9448');
    await user.type(view.getByLabelText(/relationship/i), "Bride's cousin");
    fireEvent.click(view.getByRole('button', { name: /text me/i }));

    await waitFor(() => {
      assert.equal(fetchCalls.length, 1);
    });
    assert.equal(fetchCalls[0].url, '/api/proxy/guests/help-request');
    assert.deepEqual(fetchCalls[0].body, {
      slug: 'peace-emmanuel',
      full_name: 'Ayo Guest',
      phone: '(682) 234-9448',
      relationship_to_couple: "Bride's cousin",
    });
    assert.notEqual(await view.findByText(/check your text messages/i), null);
  });
});
