import { after, afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, render } from '@testing-library/react';

import { installDom } from './testDom';

let ContractTemplate: typeof import('../../app/components/contracts/ContractTemplate').default;
let domHandle: ReturnType<typeof installDom> | null = null;

describe('ContractTemplate', () => {
  before(async () => {
    domHandle = installDom();
    ({ default: ContractTemplate } = await import('../../app/components/contracts/ContractTemplate'));
  });

  afterEach(() => {
    cleanup();
  });

  after(() => {
    domHandle = null;
  });

  it('prefers live scheduled payments over the frozen package snapshot after signing', () => {
    const view = render(
      <ContractTemplate
        packageSnapshot={{
          name: 'Signature Package',
          total_amount: 1500,
          currency: 'USD',
          services: [],
          payment_schedule: [
            { name: 'Deposit', trigger: 'on_signing', amount: 1000 },
            { name: 'Final Payment', trigger: 'days_after_signing', amount: 500, days_after: 7 },
          ],
        }}
        couple={{ partner1_name: 'Alex', email: 'alex@example.com' }}
        status="signed"
        scheduledPayments={[
          {
            id: 'payment-1',
            name: 'Deposit',
            amount: 1000,
            currency: 'USD',
            due_date: '2026-04-29T12:00:00.000Z',
            status: 'succeeded',
            paid_at: '2026-04-29T12:05:00.000Z',
          },
          {
            id: 'payment-2',
            name: 'Final Payment',
            amount: 500,
            currency: 'USD',
            due_date: '2026-05-06T12:00:00.000Z',
            status: 'scheduled',
          },
        ]}
      />
    );

    assert.equal(view.getAllByText('Paid').length >= 1, true);
    assert.equal(view.getAllByText('Scheduled').length >= 1, true);
    view.getByText(/Paid on/);
    view.getByText(/Due /);
    assert.equal(view.getAllByText(/\$1,000\.00/).length >= 1, true);
    assert.equal(view.getAllByText(/\$500\.00/).length >= 1, true);
    view.getByText('Remaining');
    assert.equal(document.body.textContent?.includes('7 days after signing'), false);
  });
});
