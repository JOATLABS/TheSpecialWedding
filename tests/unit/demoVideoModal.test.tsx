import assert from 'node:assert/strict';
import { after, afterEach, before, describe, it } from 'node:test';

import { cleanup, render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';

import type { PublicDemoVideo } from '../../app/data/publicDemoVideos';
import { installDom } from './testDom';

let DemoVideoLauncher: typeof import('../../app/components/saas/DemoVideoLauncher').default;
let domHandle: ReturnType<typeof installDom> | null = null;

const PUBLISHED_DEMO: PublicDemoVideo = {
  id: 'planner-command-center-walkthrough',
  title: 'Planner command center walkthrough',
  audience: 'Professional wedding planners',
  durationSeconds: 75,
  status: 'published',
  assetUrl: '/demo-videos/exports/planner-command-center-walkthrough-16x9.mp4',
  thumbnailUrl: '/demo-videos/thumbnails/planner-command-center-walkthrough-16x9.png',
  captionUrl: '/demo-videos/captions/planner-command-center-walkthrough.vtt',
};

function renderLauncher(demo: PublicDemoVideo = PUBLISHED_DEMO) {
  return render(
    <DemoVideoLauncher demo={demo} label="Watch the planner walkthrough" variant="hero" />,
  );
}

async function openDemo(view: ReturnType<typeof renderLauncher>) {
  const user = userEvent.setup({ document: window.document });
  const launcher = view.getByRole('button', { name: 'Watch the planner walkthrough' });
  await user.click(launcher);
  const closeButton = await view.findByRole('button', { name: 'Close demo video' });
  await waitFor(() => assert.equal(document.activeElement, closeButton), { timeout: 250 });
  return { closeButton, launcher, user };
}

describe('DemoVideoLauncher modal accessibility', { concurrency: false }, () => {
  before(async () => {
    domHandle = installDom();
    ({ default: DemoVideoLauncher } = await import('../../app/components/saas/DemoVideoLauncher'));
  });

  afterEach(() => cleanup());

  after(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    domHandle?.cleanup();
    domHandle = null;
  });

  it('stays fail-closed when a demo has no approved playable asset', () => {
    const view = renderLauncher({
      ...PUBLISHED_DEMO,
      status: 'recording',
      assetUrl: undefined,
    });

    assert.equal(view.container.childElementCount, 0);
    assert.equal(view.queryByRole('button'), null);
    assert.equal(view.queryByRole('dialog'), null);
  });

  it('announces a named dialog, focuses its close control, and locks page scrolling', async () => {
    const view = renderLauncher();
    const launcher = view.getByRole('button', { name: 'Watch the planner walkthrough' });

    assert.equal(launcher.getAttribute('aria-haspopup'), 'dialog');

    const { closeButton } = await openDemo(view);
    assert.ok(view.getByRole('dialog', { name: 'Planner command center walkthrough' }));
    assert.equal(document.activeElement, closeButton);
    await waitFor(() => assert.equal(document.documentElement.style.overflow, 'hidden'));
  });

  it('keeps forward and reverse Tab navigation inside a native-video dialog', async () => {
    const view = renderLauncher();
    const { closeButton, user } = await openDemo(view);
    const player = view.container.ownerDocument.querySelector('video');
    assert.ok(player);

    await user.tab();
    assert.equal(document.activeElement, player);
    await user.tab();
    assert.equal(document.activeElement, closeButton);
    await user.tab({ shift: true });
    assert.equal(document.activeElement, player);
    await user.tab({ shift: true });
    assert.equal(document.activeElement, closeButton);
  });

  it('keeps forward and reverse Tab navigation inside an embedded-video dialog', async () => {
    const view = renderLauncher({
      ...PUBLISHED_DEMO,
      assetUrl: 'https://www.youtube.com/embed/example',
    });
    const { closeButton, user } = await openDemo(view);
    const player = view.container.ownerDocument.querySelector('iframe');
    assert.ok(player);

    await user.tab();
    assert.equal(document.activeElement, player);
    await user.tab();
    assert.equal(document.activeElement, closeButton);
    await user.tab({ shift: true });
    assert.equal(document.activeElement, player);
    await user.tab({ shift: true });
    assert.equal(document.activeElement, closeButton);
  });

  it('dismisses by close, Escape, and backdrop while restoring focus and page scrolling', async () => {
    const view = renderLauncher();

    for (const dismissal of ['close', 'escape', 'backdrop'] as const) {
      const { closeButton, launcher, user } = await openDemo(view);

      if (dismissal === 'close') await user.click(closeButton);
      if (dismissal === 'escape') await user.keyboard('{Escape}');
      if (dismissal === 'backdrop') {
        await user.click(view.getByTestId('demo-video-backdrop'));
      }

      await waitFor(() => assert.equal(view.queryByRole('dialog'), null));
      await waitFor(() => assert.equal(document.activeElement, launcher));
      await waitFor(() => assert.equal(document.documentElement.style.overflow, ''));
    }
  });

  it('does not dismiss when the user clicks the player or dialog panel', async () => {
    const view = renderLauncher();
    const { user } = await openDemo(view);
    const player = view.container.ownerDocument.querySelector('video');
    assert.ok(player);

    await user.click(player);
    assert.ok(view.getByRole('dialog', { name: 'Planner command center walkthrough' }));
    await user.click(view.getByTestId('demo-video-panel'));
    assert.ok(view.getByRole('dialog', { name: 'Planner command center walkthrough' }));
  });
});
