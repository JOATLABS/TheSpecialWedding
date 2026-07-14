# Demo gallery fixture provenance

## Scope

These three images are synthetic, repository-owned fixtures for the seeded Sofia and
Daniel planner workspace. They are product-demo content, not screenshots of the app
and not customer, venue, photographer, or stock-library media.

The source images were generated on 2026-07-14 UTC (2026-07-13 in
`America/Chicago`) with the Codex `image_gen.imagegen` tool, recorded in the
generation log as `image_gen__imagegen`. No reference image was supplied to any of
the three generation calls.

## Artifact ledger

| Fixture | Generation completed (UTC) | Original PNG and dimensions | Original SHA-256 | Committed WebP and dimensions | Committed SHA-256 |
| --- | --- | --- | --- | --- | --- |
| Garden terrace portrait | `2026-07-14T02:49:28.733Z` | `exec-3e5fcdf3-d2a0-4ab0-b469-f631e2eb9bfb.png` (`1586x992`) | `f87e365ddbad216ae1a9315e9d388ad17d4fc62ea138b178ece3ae1e33bc1294` | `sofia-daniel-terrace.webp` (`1600x1000`) | `b0c1ae45b2d377618a518a999b0599fbf33d37d36442c2842e5cce6c9b05f453` |
| Glasshouse ceremony aisle | `2026-07-14T02:55:30.701Z` | `exec-2dc68bfc-29a2-4071-b679-2024e20f4f9f.png` (`1536x1024`) | `59f8f18984ca3706f28c7c54a8c3488fe210cab63dc5e09cc30ddaf4d35a4f83` | `sofia-daniel-ceremony.webp` (`1600x1000`) | `d56ac91b101c697bce3b23d60e5d9dd6b58386e40c56b7ed8b67c813794d1f0c` |
| Candlelit reception table | `2026-07-14T02:56:42.658Z` | `exec-3ab19a4d-08cd-4d40-9578-6191858588cc.png` (`1536x1024`) | `71615b2518ac10c0b817e371c980280c5608c5d6cdbea7d7befef666f78d7550` | `sofia-daniel-reception.webp` (`1600x1000`) | `829bb93d0538cb772b402c22b275f94eeb3a8fc9562039ddcbad9e736c1bb661` |

The original PNG files are generation artifacts and are not checked into this
repository. Their generation IDs, dimensions, and hashes are retained here so the
lineage of each smaller committed fixture remains independently identifiable.

## Final conversion record

The final conversion ran at `2026-07-14T02:58:40.754Z` with the repository's
installed `sharp` package under Node 22. Each original was transformed with this
exact operation (with `input` and `output` set to the corresponding filenames in the
ledger):

```js
sharp(input)
  .resize(1600, 1000, { fit: "cover", position: "centre" })
  .webp({ quality: 92 })
  .toFile(output)
```

This operation may center-crop before resizing; it is not a lossless format-only
conversion. An earlier `sips` conversion attempt at `2026-07-14T02:58:14.034Z` was
overwritten by the Sharp outputs and is not the source of the committed bytes. The
visually reviewed Sharp outputs were copied into `public/demo-gallery/` at
`2026-07-14T03:01:26.780Z`.

## Exact generation prompts

### Garden terrace portrait

```text
Use case: photorealistic-natural
Asset type: fictional wedding gallery seed photo inside a planner management platform
Primary request: Create a polished editorial wedding photograph of a fictional newlywed couple standing together on a glasshouse garden terrace, viewed from behind or at an oblique distance so no identifiable faces are visible.
Scene/backdrop: refined garden terrace beside a modern glasshouse wedding venue, greenery and pale stone, no signage
Subject: one bride and one groom, fictional adults, elegant formalwear, natural affectionate posture
Style/medium: high-end natural wedding photography, believable camera optics and skin/fabric texture, not an illustration or render
Composition/framing: landscape 8:5, generous environmental framing, subjects centered slightly left, no tight crop, usable as an object-cover gallery card
Lighting/mood: soft late-afternoon natural light, calm, warm, sophisticated
Color palette: ivory, sage, champagne, soft charcoal
Constraints: entirely fictional people; faces obscured; privacy-safe; no text; no logos; no watermarks; no UI; no borders
Avoid: uncanny anatomy, extra fingers, visible brand marks, oversaturation, heavy bokeh, staged stock-photo smile, local-development imagery
```

### Glasshouse ceremony aisle

```text
Use case: photorealistic-natural
Asset type: privacy-safe fictional wedding gallery photo for a planner-platform demo
Primary request: Empty elegant garden wedding ceremony aisle leading to a modern glasshouse, with neat chairs and restrained ivory-and-sage flowers. No people.
Style/medium: believable high-end editorial wedding photography, natural materials and lens detail, not CGI or illustration
Composition/framing: wide landscape, centered aisle, complete environment visible, no tight crop
Lighting/mood: soft late-afternoon daylight, refined and calm
Constraints: fictional venue, no people, no text, no logos, no watermark, no UI, no border
Avoid: fantasy architecture, oversaturation, excessive decoration, brand marks
```

### Candlelit reception table

```text
Use case: photorealistic-natural
Asset type: privacy-safe fictional wedding gallery photo for a planner-platform demo
Primary request: An elegant candlelit wedding reception table detail at a fictional glasshouse venue, showing refined place settings, linen, understated flowers, menus turned away or blank, and warm candles. No people.
Style/medium: believable high-end editorial wedding photography, realistic glass, linen, flower, and candle textures, not CGI or illustration
Composition/framing: wide landscape, table extending through the frame with enough surrounding venue context, complete place setting details, no tight macro crop
Lighting/mood: warm early-evening candlelight balanced with soft ambient window light, sophisticated and inviting
Color palette: ivory, champagne, sage, muted blush, warm brass
Constraints: fictional venue, privacy-safe, no people, no readable text, no logos, no watermark, no UI, no border
Avoid: oversaturation, fantasy décor, excessive floral clutter, brand marks, legible names, local-development imagery
```

## Privacy and usage statement

- The terrace subjects are fictional and shown from behind; no identifiable face is
  visible. The ceremony and reception fixtures contain no people.
- No customer records, real wedding media, venue media, logos, readable names, or
  other personal data were used as source material.
- No stock or third-party photography was used or incorporated. These files should
  be credited as `Fictional capture fixture generated for The Special Wedding`, not
  to a real photographer or venue.
- The WebPs were visibly inspected at their native `1600x1000` dimensions after the
  final conversion. They remain demo fixtures and must not be represented as a real
  couple, wedding, venue, or commissioned photographer's work.
