## 2026-02-02 - Interactive Panel Accessibility
**Learning:** Interactive sub-panels (like in `MessageEnrichment`) are often missed by screen readers if the toggle buttons don't communicate state (`aria-expanded`) and the close buttons lack labels.
**Action:** Always pair toggle buttons with `aria-expanded` and ensure close buttons inside panels have descriptive `aria-label`s. Add `autoFocus` to the first input for better keyboard flow.
