## 2026-02-09 - Accessible Toggle Panels
**Learning:** For components with dynamic content toggling (like `MessageEnrichment`), linking buttons to panels using `aria-controls` and `aria-expanded` is critical for screen reader users. `useId` provides a stable, unique ID for these associations without prop drilling. Additionally, `autoFocus` on the first interactive element inside a newly revealed panel greatly improves keyboard navigation flow.
**Action:** Use `useId` for all internal component ID generation and ensure focus management is considered for all dynamic UI states.
