## 2025-02-18 - Verifying Loading States with Playwright
**Learning:** To reliably test transient loading states (like spinners), intercept the network request with `page.route` and introduce a `time.sleep` in the handler. This keeps the UI in loading state long enough for `expect` to verify it.
**Action:** Use this pattern when testing async button interactions.
