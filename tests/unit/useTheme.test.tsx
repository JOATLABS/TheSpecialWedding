import { after, afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, render, waitFor } from '@testing-library/react';

import type { Wedding } from '../../app/types/wedding';
import { installDom } from './testDom';

let useTheme: typeof import('../../app/hooks/useTheme')['useTheme'];
let domHandle: ReturnType<typeof installDom> | null = null;

function ThemeProbe({ wedding }: { wedding: Wedding }) {
  const theme = useTheme(wedding);

  return (
    <div data-testid="theme-probe">
      {theme.getPrimaryColor()}|{theme.getSecondaryColor()}|{theme.getAccentColor()}
    </div>
  );
}

describe('public wedding theme hook', () => {
  before(async () => {
    domHandle = installDom();
    ({ useTheme } = await import('../../app/hooks/useTheme'));
  });

  afterEach(() => {
    cleanup();
    document.documentElement.removeAttribute('style');
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('falls back to default colors when saved theme config is incomplete', async () => {
    const wedding = {
      theme_config: {},
    } as Wedding;

    const view = render(<ThemeProbe wedding={wedding} />);

    assert.equal(
      view.getByTestId('theme-probe').textContent,
      '#1e3a5f|#d4af37|#c8847e',
    );

    await waitFor(() => {
      assert.equal(
        document.documentElement.style.getPropertyValue('--theme-primary'),
        '#1e3a5f',
      );
      assert.equal(
        document.documentElement.style.getPropertyValue('--theme-secondary'),
        '#d4af37',
      );
      assert.equal(
        document.documentElement.style.getPropertyValue('--theme-accent'),
        '#c8847e',
      );
    });
  });
});
