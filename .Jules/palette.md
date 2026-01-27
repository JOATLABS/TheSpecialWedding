## 2024-05-24 - Accessible Form Toggles
**Learning:** Interactive toggles (password visibility, settings switches) often lack semantic meaning for screen readers, leaving users guessing their state and function.
**Action:** Always add `aria-label` to icon-only toggles and use `role="switch"` with `aria-checked` for binary settings controls.

## 2024-05-24 - Overriding Text with ARIA Labels
**Learning:** Adding `aria-label` to buttons with visible text (e.g., "Select All (5)") overrides the text content for screen readers, causing loss of dynamic information like counts.
**Action:** Only use `aria-label` when the visible text is insufficient or missing (icon-only buttons). For buttons with text, rely on the text content.
