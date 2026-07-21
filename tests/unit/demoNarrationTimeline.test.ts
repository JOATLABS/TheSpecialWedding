import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { getDemoVideoById } from '../../app/data/demoVideoProduction';
import { buildCaptionsForDemo } from '../../scripts/demo-videos/captions';
import {
  NARRATION_END_MARGIN_SECONDS,
  NARRATION_MAX_START_DRIFT_SECONDS,
  NARRATION_MIN_SEGMENT_GAP_SECONDS,
  placeNarrationSegments,
  planNarrationSegments,
} from '../../scripts/demo-videos/narration-timeline';

const hero = getDemoVideoById('planner-command-center-walkthrough');
const social = getDemoVideoById('connection-over-tools-social');

describe('narration timeline planning', () => {
  it('keeps every narration segment aligned with its caption cue', () => {
    assert.ok(hero);
    const durationSeconds = 75;
    const plans = planNarrationSegments(hero, durationSeconds);
    const captions = buildCaptionsForDemo(hero, durationSeconds);

    assert.equal(plans.length, hero.script.length);
    for (const plan of plans) {
      assert.equal(plan.text, hero.script[plan.index].voiceover);
      assert.equal(plan.scheduledStartSeconds, captions[plan.index].startMs / 1000);
      assert.equal(plan.scheduledEndSeconds, captions[plan.index].endMs / 1000);
    }
  });

  it('scales social narration around the pinned five-second outro like captions do', () => {
    assert.ok(social);
    const plans = planNarrationSegments(social, 32);
    const captions = buildCaptionsForDemo(social, 32);

    for (const plan of plans) {
      assert.equal(plan.scheduledStartSeconds, captions[plan.index].startMs / 1000);
    }
  });

  it('places on-schedule segments at their scheduled start times', () => {
    assert.ok(hero);
    const plans = planNarrationSegments(hero, 75);
    const durations = plans.map(
      (plan) => plan.scheduledEndSeconds - plan.scheduledStartSeconds - 1,
    );
    const placed = placeNarrationSegments(plans, durations, 75);

    for (const segment of placed) {
      assert.equal(segment.placedStartSeconds, segment.scheduledStartSeconds);
      assert.equal(segment.startDriftSeconds, 0);
    }
  });

  it('pushes a following segment later instead of overlapping a long line', () => {
    assert.ok(hero);
    const plans = planNarrationSegments(hero, 75).slice(0, 2);
    const overrun = plans[1].scheduledStartSeconds - plans[0].scheduledStartSeconds + 1;
    const placed = placeNarrationSegments(plans, [overrun, 2], 75);

    assert.equal(
      placed[1].placedStartSeconds,
      placed[0].placedEndSeconds + NARRATION_MIN_SEGMENT_GAP_SECONDS,
    );
    assert.ok(placed[1].placedStartSeconds > placed[1].scheduledStartSeconds);
  });

  it('fails closed when accumulated overrun drifts a line too far from its window', () => {
    assert.ok(hero);
    const plans = planNarrationSegments(hero, 75).slice(0, 2);
    const overrun = plans[1].scheduledStartSeconds
      - plans[0].scheduledStartSeconds
      + NARRATION_MAX_START_DRIFT_SECONDS
      + 1;

    assert.throws(
      () => placeNarrationSegments(plans, [overrun, 2], 75),
      /Shorten an earlier voiceover line/,
    );
  });

  it('fails closed when narration would run past the end of the video', () => {
    assert.ok(hero);
    const plans = planNarrationSegments(hero, 75);
    const durations = plans.map((plan, index) =>
      index === plans.length - 1
        ? 75 - plan.scheduledStartSeconds + 1
        : plan.scheduledEndSeconds - plan.scheduledStartSeconds - 1,
    );

    assert.throws(() => placeNarrationSegments(plans, durations, 75), /must end by/);
  });

  it('keeps the final line inside the closing margin when it just fits', () => {
    assert.ok(hero);
    const plans = planNarrationSegments(hero, 75);
    const durations = plans.map((plan, index) =>
      index === plans.length - 1
        ? 75 - NARRATION_END_MARGIN_SECONDS - plan.scheduledStartSeconds
        : plan.scheduledEndSeconds - plan.scheduledStartSeconds - 1,
    );
    const placed = placeNarrationSegments(plans, durations, 75);

    assert.ok(placed.at(-1)!.placedEndSeconds <= 75 - NARRATION_END_MARGIN_SECONDS + 1e-9);
  });

  it('rejects mismatched or invalid audio durations', () => {
    assert.ok(hero);
    const plans = planNarrationSegments(hero, 75);

    assert.throws(() => placeNarrationSegments(plans, [1], 75), /audio durations for/);
    assert.throws(
      () => placeNarrationSegments(plans, plans.map(() => 0), 75),
      /invalid audio duration/,
    );
  });
});
