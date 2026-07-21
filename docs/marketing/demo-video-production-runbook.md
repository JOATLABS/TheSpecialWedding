# Demo Video Production Runbook

This runbook produces real, manually driven product stills and walkthroughs from the isolated Phase 1 showcase workspace. Automation may prepare data, audit routes, and validate completed artifacts; it must not navigate or interact with the browser for final capture, take a final screenshot, or record the browser footage.

## Source Of Truth

- Story and target duration: `app/data/demoVideos.ts`
- Website-only public playlist: `DEMO_VIDEO_PLAYLIST` in `app/data/demoVideos.ts`
- Four independent Phase 1 social stories: `PHASE_ONE_SOCIAL_VIDEO_STORIES` in
  `app/data/demoVideos.ts`
- Combined website-plus-social production inventory:
  `DEMO_VIDEO_PRODUCTION_CATALOG` in `app/data/demoVideos.ts`
- Capture surfaces and export requirements: `app/data/demoVideoProduction.ts`
- Canonical 17-scene route/session/interaction contract: `app/data/marketingCaptureScenes.json`
- Still-image scenes and per-image receipts: `app/data/marketingCaptureManifest.ts`
- Testbed seed and verification driver: `testbed/verify_marketing_capture_workspace.py`
- Manual still-image validator: `scripts/demo-videos/validate-manual-product-images.ts`
- Manual recording receipt validator: `scripts/demo-videos/validate-manual-demo-video.ts`
- Channel-specific human playback validator:
  `scripts/demo-videos/validate-demo-video-playback-approval.ts`
- Remotion entry point: `remotion/index.ts`

The hero is one connected 75-second planner-OS story. The browser recording is a human-driven 1440x900 full-window take. Remotion renders that take with `contain`, adds a separately recorded narration track, and owns the final five-second activation outro. Captions ship as a WebVTT sidecar through the website video player's native caption track, so they remain accessible without permanently covering product controls in the footage.

The website walkthrough is a 16:9 deliverable. Do not turn the same 75-second desktop take into a social video by squeezing it into 9:16. Phase 1 social videos have their own 20-35 second, pillar-native storyboards, manually driven raw takes, narration masters, capture receipts, portrait renders, and playback approvals:

| Social demo ID | Pillar | Product action before the five-second outro | Authored total | Ordered visible proof |
| --- | --- | ---: | ---: | --- |
| `connection-over-tools-social` | Connection Over Tools | 25 seconds | 30 seconds | Planner event source -> public schedule -> couple Timeline |
| `disorganization-tax-social` | Disorganization Tax | 20 seconds | 25 seconds | Morning View -> planner inbox -> wedding budget |
| `couple-experience-boundaries-social` | Couple Experience + Boundaries | 15 seconds | 20 seconds | Planner-owned intake -> couple form -> couple Payments |
| `built-for-planners-social` | Built for Planners | 30 seconds | 35 seconds | Guest context -> venue-aware seating -> private planner vendor records |

The raw source for every row remains a distinct human-driven 1440x900 full-window browser recording. The operator records the full authored duration and leaves a clean final five-second hold for Remotion's activation outro. `social-9x16` describes the 1080x1920 rendered canvas, not permission to crop or zoom the source application. The portrait composition contains the complete 16:10 product window and uses the remaining canvas for the pillar, title, outcome, and activation story.

Generated media and receipts are gitignored. Every complete demo has these common, ID-scoped artifacts:

- raw manual recording: `output/demo-videos/raw/{demoId}.mp4`
- narration master: `output/demo-videos/narration/{demoId}.m4a`
- narration provenance manifest (generated narration only): `output/demo-videos/narration/{demoId}.narration.json`
- manual receipt: `output/demo-videos/receipts/{demoId}.json`
- human playback approval: `output/demo-videos/playback-approvals/{demoId}.json`
- WebVTT captions: `public/demo-videos/captions/{demoId}.vtt`
- transcript: `public/demo-videos/transcripts/{demoId}.md`

A website demo has only its channel-native export and thumbnail: `public/demo-videos/exports/{demoId}-16x9.mp4` and `public/demo-videos/thumbnails/{demoId}-16x9.png` at 1920x1080. A social demo instead has only `public/demo-videos/exports/{demoId}-9x16.mp4` and `public/demo-videos/thumbnails/{demoId}-9x16.png` at 1080x1920.

The demo ID separates the artifacts; do not invent a parallel `social/` path subtree. Do not set public manifest URLs until the final publication gate passes. Website publications are allowlisted in `APPROVED_PUBLIC_DEMO_VIDEO_PUBLICATIONS`; the four social publications are allowlisted separately in `APPROVED_PHASE_ONE_SOCIAL_VIDEO_PUBLICATIONS`.

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

The driver refuses non-local Mongo and any service origin other than the exact `http://127.0.0.1:8000` backend and `http://127.0.0.1:3100` frontend before it handles fixture credentials. Before reset or seed, it also inspects the canonical `marketing-capture` tmux process and fails unless the visible frontend is a real `next start` process running under Node 22; this proof does not depend on a later shell retaining `TESTBED_FRONTEND_NODE_ENV`. It refreshes the canonical public subscription plans against local Mongo with Stripe explicitly disabled, verifies their exact visible catalog and `no-store` response through the frontend proxy, removes only its owned capture namespace, reseeds the complete Phase 1 world, verifies planner/team/couple authentication, sends the planner cookie only to planner scenes and the couple cookie only to couple scenes, binds all 17 route shells to the clean served build, checks their exact seeded stable text through frontend-proxy data or served Next bundles, and verifies every gallery fixture as the exact reviewed 1600x1000 WebP bytes. These preflights support the manual review; they do not replace it.

Run the production inventory check as well:

```bash
npm run demo:requirements -- --demo planner-command-center-walkthrough
npm run demo:requirements -- --demo connection-over-tools-social
npm run demo:requirements -- --demo disorganization-tax-social
npm run demo:requirements -- --demo couple-experience-boundaries-social
npm run demo:requirements -- --demo built-for-planners-social
```

The website command must report only `web-16x9`; every social command must report only `social-9x16`. Running `npm run demo:requirements` without `--demo` checks the complete `DEMO_VIDEO_PRODUCTION_CATALOG`. It does not require media until `--require-assets` is supplied.

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

npm run demo:verify-routes -- \
  --base-url http://127.0.0.1:3100 \
  --demo connection-over-tools-social \
  --demo disorganization-tax-social \
  --demo couple-experience-boundaries-social \
  --demo built-for-planners-social
```

`demo:auth-state` writes three isolated states: `output/demo-videos/state/demo-planner.json`, `output/demo-videos/state/demo-couple.json`, and `output/demo-videos/state/demo-public.json`. Planner and couple credentials are never combined into one context, and the public state contains no authenticated session. The route verifier chooses the state from the route family, accepts repeated `--demo` values, and resolves them through the combined production catalog without adding social stories to the website playlist. It fails on any same-origin HTTP response at or above 400, failed request, console error, page error, unexpected final route, blank shell, or known error page.

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
7. After all 17 images have individual receipts, run `npm run demo:validate-images`. It validates every PNG and its full Git ancestry. `npm run build` performs the same published receipt/file/hash gate without requiring `.git`, so Gitless Docker builds remain deployable; CI separately runs the full-history published-ancestry gate. Build and CI require all 17 reviewed proofs, so any scene regressing to a placeholder fails publication.

Changing a scene to `approved` without its own receipt is rejected. A receipt whose build or checksum differs from the scene and original PNG is also rejected. There is no crop, resize, stitching, scripted navigation, or scripted screenshot call in the final-still workflow. If the complete product shell is not legible inside the 1440x900 viewport, repair or restage the frontend and retake the still; do not zoom into a card or transform the PNG afterward.

The capture runtime deliberately leaves `TESTBED_GOOGLE_MAPS_API_KEY` blank. The public wedding page must therefore show its intentional Directions fallback without an embedded provider page, failed resource, or console error.

For the hero walkthrough, manually connect these exact checkpoints in one 75-second story:

| Time | Checkpoint | Human action and visible proof |
| --- | --- | --- |
| `0:00-0:10` | Planner command center | Pause on both active wedding cards, then click **Manage** for Sofia & Daniel. |
| `0:10-0:25` | Wedding event source | Open **Events** and point to the Traditional event, The Glasshouse at Riverbend, and `4:00 PM`. |
| `0:25-0:40` | Public event plan | Manually switch to the prepared public tab and show the same venue and time. |
| `0:40-0:55` | Couple timeline | Manually switch to the prepared couple tab, open **Timeline**, and show the same plan. |
| `0:55-1:05` | Guest response context | Return to the planner tab, open **Guests**, and click the **Declined** summary/filter. |
| `1:05-1:15` | Return and activation outro | Use the first five seconds to return to the command center, then hold for Remotion's five-second fade: “One planner-owned workspace. Start with one wedding.” |

The recording is read-only. Seating, vendors, contracts, and budget have their own supporting clips; they are intentionally not crammed into the hero. The hero shows one source, two audience-specific views, and one guest-response state in planner operations without pretending the recording created that response. The Phase 1 event-edit proof belongs in the dedicated timeline clip, where the edit and its cross-surface result can be reviewed deliberately.

For the supporting Phase 1 clips:

- Morning View shows only the RSVP, recent-activity, pending-form, and setup signals that are visibly present. Keep the full product window; never plan a later crop.
- Couple Portal is a read-only review and self-service story; do not claim a response was submitted unless a separate reversible action contract proves it.
- Planner Record → Public Microsite is a parity story. Comparing preseeded surfaces does not prove an edit, automatic publish event, or live propagation.
- Guest Management shows the summary and a Declined table filter, then clears that filter before switching to Card View and inspecting the collapsed Priya Shah card. That exact seeded card visibly shows Confirmed, Friends, Vegetarian, and one submitted plus-one. Never open **Details**, **Edit**, or **QR** during capture because those controls can expose token-bearing or mutable guest state.
- Seating uses the in-product canvas Zoom out control twice to reach a visible `70%` readout while browser page zoom remains `100%`.
- Vendor Directory & CRM starts on a prepared public-directory tab and manually switches to a separately prepared authenticated planner tab with the address bar already hidden. Never open or promote the unfinished vendor portal.

### Manual social-video protocol

1. Select exactly one of the four social IDs. Prepare only that story's required planner, couple, and public tabs and rehearse its exact ordered checkpoints from `app/data/demoVideos.ts`.
2. Record a new native 1440x900 full-window take into `output/demo-videos/raw/{socialDemoId}.mp4`. Never copy, crop, resize, or reframe the website walkthrough as its source.
3. Keep browser zoom at 100%, the address bar hidden, the complete product shell visible, and every interaction human-driven. Portrait framing is added later; it is not created by zooming the browser.
4. Complete the product actions before the final five seconds, then hold a clean, publicly safe frame while Remotion's activation outro will cover the final five seconds.
5. Review and hash at least one exact frame for every ordered checkpoint. Each social ID receives its own schema-version-2 manual capture receipt.

The manual recording validator accepts only a five-second tolerance on either side of each website authored duration. A 60-second website feature take therefore must run 55–65 seconds; the old 75-percent shortcut is not accepted. Social tolerance is also five seconds but is hard-clamped to the approved 20–35 second range:

| Social demo ID | Accepted raw duration |
| --- | ---: |
| `connection-over-tools-social` | 25–35 seconds |
| `disorganization-tax-social` | 20–30 seconds |
| `couple-experience-boundaries-social` | 20–25 seconds |
| `built-for-planners-social` | 30–35 seconds |

These are fail-closed technical bounds, not permission to truncate the storyboard. The operator targets the authored total and the human review still requires every product action plus the clean five-second outro hold; a take missing either is rejected even if its file duration falls inside the validator tolerance.

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

For a social take, record directly to that story's canonical raw path with the same full-window filter. For example:

```bash
SOCIAL_DEMO_ID=connection-over-tools-social
mkdir -p output/demo-videos/raw
ffmpeg -y -f avfoundation \
  -framerate 30 \
  -capture_cursor 1 \
  -capture_mouse_clicks 0 \
  -i "SCREEN_DEVICE_INDEX:none" \
  -vf "scale=w=1440:h=900:force_original_aspect_ratio=decrease:flags=lanczos,pad=1440:900:(ow-iw)/2:(oh-ih)/2:0x071020,setsar=1,format=nv12" \
  -c:v h264_videotoolbox -b:v 12M -movflags +faststart -an \
  "output/demo-videos/raw/${SOCIAL_DEMO_ID}.mp4"
```

Repeat that native recording with a fresh manually driven take for each remaining social ID. Changing only the filename while reusing footage is not an acceptable capture.

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
    "durationSeconds": 75,
    "captureBounds": { "x": 0, "y": 0, "width": 1440, "height": 900 }
  },
  "operatorAttestation": {
    "browserWasVisible": true,
    "interactionsWereManual": true,
    "scriptedBrowserCaptureWasUsed": false,
    "dedicatedChannelTake": true,
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
      "atSeconds": 18,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Public event plan",
      "route": "/sofia-and-daniel",
      "action": "Manually switch to the prepared public tab and inspect the same event details.",
      "visibleResult": "The public schedule shows The Glasshouse at Riverbend and 4:00 PM without planner controls.",
      "atSeconds": 32,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Couple timeline",
      "route": "/couple/dashboard",
      "action": "Manually switch to the prepared couple tab, open Timeline, and inspect the same event.",
      "visibleResult": "The couple Timeline shows the same Glasshouse venue and 4:00 PM plan in its guided portal.",
      "atSeconds": 47,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Guest response context",
      "route": "/admin/guests",
      "action": "Return to the planner tab, open Guests, and filter the seeded table to Declined.",
      "visibleResult": "The planner sees the Declined slice as operational context for the same wedding.",
      "atSeconds": 60,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Return to command center",
      "route": "/admin/planner",
      "action": "Return to the planner command center and pause on the connected portfolio.",
      "visibleResult": "The two active weddings and their next actions remain visible.",
      "atSeconds": 70,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    }
  ],
  "review": {
    "reviewedFrameCount": 6,
    "rawFrameReview": "approved",
    "publicSafetyReview": "approved"
  }
}
```

### Social manual capture receipt

Social raw footage uses the same schema-version-2 manual receipt contract. The validator derives the channel from the social demo ID; do not add a `productionChannel` field or create a separate schema. Use the exact story ID, raw path, ordered catalog checkpoints, 1440x900 source dimensions, and full-window capture bounds. For `connection-over-tools-social`, the receipt shape is:

```json
{
  "schemaVersion": 2,
  "demoId": "connection-over-tools-social",
  "captureMethod": "manual-visible-browser",
  "recordedAt": "2026-07-14T18:00:00.000Z",
  "appBuildCommit": "REPLACE_WITH_GIT_COMMIT",
  "runtimeBuildIdentity": {
    "origin": "http://127.0.0.1:3100",
    "identitySelector": "meta[name=\"tsw-app-build-commit\"]",
    "observedCommit": "REPLACE_WITH_GIT_COMMIT",
    "verifiedAt": "2026-07-14T17:55:00.000Z"
  },
  "source": {
    "artifactPath": "output/demo-videos/raw/connection-over-tools-social.mp4",
    "artifactSha256": "REPLACE_WITH_SHA256",
    "byteLength": 0,
    "width": 1440,
    "height": 900,
    "durationSeconds": 30,
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
      "label": "Connection planner source",
      "route": "/admin/weddings/wedding_marketing_capture_sofia_daniel",
      "action": "Open Events and hold on The Glasshouse at Riverbend at 4:00 PM.",
      "visibleResult": "The planner-owned event record shows The Glasshouse at Riverbend and the 4:00 PM start.",
      "atSeconds": 5,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Connection guest view",
      "route": "/sofia-and-daniel",
      "action": "Switch manually to the public schedule and hold on the same venue and time.",
      "visibleResult": "The public wedding schedule shows the Glasshouse venue and 4:00 PM without planner controls.",
      "atSeconds": 14,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    },
    {
      "label": "Connection couple view",
      "route": "/couple/dashboard",
      "action": "Switch manually to the couple Timeline and hold on the matching event plan.",
      "visibleResult": "The couple Timeline presents the same Glasshouse event inside the guided couple workspace.",
      "atSeconds": 23,
      "frameSha256": "REPLACE_WITH_FRAME_SHA256"
    }
  ],
  "review": {
    "reviewedFrameCount": 3,
    "rawFrameReview": "approved",
    "publicSafetyReview": "approved"
  }
}
```

The other three social receipts keep the same fields but must use their own IDs, canonical raw paths, authored durations, and exact ordered checkpoints from `PHASE_ONE_SOCIAL_VIDEO_STORIES`. `dedicatedChannelTake` is required and must be explicitly true for every social receipt; do not copy Connection footage or checkpoint text into another story.

Use `git rev-parse HEAD`, `shasum -a 256`, `stat -f %z`, and `ffprobe` to populate the real commit, checksum, byte length, dimensions, and duration. For every reviewed checkpoint timestamp, extract the exact PNG bytes from the MP4 and hash those bytes (for example, `ffmpeg -v error -i RAW.mp4 -ss 5.000 -map 0:v:0 -frames:v 1 -f image2pipe -vcodec png pipe:1 | shasum -a 256`). Then run:

```bash
npm run demo:validate-manual-video -- \
  --receipt output/demo-videos/receipts/planner-command-center-walkthrough.json

npm run demo:validate-manual-video -- \
  --receipt output/demo-videos/receipts/connection-over-tools-social.json
```

The validator does not launch or control a browser. It rejects scripted-capture attestations, non-full-window bounds, placeholder, duplicate, out-of-plan, reordered, or altered checkpoints, extra or missing query parameters, a runtime marker that disagrees with the recorded clean commit, wrong raw paths, checksum/size mismatches, checkpoint timestamps that are not strictly increasing, reviewed-frame hashes that do not match frames extracted from the MP4, non-1440x900 footage, footage outside the channel-specific authored bounds, insufficient frame review, and unapproved safety review. The hero remains limited to 70–80 seconds, while social durations use the clamped table above. The recorded commit may later be an ancestor of a clean publication commit, so adding the approval manifest does not make the original receipt unverifiable; unrelated histories still fail closed.

## 6. Narration And Post-Production

Narration is produced separately from the screen. Do not capture the microphone or system audio in the raw browser take.

The canonical narration path is the ElevenLabs generator (see `docs/marketing/elevenlabs-narration.md`):

```bash
ELEVEN_LABS_API_KEY=... npm run demo:narrate -- --demo planner-command-center-walkthrough
```

It reads the `voiceover` lines in `app/data/demoVideos.ts` exactly, aligns each line with its caption cue against the validated take duration, applies the normalization chain below, writes the canonical master plus a `{demoId}.narration.json` provenance manifest, and fails closed when a line cannot fit its timing window. Voice, model, and speed are configurable (`ELEVENLABS_VOICE_ID` for a cloned voice). Listen to every generated master before rendering and reject any take with mispronounced product names, wrong emphasis, or claims the footage does not prove.

A human-recorded narration master remains acceptable. Read the `voiceover` lines exactly, with the final line landing in the five-second CTA. Reject narration with room noise, clipped words, synthetic route names, local-server language, or claims the footage does not prove.

For a human-recorded master, normalize the approved source into the canonical ignored path:

```bash
mkdir -p output/demo-videos/narration
ffmpeg -y -i /path/to/approved-narration-source.wav \
  -af "highpass=f=80,lowpass=f=16000,loudnorm=I=-16:TP=-1.5:LRA=11" \
  -c:a aac -b:a 192k \
  output/demo-videos/narration/planner-command-center-walkthrough.m4a

ffmpeg -y -i /path/to/approved-connection-narration-source.wav \
  -af "highpass=f=80,lowpass=f=16000,loudnorm=I=-16:TP=-1.5:LRA=11" \
  -c:a aac -b:a 192k \
  output/demo-videos/narration/connection-over-tools-social.m4a
```

Only after the manual capture receipt and narration master exist, render the contained website format:

```bash
npm run demo:render -- \
  --demo planner-command-center-walkthrough \
  --format web-16x9 \
  --receipt output/demo-videos/receipts/planner-command-center-walkthrough.json
```

The renderer fails closed when narration is missing and probes the finished MP4 to ensure it contains an audio stream. It uses the exact raw recording duration, fills the 16:9 canvas height with the 16:10 product window, preserves the complete window with `contain`, writes accessible WebVTT captions beside the video instead of burning them over product controls, and fades to the activation CTA for the final five seconds.

Only after one social story's manual receipt and narration master exist, render its channel-native portrait format:

```bash
npm run demo:render -- \
  --demo connection-over-tools-social \
  --receipt output/demo-videos/receipts/connection-over-tools-social.json
```

Render target resolution is channel-aware. Omitting `--format` selects `web-16x9` for a website ID and `social-9x16` for a social ID. An explicit matching format is allowed, but requesting `social-9x16` for a website ID or `web-16x9` for a social ID fails closed. The portrait renderer creates a 1080x1920 composition with the complete 1440x900 source window contained inside a 16:10 product frame, plus the story's pillar, title, outcome, and five-second activation outro. It does not enlarge one product card or leave a cropped fragment in place of the application shell.

After watching the complete website export at normal speed and testing the website modal on desktop and mobile, create the canonical human playback approval receipt and validate it:

```json
{
  "schemaVersion": 1,
  "demoId": "planner-command-center-walkthrough",
  "reviewedAt": "REPLACE_WITH_EXACT_ISO_TIMESTAMP",
  "reviewer": "REPLACE_WITH_HUMAN_REVIEWER_NAME",
  "reviewMethod": "human-normal-speed-playback",
  "sidecars": {
    "captions": {
      "artifactPath": "public/demo-videos/captions/planner-command-center-walkthrough.vtt",
      "artifactSha256": "REPLACE_WITH_SHA256",
      "byteLength": 0
    },
    "transcript": {
      "artifactPath": "public/demo-videos/transcripts/planner-command-center-walkthrough.md",
      "artifactSha256": "REPLACE_WITH_SHA256",
      "byteLength": 0
    }
  },
  "targets": [
    {
      "format": "web-16x9",
      "video": {
        "artifactPath": "public/demo-videos/exports/planner-command-center-walkthrough-16x9.mp4",
        "artifactSha256": "REPLACE_WITH_SHA256",
        "byteLength": 0,
        "width": 1920,
        "height": 1080,
        "durationSeconds": 75,
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

Save it as `output/demo-videos/playback-approvals/planner-command-center-walkthrough.json`. Populate hashes, byte lengths, dimensions, and duration from the real artifacts. The validator re-probes the video and thumbnail, re-hashes all four artifacts, and binds the exact reviewed WebVTT captions and Markdown transcript to the approval receipt. Editing either sidecar after review invalidates the approval.

### Social human playback approval

Watch the complete 1080x1920 social export at normal speed with narration audible, then inspect it in a portrait-mobile presentation with representative top, right, and bottom social-control overlays. The pillar, title, complete product window, outcome, and activation CTA must remain legible and unobscured. `safeAreaApproved` is a human visual attestation; the validator requires that explicit approval and independently verifies the artifact paths, hashes, byte lengths, dimensions, duration, and audio stream. It does not infer visual safety from dimensions alone.

Create `output/demo-videos/playback-approvals/connection-over-tools-social.json` with the channel-specific schema-version-1 shape:

```json
{
  "schemaVersion": 1,
  "demoId": "connection-over-tools-social",
  "reviewedAt": "REPLACE_WITH_EXACT_ISO_TIMESTAMP",
  "reviewer": "REPLACE_WITH_HUMAN_REVIEWER_NAME",
  "reviewMethod": "human-normal-speed-playback",
  "sidecars": {
    "captions": {
      "artifactPath": "public/demo-videos/captions/connection-over-tools-social.vtt",
      "artifactSha256": "REPLACE_WITH_SHA256",
      "byteLength": 0
    },
    "transcript": {
      "artifactPath": "public/demo-videos/transcripts/connection-over-tools-social.md",
      "artifactSha256": "REPLACE_WITH_SHA256",
      "byteLength": 0
    }
  },
  "targets": [
    {
      "format": "social-9x16",
      "video": {
        "artifactPath": "public/demo-videos/exports/connection-over-tools-social-9x16.mp4",
        "artifactSha256": "REPLACE_WITH_SHA256",
        "byteLength": 0,
        "width": 1080,
        "height": 1920,
        "durationSeconds": 30,
        "hasAudio": true
      },
      "thumbnail": {
        "artifactPath": "public/demo-videos/thumbnails/connection-over-tools-social-9x16.png",
        "artifactSha256": "REPLACE_WITH_SHA256",
        "byteLength": 0,
        "width": 1080,
        "height": 1920
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
  "socialPlayback": {
    "portraitMobileApproved": true,
    "safeAreaApproved": true
  }
}
```

A social receipt must contain exactly one `social-9x16` target and `socialPlayback`; `websitePlayback` is forbidden. A website receipt must contain exactly one `web-16x9` target and `websitePlayback`; `socialPlayback` is forbidden. Both receipt types must include the exact canonical captions and transcript paths, checksums, and byte lengths. Repeat the social review and receipt with the exact canonical ID, duration, export, thumbnail, captions, and transcript paths for each of the other three stories.

```bash
npm run demo:validate-playback -- --demo planner-command-center-walkthrough
npm run demo:validate-playback -- --demo connection-over-tools-social
```

Then require every generated asset:

```bash
npm run demo:requirements -- \
  --demo planner-command-center-walkthrough \
  --require-assets

npm run demo:requirements -- \
  --demo connection-over-tools-social \
  --require-assets
```

Repeat `demo:validate-playback` and `demo:requirements -- --require-assets` for `disorganization-tax-social`, `couple-experience-boundaries-social`, and `built-for-planners-social`; one approved story cannot satisfy another story's gate. The asset gate also requires the approved export duration to match the validated raw take within the media-probe tolerance and, once an allowlist entry exists, requires its build commit to match the manual capture receipt. Rendering always revalidates the manual receipt; arbitrary raw-file and duration overrides are rejected. The validated raw recording and narration master stay outside the deployable `public/` tree and are copied into ignored Remotion staging paths only for the render. Both staging files are removed even when rendering fails. Captions may clarify the visible action, but must not hide the product or claim a result the recording does not show.

## 7. Publication Gate

Before changing a demo to `published` or attaching CDN URLs:

1. Watch the entire channel-native export at normal speed with narration audible: 1920x1080 for website or 1080x1920 for social.
2. Confirm the connected story uses the approved fictional Phase 1 workspace.
3. Confirm the product window is complete and never cropped or digitally zoomed.
4. Confirm no local origin, developer UI, private data, tokens, or real contact/payment information is visible.
5. Confirm no real message, payment, signature, vendor action, or private upload occurred.
6. Confirm captions are accurate and readable. For social, confirm the pillar, title, complete product window, outcome, and activation CTA remain inside human-reviewed social-overlay safe areas.
7. For website video, load the demo modal in a visible desktop browser and a mobile viewport and prove playback, poster, controls, captions, and fallback behavior. For social video, watch the portrait export in a visible portrait-mobile presentation and complete both `portraitMobileApproved` and `safeAreaApproved` review.
8. Confirm the raw footage came from that exact story's manually driven browser take. A route preflight, scripted browser pass, website recording, or another social story cannot serve as its final capture evidence.
9. Record the human playback approval separately from the raw-capture receipt and make `npm run demo:validate-playback` plus `npm run demo:requirements -- --require-assets` pass for that exact ID.
10. Add the publication only to its channel's explicit allowlist: `APPROVED_PUBLIC_DEMO_VIDEO_PUBLICATIONS` for website or `APPROVED_PHASE_ONE_SOCIAL_VIDEO_PUBLICATIONS` for social.
11. Persist the approved evidence and deployable media explicitly. The current publication contract uses repo-static `/demo-videos/...` URLs; because generated media is ignored by default, a normal `git add` is intentionally insufficient. For each approved ID, force-track only its canonical raw, narration, capture receipt, playback receipt, export, thumbnail, captions, and transcript together with the allowlist change:

```bash
demo_id=REPLACE_WITH_APPROVED_DEMO_ID
format=16x9 # use 9x16 for a social story

git add -f \
  "output/demo-videos/raw/${demo_id}.mp4" \
  "output/demo-videos/narration/${demo_id}.m4a" \
  "output/demo-videos/narration/${demo_id}.narration.json" \
  "output/demo-videos/receipts/${demo_id}.json" \
  "output/demo-videos/playback-approvals/${demo_id}.json" \
  "public/demo-videos/exports/${demo_id}-${format}.mp4" \
  "public/demo-videos/thumbnails/${demo_id}-${format}.png" \
  "public/demo-videos/captions/${demo_id}.vtt" \
  "public/demo-videos/transcripts/${demo_id}.md"
git add app/data/demoVideos.ts
```

For a human-recorded master there is no narration manifest; drop that one line from the command instead of creating a placeholder. Do not force-track Remotion props or either `.render-input` staging file. Re-run the exact demo's playback and asset validators from the staged tree, then prove the same commands in a fresh checkout before deployment. The raw and narration evidence remain outside the deployable `public/` tree but must be retained so the publication validator can reproduce the receipt checks. CDN publication is not a documentation-only substitution: the current allowlist intentionally accepts only canonical same-origin paths, so CDN support requires an explicit code and validator change before any URL is attached.

If any item fails, keep the public manifest in its retake-safe `recording` state.
