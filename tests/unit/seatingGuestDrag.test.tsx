import { after, afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, render } from '@testing-library/react';

import { installDom } from './testDom';
import { Guest } from '../../app/types/table';

let DndContext: typeof import('@dnd-kit/core')['DndContext'];
let GuestItem: typeof import('../../app/admin/components/seating/GuestItem')['GuestItem'];
let getGuestItemStyle: typeof import('../../app/admin/components/seating/GuestItem')['getGuestItemStyle'];
let domHandle: ReturnType<typeof installDom> | null = null;

const guest: Guest = {
  id: 'guest-1',
  wedding_id: 'wedding-1',
  name: 'Ada Lovelace',
  group_id: 'Family',
  table_id: null,
};

describe('seating guest drag controls', () => {
  before(async () => {
    domHandle = installDom();
    ({ DndContext } = await import('@dnd-kit/core'));
    ({ GuestItem, getGuestItemStyle } = await import('../../app/admin/components/seating/GuestItem'));
  });

  afterEach(() => {
    cleanup();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('scopes drag activation to a per-guest handle', () => {
    const view = render(
      <DndContext>
        <GuestItem guest={guest} />
      </DndContext>
    );

    const row = view.getByTestId('guest-item-guest-1');
    const handle = view.getByRole('button', { name: 'Drag Ada Lovelace to a table' });

    assert.equal(row.textContent?.includes('Ada Lovelace'), true);
    assert.match(handle.className, /cursor-grab/);
    assert.doesNotMatch(row.className, /cursor-grab/);
    assert.equal(handle.getAttribute('title'), 'Drag guest');
  });

  it('keeps the source row anchored while the drag overlay follows the pointer', () => {
    const style = getGuestItemStyle(true);

    assert.equal(style.transform, undefined);
    assert.equal(style.opacity, 0.35);
    assert.equal(style.transition, 'none');
  });
});
