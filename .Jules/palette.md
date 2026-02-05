## 2024-05-22 - MessageEnrichment Accessibility
**Learning:** Client-side components with conditional rendering (like toggle panels) need explicit `aria-expanded` and `aria-controls` management, plus unique IDs via `useId` to link triggers to content.
**Action:** Always use `useId` for generating IDs in reusable components and ensure focus is managed (e.g., `autoFocus`) when panels appear.
