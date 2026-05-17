// LEGACY filename — the real component now lives at
// ``./CalendarConnect.tsx``. This shim is retained so any imports
// that still reference the old path (mid-refactor branches, third-
// party tooling, etc.) keep resolving. Safe to delete once
// ``grep -rn "GoogleCalendarConnect"`` returns zero hits across the
// repo.
export { default } from './CalendarConnect';
