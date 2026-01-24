## 2024-05-23 - [Missing Guest Indexes]
**Learning:** The `guests` collection was missing indexes entirely, despite being a high-traffic entity for lookups by `wedding_id` and `token`. This likely caused O(N) scans on every guest list load.
**Action:** Always verify index existence for core entities in `app/core/database_indexes.py` or equivalent during performance audits.
