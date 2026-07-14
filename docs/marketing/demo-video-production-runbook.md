# Demo Video Production Runbook

This runbook produces real, manually driven product stills and walkthroughs from the isolated Phase 1 showcase workspace. Automation may prepare data, audit routes, and validate completed artifacts; it must not navigate or interact with the browser for final capture, take a final screenshot, or record the browser footage.

## Source Of Truth

- Story and target duration: `app/data/demoVideos.ts`
- Capture surfaces and export requirements: `app/data/demoVideoProduction.ts`
- Canonical 17-scene route/session/interaction contract: `app/data/marketingCaptureScenes.json`
- Still-image scenes and per-image receipts: `app/data/marketingCaptureManifest.ts`
- Testbed seed and verification driver: `testbed/verify_marketing_capture_workspace.py`
- Manual still-image validator: `scripts/demo-videos/validate-manual-product-images.ts`
- Manual recording receipt validator: `scripts/demo-videos/validate-manual-demo-video.ts`
- Remotion entry point: `remotion/index.ts`

The hero is one connected 85-second planner-OS story. The browser recording is a human-driven 1440x900 full-window take. Remotion renders that take with `contain`, adds a separately recorded narration track, and owns the final five-second activation outro. Captions ship as a WebVTT sidecar through the website video player's native caption track, so they remain accessible without permanently covering product controls in the footage.

The website walkthrough is a 16:9 deliverable. Do not turn the same 85-second desktop take into a social video by squeezing it into 9:16. Phase 1 social videos need their own 20-35 second, pillar-native storyboards and manual capture receipts for Connection Over Tools, Disorganization Tax, Couple Experience + Boundaries, and Built for Planners.

Generated media and receipts are gitignored. A complete demo has:

- raw manual recording: `output/demo-videos/raw/{demoId}.mp4`
- narration master: `output/demo-videos/narration/{demoId}.m4a`
- manual receipt: `output/demo-videos/receipts/{demoId}.json`
- human playback approval: `output/demo-videos/playback-approvals/{demoId}.json`
- WebVTT captions: `public/demo-videos/captions/{demoId}.vtt`
- transcript: `public/demo-videos/transcripts/{demoId}.md`
- website export and thumbnail: `public/demo-videos/exports/{demoId}-16x9.mp4` and `public/demo-videos/thumbnails/{demoId}-16x9.png`

Do not set public manifest URLs until the final publication gate passes.

## 1. Start And Seed The Isolated Workspace

Use Node 22 for every frontend command. Stop any ad-hoc/default testbed session before binding the canonical capture ports. Build first, then start the tmux-backed stack with a production Next server on the dedicated capture origin. Reset, seed, and verify the fictional workspace only after those services are healthy:

```bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
hash -r
node --version
# Must be v22.x.

TESTBED_SESSION_NAME=marketing-capture \
.venv.nosync/bin/python testbed/testbed.py down
NODE_ENV=production npm run build

TESTBED_SESSION_NAME=marketing-capture \
TESTBED_FRONTEND_PORT=3100 \
TESTBED_FRONTEND_ORIGIN=http://127.0.0.1:3100 \
TESTBED_FRONTEND_CMD="npm run start -- --hostname 127.0.0.1" \
TESTBED_FRONTEND_NODE_ENV=production \
TESTBED_GOOGLE_MAPS_API_KEY="" \
TESTBED_UVICORN_ARGS="" \
.venv.nosync/bin/python testbed/testbed.py up --with-frontend

TESTBED_NON_INTERACTIVE=1 \
.venv.nosync/bin/python testbed/verify_marketing_capture_workspace.py \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://127.0.0.1:3100
```

The driver refuses non-local Mongo and any service origin other than the exact `http://127.0.0.1:8000` backend and `http://127.0.0.1:3100` frontend before it handles fixture credentials. Before reset or seed, it also inspects the canonical `marketing-capture` tmux process and fails unless the visible frontend is a real `next start` process running under Node 22; this proof does not depend on a later shell retaining `TESTBED_FRONTEND_NODE_ENV`. It removes only its owned seed namespace, reseeds the complete Phase 1 world, verifies planner/team/couple authentication, sends the planner cookie only to planner scenes and the couple cookie only to couple scenes, binds all 17 route shells to the clean served build, checks their exact seeded stable text through frontend-proxy data or served Next bundles, and verifies every gallery fixture as the exact reviewed 1600x1000 WebP bytes. These preflights support the manual review; they do not replace it.

Run the production inventory check as well:

```bash
npm run demo:requirements -- --demo planner-command-center-walkthrough
```

Before rehearsal, confirm all of the following:

```bash
git status --short
git rev-parse HEAD
TESTBED_SESSION_NAME=marketing-capture .venv.nosync/bin/python testbed/testbed.py status
curl -fsS http://127.0.0.1:3100/ >/dev/null
```

The worktree must be clean. `testbed.py status` must print `runtime=next-start node=node-22` for the frontend even though the status command does not repeat the startup-only `TESTBED_FRONTEND_NODE_ENV` export. The visible app's `meta[name="tsw-app-build-commit"]` must equal the full commit returned by `git rev-parse HEAD`. A development server, any non-Node-22 process, or a stale build marker invalidates the take.

## 2. Optional Automated Preflight Is Not Acceptance Evidence

The storage-state and route-audit tools may be used to catch setup defects before the manual pass:

```bash
DEMO_VIDEO_PLANNER_EMAIL=... \
DEMO_VIDEO_PLANNER_PASSWORD=... \
DEMO_VIDEO_COUPLE_EMAIL=... \
DEMO_VIDEO_COUPLE_PASSWORD=... \
npm run demo:auth-state -- --base-url http://127.0.0.1:3100
npm run demo:verify-routes -- \
  --base-url http://127.0.0.1:3100 \
  --demo planner-command-center-walkthrough
```

These tools are non-acceptance setup only. They may prove that routes resolve and seeded sessions work, but their headless browser state, navigation, and receipts do not prove the visible journey and must never be used as recorded footage. The production recording requires a fresh visible browser, a visible login, and human-driven interactions.

## 3. Prepare The Visible Browser

1. Open a clean Incognito window or a dedicated capture-only Chrome profile. Personal extensions, autofill prompts, password managers, and profile avatars must not appear.
2. Sign in visibly to the planner surface with the seeded planner identity.
3. Sign in visibly to the couple surface in a second tab with the seeded couple identity.
4. Open the public Sofia & Daniel microsite in a third tab. Prepare the three tabs in planner, public, couple order so the operator can switch them manually without exposing the address bar.
5. Verify the build marker in the visible app, then enter browser full-screen/presentation mode. Hide the address bar and browser chrome before recording so no local origin appears.
6. Keep the complete product viewport visible. Do not zoom the page, crop the app, or enlarge one card at the expense of the full window.
7. Close unrelated windows and notifications. Rehearse the clicks, tab switches, scroll distances, and readable pauses without recording. Do not create a navigation or interaction script.

### Manual still-image protocol

Every final product still is captured one at a time from the visible frontend in Google Chrome:

1. Keep browser zoom exactly 100%.
2. Open Chrome DevTools Device Toolbar and select `Responsive`, `1440x900`, and `DPR 1`.
3. Drive the frontend manually to the manifest route and required stable state. Wait for data, fonts, and images to finish loading, and confirm there is no framework overlay or console error.
4. Open the DevTools command palette and choose `Capture screenshot`, not `Capture full size screenshot`.
5. Inspect the original 1440x900 PNG at native resolution before approving or moving it to its manifest path.
6. Hash the untouched PNG and add that scene's explicit `source.reviewReceipt` to `marketingCaptureManifest.ts`. The receipt must name the scene, captured build, artifact checksum, visible Chrome settings, capture command, operator review time, and the fact that no scripted capture or post-capture transform was used. Never generate or copy one shared receipt across scenes.
7. After all 17 images have individual receipts, run `npm run demo:validate-images`. It validates every PNG and its full Git ancestry. `npm run build` performs the same published receipt/file/hash gate without requiring `.git`, so Gitless Docker builds remain deployable; CI separately runs the full-history published-ancestry gate. Until the final two captures are approved, build and CI also enforce the current floor of 15 reviewed proofs so an accidental status regression cannot silently replace published images with placeholders; moving forward from 15 to all 17 remains valid.

Changing a scene to `approved` without its own receipt is rejected. A receipt whose build or checksum differs from the scene and original PNG is also rejected. There is no crop, resize, stitching, scripted navigation, or scripted screenshot call in the final-still workflow. If the complete product shell is not legible inside the 1440x900 viewport, repair or restage the frontend and retake the still; do not zoom into a card or transform the PNG afterward.

The capture runtime deliberately leaves `TESTBED_GOOGLE_MAPS_API_KEY` blank. The public wedding page must therefore show its intentional Directions fallback without an embedded provider page, failed resource, or console error.

For the hero walkthrough, manually connect these exact checkpoints in one 85-second story:

| Time | Checkpoint | Human action and visible proof |
| --- | --- | --- |
| `0:00-0:10` | Planner command center | Pause on both active wedding cards, then click **Manage** for Sofia & Daniel. |
| `0:10-0:22` | Wedding event source | Open **Events** and point to the Traditional event, The Glasshouse at Riverbend, and `4:00 PM`. |
| `0:22-0:34` | Public event plan | Manually switch to the prepared public tab and show the same venue and time. |
| `0:34-0:46` | Couple timeline | Manually switch to the prepared couple tab, open **Timeline**, and show the same plan. |
| `0:46-0:58` | Guest response slice | Return to the planner tab, open **Guests**, and click the **Declined** summary/filter. |
| `0:58-1:08` | Seating plan | Use planner navigation to open **Seating**, then select Sofia & Daniel in the wedding picker. |
| `1:08-1:16` | Vendor contract context | Open **Vendors**, pause on overview totals, then open **Contracts**. |
| `1:16-1:20` | Return to command center | Use planner navigation to return to the two-wedding portfolio. |
| `1:20-1:25` | Activation outro | Hold on the command center. Remotion fades in: “One planner-owned workspace. Start with one wedding.” |

The recording is read-only. Budget has its own supporting clip; it is intentionally not crammed into the hero. The Phase 1 event-edit proof belongs in the dedicated timeline clip, where the edit and its cross-surface result can be reviewed deliberately.

Use natural cursor movement and readable pauses. Do not trigger a payment, SMS, email, legal signature, vendor send, or upload of private media.

## 4. Record With A Native Screen Recorder

Use the macOS Screenshot toolbar/QuickTime recorder or an FFmpeg AVFoundation screen device. The recorder captures pixels only; the operator drives every browser action manually.

To use FFmpeg, list local capture devices and identify the screen device:

```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

Start a native recording directly into the ignored canonical raw path, manually drive the browser, then press `q` in the recording terminal to stop:

```bash
mkdir -p output/demo-videos/raw
ffmpeg -y -f avfoundation \
  -framerate 30 \
  -capture_cursor 1 \
  -capture_mouse_clicks 0 \
  -i "SCREEN_DEVICE_INDEX:none" \
  -vf "scale=w=1440:h=900:force_original_aspect_ratio=decrease:flags=lanczos,pad=1440:900:(ow-iw)/2:(oh-ih)/2:0x071020,setsar=1,format=nv12" \
  -c:v h264_videotoolbox -b:v 12M -movflags +faststart -an \
  output/demo-videos/raw/planner-command-center-walkthrough.mp4
```

Re-list AVFoundation devices immediately before every take because the screen index can change. The source display does not have to be 16:10: the scale-plus-pad filter preserves its aspect ratio instead of stretching it to 1440x900. The small matte is preferable to distorted UI.

Do not crop into the application, digitally zoom, hide or replace the natural cursor, synthesize actions, or use a browser-driving recorder. If the full window is not legible, redo the visible browser layout and record again.

## 5. Review And Validate The Manual Receipt

Watch the complete raw footage at normal speed and review at least one still frame from every listed checkpoint. Reject the take if any frame shows a local address, developer overlay, loading/error shell, private identity, real contact information, token, payment data, or clipped product window.

Create `output/demo-videos/receipts/planner-command-center-walkthrough.json` after that review. Before recording, inspect `meta[name="tsw-app-build-commit"]` in the visible app and confirm that it equals the full 40-character current commit. Validation must run from a clean worktree, including no untracked application or configuration files:

```json
{
  "schemaVersion": 2,
  "demoId": "planner-command-center-walkthrough",
  "captureMethod": "manual-visible-browser",
  "recordedAt": "2026-07-12T18:00:00.000Z",
  "appBuildCommit": "REPLACE_WITH_GIT_COMMIT",
  "runtimeBuildIdentity": {
    "origin": "http://127.0.0.1:3100",
    "identitySelector": "meta[name=\"tsw-app-build-commit\"]",
    "observedCommit": "REPLACE_WITH_GIT_COMMIT",
    "verifiedAt": "2026-07-12T17:55:00.000Z"
  },
  "source": {
    "artifactPath": "output/demo-videos/raw/planner-command-center-walkthrough.mp4",
    "artifactSha256": "REPLACE_WITH_SHA256",
    "byteLength": 0,
    "width": 1440,
    "height": 900,
    "durationSeconds": 85,
    "captureBounds": { "x": 0, "y": 0, "width": 1440, "height": 900 }
  },
  "operatorAttestation": {
    "browserWasVisible": true,
    "interactionsWereManual": true,
    "scriptedBrowserCaptureWasUsed": false,
    "fullWindowWasVisible": true,
    "browserAddressBarWasHidden": true,
    "realCustomerDataWasExcluded": true,
    "sideEffectsWereTriggered": false
  },
  "checkpoints": [
    {
      "label": "Planner command center",
      "route": "/admin/planner",
      "action": "Scan both active wedding cards, then choose Manage for Sofia & Daniel.",
      "visibleResult": "Two active weddings show populated progress and Sofia & Daniel is the connected story to follow.",
      "atSeconds": 5,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Wedding event source",
      "route": "/admin/weddings/wedding_marketing_capture_sofia_daniel",
      "action": "Open Events and inspect the Traditional event venue and 4:00 PM start time.",
      "visibleResult": "The planner source record shows The Glasshouse at Riverbend and the 4:00 PM event time.",
      "atSeconds": 16,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Public event plan",
      "route": "/sofia-and-daniel",
      "action": "Manually switch to the prepared public tab and inspect the same event details.",
      "visibleResult": "The public schedule shows The Glasshouse at Riverbend and 4:00 PM without planner controls.",
      "atSeconds": 28,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Couple timeline",
      "route": "/couple/dashboard",
      "action": "Manually switch to the prepared couple tab, open Timeline, and inspect the same event.",
      "visibleResult": "The couple Timeline shows the same Glasshouse venue and 4:00 PM plan in its guided portal.",
      "atSeconds": 40,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Guest response slice",
      "route": "/admin/guests",
      "action": "Return to the planner tab, open Guests, and filter the seeded table to Declined.",
      "visibleResult": "The planner sees the declined guest slice alongside the same wedding guest operations context.",
      "atSeconds": 52,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Seating plan",
      "route": "/admin/seating",
      "action": "Use planner navigation to open Seating, then select Sofia & Daniel from the wedding picker.",
      "visibleResult": "The selected wedding reveals its seeded venue floor plan, tables, and existing guest assignments.",
      "atSeconds": 64,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Vendor contract context",
      "route": "/admin/vendors",
      "action": "Open Vendors, inspect the overview totals, then open Contracts without changing a record.",
      "visibleResult": "The planner vendor workspace shows populated totals and existing agreement amounts and statuses.",
      "atSeconds": 74,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Return to command center",
      "route": "/admin/planner",
      "action": "Return to the planner command center and pause on the connected portfolio.",
      "visibleResult": "The two active weddings and their next actions remain visible.",
      "atSeconds": 79,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    }
  ],
  "review": {
    "reviewedFrameCount": 8,
    "rawFrameReview": "approved",
    "publicSafetyReview": "approved"
  }
}
```

Use `git rev-parse HEAD`, `shasum -a 256`, `stat -f %z`, and `ffprobe` to populate the real commit, checksum, byte length, dimensions, and duration. For every reviewed checkpoint timestamp, extract the exact PNG bytes from the MP4 and hash those bytes (for example, `ffmpeg -v error -i RAW.mp4 -ss 5.000 -map 0:v:0 -frames:v 1 -f image2pipe -vcodec png pipe:1 | shasum -a 256`). Then run:

```bash
npm run demo:validate-manual-video -- \
  --receipt output/demo-videos/receipts/planner-command-center-walkthrough.json
```

The validator does not launch or control a browser. It rejects scripted-capture attestations, non-full-window bounds, placeholder, duplicate, out-of-plan, reordered, or altered checkpoints, extra or missing query parameters, a runtime marker that disagrees with the recorded clean commit, wrong raw paths, checksum/size mismatches, checkpoint timestamps that are not strictly increasing, reviewed-frame hashes that do not match frames extracted from the MP4, non-1440x900 footage, footage outside the 60-90 second hero window, insufficient frame review, and unapproved safety review. The recorded commit may later be an ancestor of a clean publication commit, so adding the approval manifest does not make the original receipt unverifiable; unrelated histories still fail closed.

## 6. Narration And Post-Production

Record narration separately from the screen. Do not capture the microphone or system audio in the raw browser take. Read the `voiceover` lines in `app/data/demoVideos.ts` exactly, with the final line landing in the five-second CTA. Reject narration with room noise, clipped words, synthetic route names, local-server language, or claims the footage does not prove.

Normalize the approved narration master into the canonical ignored path:

```bash
mkdir -p output/demo-videos/narration
ffmpeg -y -i /path/to/approved-narration-source.wav \
  -af "highpass=f=80,lowpass=f=16000,loudnorm=I=-16:TP=-1.5:LRA=11" \
  -c:a aac -b:a 192k \
  output/demo-videos/narration/planner-command-center-walkthrough.m4a
```

Only after the manual capture receipt and narration master exist, render the contained website format:

```bash
npm run demo:render -- \
  --demo planner-command-center-walkthrough \
  --format web-16x9 \
  --receipt output/demo-videos/receipts/planner-command-center-walkthrough.json
```

The renderer fails closed when narration is missing and probes the finished MP4 to ensure it contains an audio stream. It uses the exact raw recording duration, fills the 16:9 canvas height with the 16:10 product window, preserves the complete window with `contain`, overlays compact captions, and fades to the activation CTA for the final five seconds.

Do not run `--format social-9x16` for a desktop walkthrough. Social output must come from a separately defined, 20-35 second Phase 1 story with its own manual capture contract.

After watching the complete website export at normal speed and testing the website modal on desktop and mobile, create the canonical human playback approval receipt and validate it:

```json
{
  "schemaVersion": 1,
  "demoId": "planner-command-center-walkthrough",
  "reviewedAt": "REPLACE_WITH_EXACT_ISO_TIMESTAMP",
  "reviewer": "REPLACE_WITH_HUMAN_REVIEWER_NAME",
  "reviewMethod": "human-normal-speed-playback",
  "targets": [
    {
      "format": "web-16x9",
      "video": {
        "artifactPath": "public/demo-videos/exports/planner-command-center-walkthrough-16x9.mp4",
        "artifactSha256": "REPLACE_WITH_SHA256",
        "byteLength": 0,
        "width": 1920,
        "height": 1080,
        "durationSeconds": 85,
        "hasAudio": true
      },
      "thumbnail": {
        "artifactPath": "public/demo-videos/thumbnails/planner-command-center-walkthrough-16x9.png",
        "artifactSha256": "REPLACE_WITH_SHA256",
        "byteLength": 0,
        "width": 1920,
        "height": 1080
      },
      "review": {
        "fullNormalSpeedPlaybackCompleted": true,
        "captionsApproved": true,
        "narrationAndAudioApproved": true,
        "fullUncroppedProductWindowApproved": true,
        "localAndDevelopmentContentExcluded": true,
        "privateContentExcluded": true,
        "publicSafetyApproved": true
      }
    }
  ],
  "websitePlayback": {
    "desktopApproved": true,
    "mobileApproved": true
  }
}
```

Save it as `output/demo-videos/playback-approvals/planner-command-center-walkthrough.json`. Populate hashes, byte lengths, dimensions, and duration from the real artifacts; the validator re-probes and re-hashes both files.

```bash
npm run demo:validate-playback -- --demo planner-command-center-walkthrough
```

Then require every generated asset:

```bash
npm run demo:requirements -- \
  --demo planner-command-center-walkthrough \
  --require-assets
```

Rendering always revalidates the manual receipt; arbitrary raw-file and duration overrides are rejected. The validated raw recording and narration master stay outside the deployable `public/` tree and are copied into ignored Remotion staging paths only for the render. Both staging files are removed even when rendering fails. Captions may clarify the visible action, but must not hide the product or claim a result the recording does not show.

## 7. Publication Gate

Before changing a demo to `published` or attaching CDN URLs:

1. Watch the entire 16:9 export at normal speed with narration audible.
2. Confirm the connected story uses the approved fictional Phase 1 workspace.
3. Confirm the product window is complete and never cropped or digitally zoomed.
4. Confirm no local origin, developer UI, private data, tokens, or real contact/payment information is visible.
5. Confirm no real message, payment, signature, vendor action, or private upload occurred.
6. Confirm captions are accurate, readable, and inside safe areas.
7. Load the website demo modal in a visible desktop browser and a mobile viewport; prove playback, poster, controls, and fallback behavior.
8. Record the human playback approval separately from the raw-capture receipt and make `npm run demo:validate-playback` pass.

If any item fails, keep the public manifest in its retake-safe `recording` state.
