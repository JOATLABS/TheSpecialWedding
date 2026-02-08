# Bolt's Performance Journal ⚡

## 2024-05-23 - Testing Async MongoDB with Synchronous Mongomock
**Learning:** This codebase uses `motor` for async MongoDB operations in production but `mongomock` (synchronous) for testing. Standard `mongomock` methods are not awaitable.
**Action:** When testing services that `await` DB calls, wrap `mongomock` collection methods in async functions or use `AsyncMock` with a `side_effect` that delegates to the synchronous `mongomock` method. This allows testing async logic without a real MongoDB connection.
