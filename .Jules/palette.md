# Palette's Journal 🎨

## Critical UX/Accessibility Learnings

This journal records ONLY critical learnings - no routine updates.
Format: `## YYYY-MM-DD - [Title]` followed by **Learning** and **Action**.

## 2025-02-18 - Complex Interactive Panels
**Learning:** Components with toggleable sub-panels (like MessageEnrichment) often lack critical ARIA state (`aria-expanded`, `aria-controls`) and focus management (`autoFocus`), making them unusable for keyboard/screen-reader users.
**Action:** Always pair toggles with `aria-expanded` and ensure focus moves to the first interactive element in the revealed content.
