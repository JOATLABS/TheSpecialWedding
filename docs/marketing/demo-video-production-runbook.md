# Demo Video Production Runbook

This runbook produces a real, manually driven product walkthrough from the isolated Phase 1 showcase workspace. Automation may prepare data and audit routes; it must not navigate, interact with, or record the browser footage.

## Source Of Truth

- Story and target duration: `app/data/demoVideos.ts`
- Capture surfaces and export requirements: `app/data/demoVideoProduction.ts`
- Testbed seed and verification driver: `testbed/verify_marketing_capture_workspace.py`
- Manual recording receipt validator: `scripts/demo-videos/validate-manual-demo-video.ts`
- Remotion entry point: `remotion/index.ts`

The hero is a connected 90-second planner-OS story. The foreground recording is always rendered with `contain`, so the full product window stays visible in both the website and social compositions.

Generated media and receipts are gitignored. A complete demo has:

- raw manual recording: `output/demo-videos/raw/{demoId}.mp4`
- manual receipt: `output/demo-videos/receipts/{demoId}.json`
- captions: `public/demo-videos/captions/{demoId}.json`
- transcript: `public/demo-videos/transcripts/{demoId}.md`
- website export and thumbnail: `public/demo-videos/exports/{demoId}-16x9.mp4` and `public/demo-videos/thumbnails/{demoId}-16x9.png`
- social export and thumbnail: `public/demo-videos/exports/{demoId}-9x16.mp4` and `public/demo-videos/thumbnails/{demoId}-9x16.png`

Do not set public manifest URLs until the final publication gate passes.

## 1. Start And Seed The Isolated Workspace

Use Node 22 for frontend commands. Build first, then start the tmux-backed stack with a production Next server on the dedicated capture origin. Reset, seed, and verify the fictional workspace only after those services are healthy:

```bash
npm run build
TESTBED_SESSION_NAME=marketing-capture \
TESTBED_FRONTEND_PORT=3100 \
TESTBED_FRONTEND_CMD="npm run start -- --hostname 127.0.0.1" \
TESTBED_UVICORN_ARGS="" \
.venv.nosync/bin/python testbed/testbed.py up --with-frontend

TESTBED_NON_INTERACTIVE=1 \
.venv.nosync/bin/python testbed/verify_marketing_capture_workspace.py \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://127.0.0.1:3100
```

The driver refuses non-local Mongo, removes only its owned seed namespace, reseeds the complete Phase 1 world, checks collection ownership and counts, verifies planner/team/couple authentication, and confirms the public wedding route.

Run the production inventory check as well:

```bash
npm run demo:requirements -- --demo planner-command-center-walkthrough
```

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

1. Open a new visible browser window at the local frontend.
2. Sign in visibly with the dedicated seeded planner or couple identity.
3. Hide the address bar and browser chrome before recording so no local origin appears.
4. Use an exact 1440x900 recording window and keep the entire product viewport visible.
5. Close unrelated windows, notifications, password prompts, developer tools, and personal browser profiles.
6. Rehearse the route changes and waits without recording. Do not rehearse by creating an automated navigation script.

For the hero walkthrough, manually connect these checkpoints in one 60-90 second story:

1. planner command center and two active weddings
2. Sofia & Daniel's seeded wedding source record
3. public view of the same seeded plan
4. couple portal view of the same seeded plan
5. populated guest operations
6. populated seating plan
7. vendor and contract/payment context
8. budget and recorded-payment context
9. return to the planner command center

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
ffmpeg -f avfoundation -framerate 30 -capture_cursor 0 -i "SCREEN_DEVICE_INDEX:none" \
  -vf "scale=1440:900:flags=lanczos,format=nv12" \
  -c:v h264_videotoolbox -b:v 12M -movflags +faststart -an \
  output/demo-videos/raw/planner-command-center-walkthrough.mp4
```

Do not crop into the application, digitally zoom, replace the cursor, synthesize actions, or use a browser-driving recorder. If the full window is not legible, redo the visible browser layout and record again.

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
    "durationSeconds": 90,
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
      "action": "Scan both active wedding cards and their next actions.",
      "visibleResult": "Two active weddings show populated setup, RSVP, vendor, budget, and next-action signals.",
      "atSeconds": 5,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Wedding source record",
      "route": "/admin/weddings/wedding_marketing_capture_sofia_daniel",
      "action": "Open Sofia & Daniel's wedding source record and inspect its schedule and story state.",
      "visibleResult": "The seeded schedule and story state are populated for Sofia & Daniel.",
      "atSeconds": 15,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Public wedding plan",
      "route": "/sofia-and-daniel",
      "action": "Open the public microsite for the same wedding.",
      "visibleResult": "The public schedule and story match the seeded wedding without planner-only controls.",
      "atSeconds": 25,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Couple portal plan",
      "route": "/couple/dashboard",
      "action": "Open Sofia & Daniel's couple portal and inspect the shared wedding plan.",
      "visibleResult": "The couple portal shows the same seeded wedding context without planner-only operations.",
      "atSeconds": 35,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Guest operations",
      "route": "/admin/guests",
      "action": "Inspect the populated guest list, RSVP, meal, household, and plus-one state.",
      "visibleResult": "Seeded guests show varied RSVP, meal, household, and plus-one data.",
      "atSeconds": 45,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Seating plan",
      "route": "/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel",
      "action": "Open Sofia & Daniel's seating plan and inspect assigned guests.",
      "visibleResult": "The seeded floor plan shows populated tables and guest assignments.",
      "atSeconds": 55,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Vendor operations",
      "route": "/admin/vendors",
      "action": "Inspect assigned vendors and their operational status.",
      "visibleResult": "Seeded vendor assignments and contract/payment context are visible.",
      "atSeconds": 65,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Budget checkpoint",
      "route": "/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel",
      "action": "Inspect category totals, recorded payments, and budget status.",
      "visibleResult": "Seeded budget categories, actual payments, and totals are populated.",
      "atSeconds": 75,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Return to command center",
      "route": "/admin/planner",
      "action": "Return to the planner command center and pause on the connected portfolio.",
      "visibleResult": "The two active weddings and their next actions remain visible.",
      "atSeconds": 85,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    }
  ],
  "review": {
    "reviewedFrameCount": 9,
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

The validator does not launch or control a browser. It rejects scripted-capture attestations, non-full-window bounds, placeholder, duplicate, out-of-plan, reordered, or altered checkpoints, extra or missing query parameters, a runtime marker that disagrees with the exact clean commit, wrong raw paths, checksum/size mismatches, checkpoint timestamps that are not strictly increasing, reviewed-frame hashes that do not match frames extracted from the MP4, non-1440x900 footage, footage outside the 60-90 second hero window, insufficient frame review, and unapproved safety review.

## 6. Post-Production

Only after the manual receipt passes, render both contained formats:

```bash
npm run demo:render -- \
  --demo planner-command-center-walkthrough \
  --format web-16x9 \
  --receipt output/demo-videos/receipts/planner-command-center-walkthrough.json

npm run demo:render -- \
  --demo planner-command-center-walkthrough \
  --format social-9x16 \
  --receipt output/demo-videos/receipts/planner-command-center-walkthrough.json
```

Then require every generated asset:

```bash
npm run demo:requirements -- \
  --demo planner-command-center-walkthrough \
  --require-assets
```

Rendering always revalidates the manual receipt and uses the probed recording duration; arbitrary raw-file and duration overrides are rejected. The validated raw recording stays outside the deployable `public/` tree and is copied into an ignored Remotion staging path only for the duration of each render. Captions may clarify the visible action, but must not hide the product or claim a result the recording does not show. The social composition keeps the entire product window in a contained foreground panel; its blurred background is decorative only.

## 7. Publication Gate

Before changing a demo to `published` or attaching CDN URLs:

1. Watch the entire 16:9 export and the entire 9:16 export at normal speed.
2. Confirm the connected story uses the approved fictional Phase 1 workspace.
3. Confirm the product window is complete and never cropped or digitally zoomed.
4. Confirm no local origin, developer UI, private data, tokens, or real contact/payment information is visible.
5. Confirm no real message, payment, signature, vendor action, or private upload occurred.
6. Confirm captions are accurate, readable, and inside safe areas.
7. Load the website demo modal in a visible desktop browser and a mobile viewport; prove playback, poster, controls, and fallback behavior.
8. Record the human playback approval separately from the raw-capture receipt.

If any item fails, keep the public manifest in its retake-safe `recording` state.
