# Demo Video Production Runbook

This runbook turns the scripted demo manifest into real browser recordings and Remotion exports.

## Source Of Truth

- Script inventory: `app/data/demoVideos.ts`
- Capture/export requirements: `app/data/demoVideoProduction.ts`
- Public demo library: `/resources/demos`
- Remotion entry point: `remotion/index.ts`

Every demo must keep these assets aligned before it can be marked `published` in the manifest:

- raw browser recording: `public/demo-videos/raw/{demoId}.webm`
- captions: `public/demo-videos/captions/{demoId}.json`
- transcript: `public/demo-videos/transcripts/{demoId}.md`
- website export: `public/demo-videos/exports/{demoId}-16x9.mp4`
- website thumbnail: `public/demo-videos/thumbnails/{demoId}-16x9.png`
- social export: `public/demo-videos/exports/{demoId}-9x16.mp4`
- social thumbnail: `public/demo-videos/thumbnails/{demoId}-9x16.png`

Generated media folders are gitignored. Upload final production assets to the selected CDN/storage target, then update the manifest `assetUrl`, `thumbnailUrl`, `captionUrl`, `transcriptUrl`, `socialAssetUrl`, `socialThumbnailUrl`, `recordedAt`, and `appBuildLabel` fields for the published batch.

## Requirement Gate

Run this before recording:

```bash
npm run demo:requirements
```

Run this before publishing one clip:

```bash
npm run demo:requirements -- --demo morning-view-demo --require-assets
```

`--require-assets` must fail until the raw recording, captions, transcript, MP4 export, and thumbnail exist.

## Seed And Session Requirements

Production recordings need seeded demo data, not live customer data.

- Create the demo planner/couple login identities first with `scripts/setup_smoke_accounts.py`.
- Enrich that workspace for product-video capture with:

```bash
SMOKE_PLANNER_EMAIL=demo-planner+videos@thespecialwedding.io npm run demo:seed
```

- Planner/admin flows require a seeded planner session state.
- Couple flows require a seeded couple session state.
- Vendor token flows require disposable contract/vendor tokens.
- Guest upload flows require disposable upload tokens and prepared non-private demo media.
- Payment flows require Stripe test mode and must stop before irreversible confirmation.
- Communications flows require local/test email and SMS transports only.

Recommended browser session-state locations:

```text
output/demo-videos/state/demo-mixed.json
```

Create the mixed planner/couple state used by the batch recorder with:

```bash
SMOKE_PLANNER_EMAIL=demo-planner+videos@thespecialwedding.io \
SMOKE_PLANNER_PASSWORD=... \
SMOKE_COUPLE_EMAIL=demo-couple+videos@thespecialwedding.io \
SMOKE_COUPLE_PASSWORD=... \
npm run demo:auth-state -- --base-url http://127.0.0.1:3100
```

The enriched seeder writes route parameters to `output/demo-videos/capture-fixtures.json`.

## Smoke Export Proof

Use this to prove the pipeline without claiming a production demo is complete:

```bash
npm run demo:record -- \
  --demo planner-command-center-walkthrough \
  --route /resources/demos \
  --smoke \
  --max-seconds 8

npm run demo:render -- \
  --demo planner-command-center-walkthrough \
  --format web-16x9 \
  --duration-seconds 8
```

This produces a real browser recording and a real Remotion MP4, but it is not a publishable product walkthrough because it records the demo library route instead of the protected planner/couple workflow.

## Production Recording Pattern

Start the local app with the normal testbed or manual commands:

```bash
python testbed/testbed.py up --with-frontend
```

For the local manual path used by the production demo batch:

```bash
uvicorn app.main:app --reload --port 8000
npm run dev -- --hostname 127.0.0.1 --port 3100
```

Before recording, audit every route in the demo playlist. This fails if a page lands on a login/error shell or if same-origin 403/5xx subrequests occur behind an otherwise-rendered page:

```bash
npm run demo:verify-routes -- --base-url http://127.0.0.1:3100
```

Then record one demo:

```bash
npm run demo:record -- \
  --demo morning-view-demo \
  --base-url http://127.0.0.1:3100 \
  --storage-state testbed/state/demo-planner.json
```

Parameterized routes must be resolved explicitly:

```bash
npm run demo:record -- \
  --demo microsite-auto-publishes-demo \
  --storage-state testbed/state/demo-planner.json \
  --route-param id=DEMO_WEDDING_ID \
  --route-param slug=demo-wedding
```

Side-effect-capable routes must be acknowledged only after fixture safety is confirmed:

```bash
npm run demo:record -- \
  --demo contract-sign-pay-demo \
  --storage-state testbed/state/demo-planner.json \
  --route-param id=DEMO_CONTRACT_ID \
  --route-param token=DEMO_VENDOR_TOKEN \
  --allow-side-effect-fixtures
```

Render both final formats:

```bash
npm run demo:render -- --demo morning-view-demo --format web-16x9
npm run demo:render -- --demo morning-view-demo --format social-9x16
```

Verify assets:

```bash
npm run demo:requirements -- --demo morning-view-demo --require-assets
```

Batch capture/render all demos, using seeded route parameters and the mixed browser state:

```bash
npm run demo:capture-all -- --base-url http://127.0.0.1:3100
```

To rerun only selected clips after a route fix:

```bash
npm run demo:capture-all -- \
  --base-url http://127.0.0.1:3100 \
  --demo planner-command-center-walkthrough \
  --demo microsite-auto-publishes-demo
```

Evidence receipts from the production pass live under `output/demo-videos/`:

- `route-audit-receipt.json`
- `capture-receipt.json`
- `media-audit-receipt.json`
- `contact-sheet-16x9.png`
- `contact-sheet-9x16.png`

## Publishing Checklist

Before changing a manifest item to `published`:

1. The video shows the real product UI, not a slide or fake mock.
2. Cursor movement and pauses are human-readable.
3. No private names, emails, phone numbers, payment data, local file paths, or real tokens are visible.
4. No real SMS, email, payment, legal signature, or external vendor action was triggered.
5. Captions match the approved script.
6. The 16:9 and 9:16 exports render without black frames, clipped captions, or unreadable text.
7. The public modal plays the uploaded asset and still exposes an accurate fallback if the asset is unavailable.
