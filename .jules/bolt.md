## 2025-05-23 - Mixed ObjectId and String ID Performance
**Learning:** The `rsvps` collection contains mixed `guest_id` types (ObjectId and string). When implementing batch fetching (e.g., to solve N+1), you must query for *both* formats using `$in` to ensure no data is missed, as simpler queries might only catch one type.
**Action:** When optimizing queries on legacy collections, always inspect data types first and construct `$in` clauses that cover all historical ID formats.
