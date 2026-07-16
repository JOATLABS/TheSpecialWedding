import assert from 'node:assert/strict';
import { after, afterEach, before, describe, it } from 'node:test';
import React, { useState } from 'react';
import { cleanup, render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { installDom } from './testDom';

let PlatformTabs: typeof import('../../app/admin/platform/PlatformTabs').default;
let resolvePlatformPrimaryView: typeof import('../../app/admin/platform/platformViewState').resolvePlatformPrimaryView;
let domHandle: ReturnType<typeof installDom> | null = null;

describe('storefront operator platform shell', () => {
  before(async () => {
    domHandle = installDom();
    ({ default: PlatformTabs } = await import(
      '../../app/admin/platform/PlatformTabs'
    ));
    ({ resolvePlatformPrimaryView } = await import(
      '../../app/admin/platform/platformViewState'
    ));
  });

  afterEach(() => cleanup());

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('keeps the storefront review queue available when platform health fails', () => {
    assert.equal(
      resolvePlatformPrimaryView({
        activeTab: 'storefront',
        authLoading: false,
        healthLoading: false,
        isRootAdmin: true,
        hasMetrics: false,
        hasHealthError: true,
      }),
      'storefront',
    );
    assert.equal(
      resolvePlatformPrimaryView({
        activeTab: 'health',
        authLoading: false,
        healthLoading: false,
        isRootAdmin: true,
        hasMetrics: false,
        hasHealthError: true,
      }),
      'health_error',
    );
  });

  it('provides keyboard tabs and horizontal mobile overflow', async () => {
    function Harness() {
      const [active, setActive] = useState<
        import('../../app/admin/platform/PlatformTabs').PlatformTabId
      >('health');
      return <PlatformTabs activeTab={active} onChange={setActive} />;
    }

    const user = userEvent.setup({ document: window.document });
    const view = render(<Harness />);
    const tablist = view.getByRole('tablist', {
      name: /platform infrastructure sections/i,
    });
    const health = view.getByRole('tab', { name: /system health/i });
    const errors = view.getByRole('tab', { name: /^errors$/i });
    const storefront = view.getByRole('tab', { name: /storefront domains/i });

    assert.equal(health.getAttribute('aria-selected'), 'true');
    assert.equal(health.getAttribute('tabindex'), '0');
    assert.equal(storefront.getAttribute('tabindex'), '-1');
    assert.match(tablist.parentElement?.className ?? '', /overflow-x-auto/);
    assert.match(tablist.className, /min-w-max/);

    health.focus();
    await user.keyboard('{ArrowRight}');
    assert.equal(document.activeElement, errors);
    assert.equal(errors.getAttribute('aria-selected'), 'true');
    await user.keyboard('{End}');
    const backups = view.getByRole('tab', { name: /backups/i });
    assert.equal(document.activeElement, backups);
    assert.equal(backups.getAttribute('aria-selected'), 'true');
    await user.keyboard('{Home}');
    assert.equal(document.activeElement, health);
  });
});
