# Brand Assets

This directory holds The Special Wedding brand assets. The canonical source of truth for the lockup is the React component at `app/components/brand/BrandLockup.tsx` — the SVG files below are static fallbacks for places that need raw SVG (browser favicon, schema.org metadata, social previews).

## Files

| File | Purpose | Surface |
|------|---------|---------|
| `logo.svg` | Full lockup (icon + wordmark) — primary marketing/site asset | Dark backgrounds |
| `logo-light.svg` | Full lockup tuned for light backgrounds | Cream / white |
| `logo-mark.svg` | Icon + wordmark, no tagline — narrower variant | Dark |
| `logo-icon.svg` | Icon only (rings + heart) | Either |
| `favicon.svg` | Simplified icon for browser tab (16-32px target) | Either |
| `logo_all.png` | Legacy apple-touch-icon — needs regeneration | n/a |

## PNG variants required for PWA

The web app manifest (`/public/manifest.json`) and `app/layout.tsx` reference these PNGs that need to be regenerated whenever the SVG changes:

- `/public/icon-192x192.png` — 192×192 PWA icon
- `/public/icon-512x512.png` — 512×512 PWA icon
- `/public/logo_all.png` — 512×512 apple-touch-icon (maskable)

### Regenerate from SVG

```bash
# Using rsvg-convert (recommended; install via `brew install librsvg`)
rsvg-convert -w 192 -h 192 public/logo-icon.svg -o public/icon-192x192.png
rsvg-convert -w 512 -h 512 public/logo-icon.svg -o public/icon-512x512.png
rsvg-convert -w 512 -h 512 public/logo-icon.svg -o public/logo_all.png

# Or via ImageMagick
magick -density 300 -background transparent public/logo-icon.svg -resize 192x192 public/icon-192x192.png
magick -density 300 -background transparent public/logo-icon.svg -resize 512x512 public/icon-512x512.png
magick -density 300 -background transparent public/logo-icon.svg -resize 512x512 public/logo_all.png
```

For the open graph image (`og-image.png`, referenced in `app/layout.tsx`), composite the full lockup over a 1200×630 dark gradient — this is a marketing-side asset, not a brand mark variant.

## Color palette

The SVG files use these stops (all within the rose family — Special Wedding brand color):

- `#FFFFFF` — highlight peak
- `#FFE5DC` — light rose
- `#E8B4B8` — primary rose (brand color)
- `#C8847E` — wedding-rose accent
- `#A87278` — mid rose
- `#7A4B50` — deep rose
- `#5C2F34` — burgundy
- `#3D1418` — outline / shadow rose
- `#1F0A0C` — near-black rose

If you change any of these stops, mirror the change in `app/components/brand/BrandLockup.tsx` so the React component and SVG fallbacks stay in lockstep.
