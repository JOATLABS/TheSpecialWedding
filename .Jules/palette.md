## 2024-05-24 - Accessible Form Toggles
**Learning:** Interactive toggles (password visibility, settings switches) often lack semantic meaning for screen readers, leaving users guessing their state and function.
**Action:** Always add `aria-label` to icon-only toggles and use `role="switch"` with `aria-checked` for binary settings controls.
