import type { DemoVideo } from '../../app/data/demoVideos';
import { buildCaptionsForDemo } from './captions';

export type NarrationSegmentPlan = {
  index: number;
  text: string;
  scheduledStartSeconds: number;
  scheduledEndSeconds: number;
};

export type PlacedNarrationSegment = NarrationSegmentPlan & {
  placedStartSeconds: number;
  audioDurationSeconds: number;
  placedEndSeconds: number;
  startDriftSeconds: number;
};

// Segments are laid out sequentially: a line that runs long pushes the next
// line later instead of speaking over it, but only within these bounds so the
// voice can never detach from the on-screen action it describes.
export const NARRATION_MIN_SEGMENT_GAP_SECONDS = 0.15;
export const NARRATION_MAX_START_DRIFT_SECONDS = 2.5;
export const NARRATION_END_MARGIN_SECONDS = 0.25;

/**
 * Narration timing reuses the caption timeline so the spoken line and its
 * WebVTT cue always start together, including the caption scaler's handling
 * of takes that run shorter or longer than the authored duration.
 */
export function planNarrationSegments(
  demo: DemoVideo,
  durationSeconds: number,
): NarrationSegmentPlan[] {
  return buildCaptionsForDemo(demo, durationSeconds).map((caption, index) => ({
    index,
    text: caption.text,
    scheduledStartSeconds: caption.startMs / 1000,
    scheduledEndSeconds: caption.endMs / 1000,
  }));
}

export function placeNarrationSegments(
  plans: readonly NarrationSegmentPlan[],
  audioDurationsSeconds: readonly number[],
  videoDurationSeconds: number,
): PlacedNarrationSegment[] {
  if (plans.length !== audioDurationsSeconds.length) {
    throw new Error(
      `Narration placement received ${audioDurationsSeconds.length} audio durations for ${plans.length} segments.`,
    );
  }

  const placed: PlacedNarrationSegment[] = [];
  let previousEnd = 0;

  for (const plan of plans) {
    const audioDurationSeconds = audioDurationsSeconds[plan.index];
    if (!Number.isFinite(audioDurationSeconds) || audioDurationSeconds <= 0) {
      throw new Error(
        `Narration segment ${plan.index} has an invalid audio duration (${audioDurationSeconds}).`,
      );
    }

    const earliestStart = placed.length === 0
      ? plan.scheduledStartSeconds
      : previousEnd + NARRATION_MIN_SEGMENT_GAP_SECONDS;
    const placedStartSeconds = Math.max(plan.scheduledStartSeconds, earliestStart);
    const startDriftSeconds = placedStartSeconds - plan.scheduledStartSeconds;

    if (startDriftSeconds > NARRATION_MAX_START_DRIFT_SECONDS) {
      throw new Error(
        `Narration segment ${plan.index} ("${plan.text.slice(0, 60)}…") would start `
          + `${startDriftSeconds.toFixed(2)}s after its ${plan.scheduledStartSeconds.toFixed(2)}s window `
          + `because earlier lines run long. Shorten an earlier voiceover line or raise the speaking speed.`,
      );
    }

    const placedEndSeconds = placedStartSeconds + audioDurationSeconds;
    placed.push({
      ...plan,
      placedStartSeconds,
      audioDurationSeconds,
      placedEndSeconds,
      startDriftSeconds,
    });
    previousEnd = placedEndSeconds;
  }

  const lastEnd = placed.at(-1)?.placedEndSeconds ?? 0;
  const latestAllowedEnd = videoDurationSeconds - NARRATION_END_MARGIN_SECONDS;
  if (lastEnd > latestAllowedEnd) {
    throw new Error(
      `Narration runs to ${lastEnd.toFixed(2)}s but must end by ${latestAllowedEnd.toFixed(2)}s `
        + `inside the ${videoDurationSeconds.toFixed(2)}s video. Shorten the final voiceover lines or `
        + `raise the speaking speed.`,
    );
  }

  return placed;
}
