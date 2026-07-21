export type NarrationWindow = {
  startSeconds: number;
  endSeconds: number;
};

export const MUSIC_BED_BASE_VOLUME = 0.3;
export const MUSIC_BED_DUCKED_VOLUME = 0.11;
export const MUSIC_DUCK_RAMP_SECONDS = 0.35;
// Ducking opens slightly before a line begins and releases slightly after it
// ends so speech onsets are never clipped by the ramp.
export const MUSIC_DUCK_LEAD_SECONDS = 0.15;

/**
 * Music volume at a given time: the bed sits at its base level and ducks
 * smoothly while any narration window is active. Windows come from the
 * narration provenance manifest, so the ducking follows the actually
 * synthesized speech rather than the authored timestamps.
 */
export function musicVolumeAtSeconds(
  seconds: number,
  windows: readonly NarrationWindow[],
): number {
  let duckAmount = 0;

  for (const window of windows) {
    const start = window.startSeconds - MUSIC_DUCK_LEAD_SECONDS;
    const end = window.endSeconds + MUSIC_DUCK_LEAD_SECONDS;
    if (!(Number.isFinite(start) && Number.isFinite(end)) || end <= start) continue;

    let amount = 0;
    if (seconds >= start && seconds <= end) {
      amount = 1;
    } else if (seconds < start && start - seconds < MUSIC_DUCK_RAMP_SECONDS) {
      amount = 1 - (start - seconds) / MUSIC_DUCK_RAMP_SECONDS;
    } else if (seconds > end && seconds - end < MUSIC_DUCK_RAMP_SECONDS) {
      amount = 1 - (seconds - end) / MUSIC_DUCK_RAMP_SECONDS;
    }

    duckAmount = Math.max(duckAmount, amount);
  }

  if (duckAmount >= 1) return MUSIC_BED_DUCKED_VOLUME;
  if (duckAmount <= 0) return MUSIC_BED_BASE_VOLUME;
  return MUSIC_BED_BASE_VOLUME - (MUSIC_BED_BASE_VOLUME - MUSIC_BED_DUCKED_VOLUME) * duckAmount;
}
