# Figma-ready SaaS landing blueprint

This document captures the artboard structure, component styles, and spacing tokens you can drop into a new Figma file to replicate the updated Special Wedding marketing site. Frames are sized for desktop (`1440 × 3800`) with nested auto-layout sections for tablet (`834 × variable`) and mobile (`390 × variable`).

## Frame hierarchy
1. **`Landing / Desktop`** – 12-column layout (80px margins) with 24px gutters.
   - Hero
   - Product Tour
   - Integrations Grid
   - Workflow Timeline
   - Benefits Mosaic
   - Pricing Deck
   - Testimonials
   - FAQ & Resources
   - Closing CTA
2. **`Landing / Tablet`** – 8-column layout (48px margins) mirroring the same section order.
3. **`Landing / Mobile`** – 4-column layout (24px margins), all sections converted to stacked vertical cards.

## Key styles
- **Typography**
  - Display / 60px / 120% / SemiBold (Inter)
  - Heading / 44px / 120% / SemiBold (Inter)
  - Body Large / 18px / 160% / Medium (Inter)
  - Body Small / 14px / 170% / Regular (Inter)
  - Supporting Caps / 11px / 160% / 400 with 320 tracking
- **Color tokens**
  - `Primary 500` `#3B82F6`
  - `Primary 600` `#2563EB`
  - `Primary 900` `#0F172A`
  - `Lavender 500` `#7C3AED`
  - `Emerald 400` `#34D399`
  - `Surface 100` `#F8FAFC`
  - `Surface 0` `#FFFFFF`
- **Effects**
  - Drop shadow: `0 40 120 -70 rgba(15, 23, 42, 0.35)`
  - Glow: `0 80 180 -90 rgba(59, 130, 246, 0.4)`
  - Gradient overlay: `radial` from `rgba(59,130,246,0.35)` to transparent

## Section breakdown
### Hero
- 3-column auto layout (Logo cluster, Navigation, CTA set)
- Hero body uses 6-column span with responsive stack on mobile
- Featured plan card uses nested auto layout with gradient background & icon chips

### Product Tour
- Split frame: copy column (width 520) + visual column (width 560)
- Stats cards use 16px padding, 12px corner radius, 16px vertical spacing

### Integrations
- Responsive component set with 3-up variant (desktop), 2-up (tablet), 1-up (mobile)
- Cards sized 200 × 160 with centered logo text

### Workflow Timeline
- Vertical stepper with 24px gap; each item uses badge component (`badge/time`), heading, body copy

### Benefits Mosaic
- 2 × 2 grid of feature cards (minimum height 220)
- Statistic tiles pinned to top-left for contrast

### Pricing Deck
- Component set with `plan/base`, `plan/featured`, `plan/outline` variants
- Toggle chips for monthly/yearly states

### Testimonials
- Auto layout of 3 cards with shared padding (24px) and drop shadow token

### FAQ & Resources
- FAQ column uses accordion component (chevron toggles)
- Resource grid uses card components (title + description + arrow glyph)

### Closing CTA
- Full-width gradient container with stacked copy and dual buttons (primary/ghost)

## Interaction notes
- CTA buttons have elevation variant (`rest`, `hover`, `press`) using 4dp, 8dp, 12dp shadows
- Modal (Planner auth) slides up on mobile (`0 → 16px` motion) and scales in on desktop (`0.94 → 1`)
- Smooth scroll anchors for navigation: `#features`, `#workflow`, `#pricing`, `#testimonials`

## Export guidance
- Export hero visual placeholder at `1280 × 860` PNG with 2x retina variant
- Export integration logos as SVG for crisp scaling

Drop this outline into Figma as section descriptions to accelerate collaboration between design and engineering.
