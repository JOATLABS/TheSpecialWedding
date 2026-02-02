## 2024-05-22 - [MongoDB Mixed ID Types]
**Learning:** `rsvps` collection contains mixed `guest_id` types (both `ObjectId` and `string`).
**Action:** When implementing batch queries using `$in`, always include both `ObjectId` and `string` versions of the ID in the query array to ensure all records are found.
