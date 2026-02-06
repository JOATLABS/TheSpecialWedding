## 2026-02-06 - Missing Accessibility in Interactive Toggles
**Learning:** Found critical accessibility gaps in `MessageEnrichment` component: toggle buttons lacked `aria-expanded`/`aria-controls` and icon-only buttons lacked `aria-label`. This pattern likely exists in other UI components relying on icons.
**Action:** When implementing or modifying toggleable panels, always pair visible state (CSS) with semantic state (`aria-expanded`) and ensure all icon-only buttons have descriptive `aria-label`s. Use `useId` for robust `aria-controls` linkage.
