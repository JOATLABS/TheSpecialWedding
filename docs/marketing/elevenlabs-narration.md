# ElevenLabs Narration Pipeline

The robotic narration in the first published walkthrough batch was a source
problem, not a Remotion problem: the original masters were 22.05 kHz mono AAC
at ~30 kbps from an old-generation TTS engine, and Remotion faithfully rendered
that input into the exports. Remotion performs no speech synthesis — `<Audio>`
plays exactly the file it is given — so the fix is to regenerate the narration
masters with a modern neural voice and re-render. Nothing about the composition
(`remotion/DemoVideoComposition.tsx`), the render pipeline, or the deploy
workflow changes.

## Source of truth

- Voiceover lines and windows: `script[].voiceover` + `script[].timestamp` in
  `app/data/demoVideos.ts`. The generator reads the catalog, so a new demo
  (for example a storefront walkthrough) gets narration by adding its catalog
  entry — no new wiring.
- Narration timing: `scripts/demo-videos/narration-timeline.ts` reuses
  `buildCaptionsForDemo`, so the spoken line and its WebVTT caption cue always
  start together, including takes that run shorter or longer than the authored
  duration (the validated capture-receipt duration is preferred when present).
- Output contract: the same canonical master path the renderer already stages,
  `output/demo-videos/narration/{demoId}.m4a`, normalized with the runbook
  chain (`highpass=f=80,lowpass=f=16000,loudnorm=I=-16:TP=-1.5:LRA=11`) at
  44.1 kHz AAC 192k. A provenance manifest is written beside each master at
  `output/demo-videos/narration/{demoId}.narration.json` recording voice,
  model, settings, per-line placement, and content hashes; it also acts as the
  regeneration cache.

## Configuration

| Setting | Env var | Flag | Default |
| --- | --- | --- | --- |
| API key | `ELEVEN_LABS_API_KEY` (or `ELEVENLABS_API_KEY`) | — | required unless `--dry-run` |
| Voice | `ELEVENLABS_VOICE_ID` | `--voice-id` | `My4OXDyai4TWzZlKmUyw` (the founder’s cloned voice; premade US-female fallback: “Rachel”, `21m00Tcm4TlvDq8ikWAM`) |
| Model | `ELEVENLABS_MODEL_ID` | `--model` | `eleven_multilingual_v2` |
| Output format | `ELEVENLABS_OUTPUT_FORMAT` | `--output-format` | `mp3_44100_128` |
| Speaking speed | `ELEVENLABS_SPEED` | `--speed` | provider default (accepted range 0.7–1.2) |
| Delivery | — | `--stability`, `--similarity-boost`, `--style` | 0.5 / 0.75 / 0 |

- **Your cloned voice:** create the clone in ElevenLabs VoiceLab, copy its
  voice id, and set `ELEVENLABS_VOICE_ID` (locally or as a repository
  variable/workflow input). Nothing else changes. `GET
  https://api.elevenlabs.io/v1/voices` with the `xi-api-key` header lists the
  ids available to the account.
- `mp3_44100_128` is the best MP3 rate on the Starter plan; set
  `ELEVENLABS_OUTPUT_FORMAT=mp3_44100_192` once the account is on Creator or
  above. The intermediate segment format matters less than it looks — the
  master is normalized and re-encoded to 192k AAC either way, and the render
  encodes the final export track at Remotion's 320k AAC default.
- The GitHub Actions repository secret is named `ELEVEN_LABS_API_KEY` and is
  already configured; the generator accepts both spellings.

## Generating narration

```bash
# See what would be spoken (no API calls, no key needed)
npm run demo:narrate -- --all-published --dry-run

# Regenerate every published demo's master (skips demos whose script, voice,
# and settings are unchanged since the last run)
ELEVEN_LABS_API_KEY=... npm run demo:narrate -- --all-published

# One demo, with a cloned voice
ELEVEN_LABS_API_KEY=... npm run demo:narrate -- \
  --demo morning-view-demo \
  --voice-id YOUR_CLONED_VOICE_ID
```

Each script line is synthesized as its own request with `previous_text` /
`next_text` continuity context, placed at its caption-aligned start time, and
mixed into one master. Placement is sequential — a long line pushes the next
line later instead of speaking over it — and fails closed when a line would
drift more than 2.5 s from its window or run past the end of the video, with
the fix being a shorter voiceover line or a higher `--speed`.

`ffmpeg`/`ffprobe` must be on `PATH` (they already are in CI and in the
capture-host runbook environment).

## Shipping the regenerated audio

The publication gates are unchanged and intentionally fail closed:

1. `npm run demo:narrate -- --all-published`
2. `npm run demo:render -- --demo <id>` for each affected demo (revalidates the
   manual capture receipt; raw takes and receipts are untouched by a narration
   refresh).
3. Watch every re-rendered export at normal speed with narration audible
   (desktop + mobile for website demos, portrait presentation for social).
4. Refresh the playback approvals you actually reviewed:
   `npm run demo:approve-playback -- --all-published --reviewer "Your Name"
   --attest-all` (or per-demo with `--demo`; the helper refuses to run without
   the reviewer name and explicit attestation flags, and re-runs the canonical
   validator on the result).
5. Commit narration masters + manifests, exports, thumbnails, and refreshed
   approvals together (`git add -f` for the `output/` evidence, per the
   runbook), then let CI's published-video gates verify the tree before merge.
   Staging deploys automatically after CI on `main`.

The `Generate Narration (ElevenLabs)` workflow (`.github/workflows/
generate-narration.yml`) automates steps 1–2 on a dispatch and opens a draft PR
with the regenerated artifacts; steps 3–5 stay human on purpose, and the
reviewer's approval push is what turns CI green on that PR.

## Adding narration for a brand-new demo (e.g. the storefront walkthrough)

1. Add the demo to `app/data/demoVideos.ts` with its `script` (timestamps +
   voiceover lines).
2. `npm run demo:narrate -- --demo <new-id>` — before the raw take exists the
   generator uses the authored duration, so the operator can rehearse against
   the real voice track.
3. Record the manual raw take per the runbook, create the capture receipt,
   then re-run `demo:narrate` (it re-aligns to the validated take duration
   when it differs) and continue with render → review → approval → allowlist.
