# Palette's Journal

This journal records critical UX/accessibility learnings and patterns for the project.

## Format
`## YYYY-MM-DD - [Title]
**Learning:** [UX/a11y insight]
**Action:** [How to apply next time]`

## 2025-02-18 - Complex Component Accessibility
**Learning:** Complex interactive components like `MessageEnrichment` often miss accessibility details (ARIA labels, focus management) that are standard in base components. Specifically, toggle patterns need `aria-expanded` and `aria-controls` to be truly accessible.
**Action:** When auditing complex components, verify the "toggle" pattern includes `aria-expanded`, `aria-controls`, and proper focus management (e.g., `autoFocus` on panel open).
