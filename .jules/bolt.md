## 2025-05-18 - Missing DB Indexes
**Learning:** The application uses MongoDB but several core collections (`guests`, `plus_ones`, `rsvps`) were completely unindexed despite being queried frequently by foreign keys (`wedding_id`, `guest_id`). This is a classic "silent killer" of performance as data grows.
**Action:** When working on backend optimizations, always check `app/core/database_indexes.py` first to ensure all collections with relationships have corresponding indexes.
