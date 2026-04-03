# Sprint 5 Code Review: couple_portal.py
## Focus: P1-6 (Note Replies) & P1-2 (Meeting Scheduling)

**Reviewed**: Lines 1330-1665 (Sprint 5 new endpoints)
**Comparison patterns**: Lines 500-700 (existing note handling)
**Review date**: 2026-03-22

---

## CRITICAL FINDINGS

### 🔴 SECURITY: Missing archived wedding check for note reply endpoints (Lines 1344-1433)

**Issue**: P1-6 note reply endpoints (`reply_to_event_note`, `reply_to_item_note`) do NOT check if the wedding is archived before allowing replies.

**Current code** (lines 1348-1383):
```python
async def reply_to_event_note(
    data: ReplyToNoteRequest,
    event_index: int = Path(..., ge=0),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Planner replies to an event-level note from the couple. Creates a new note with reply_to set."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)
    # ... no archive check
```

**Contrast with** existing note endpoints (lines 520-521, 561-562):
```python
if couple.get("wedding_archived"):
    raise HTTPException(status_code=403, detail="Notes are disabled for archived weddings")
```

**Impact**: Planners can continue modifying archived weddings by adding note replies, violating the archived wedding immutability contract observed in other endpoints (lines 520, 561, 804-806).

**Recommendation**: Add archive check immediately after `_get_wedding_for_planner()`:
```python
if wedding.get("archived") or wedding.get("wedding_archived"):
    raise HTTPException(status_code=403, detail="Notes are disabled for archived weddings")
```

**Affected lines**: 1354-1356 (reply_to_event_note), 1399-1400 (reply_to_item_note)

---

### 🔴 SECURITY: Weak ObjectId validation in schedule_meeting (Lines 1469-1472)

**Issue**: Generic exception catch (`except (InvalidId, Exception)`) silently swallows validation errors without proper logging or specific error handling.

**Current code** (lines 1469-1472):
```python
try:
    ObjectId(data.wedding_id)
except (InvalidId, Exception):
    raise HTTPException(status_code=400, detail="Invalid wedding ID format")
```

**Problem**: Catches all exceptions (including DB failures, timeout errors) and returns a 400 response, masking real failures. Also doesn't validate that the ObjectId conversion actually succeeds before proceeding.

**Recommendation**: Tighten validation:
```python
try:
    ObjectId(data.wedding_id)
except InvalidId:
    raise HTTPException(status_code=400, detail="Invalid wedding ID format")
```

The generic `Exception` catch is unnecessary since `ObjectId()` only raises `InvalidId` on bad input.

**Affected lines**: 1469-1472, 1596-1599 (cancel_meeting has same pattern)

---

### 🟡 PERFORMANCE: Unbounded query in list_meetings_couple (Lines 1646-1651)

**Issue**: Query filters by `wedding_id`, `category`, `planner_email` but may lack database index, causing full collection scans.

**Current code** (lines 1646-1651):
```python
cursor = tasks_collection.find({
    "wedding_id": wedding_id,
    "category": "meeting",
    "planner_email": planner_email,
    "start_date": {"$gte": now},
}).sort("start_date", 1).limit(20)
```

**Issue**: No compound index on `{wedding_id, category, planner_email, start_date}`. With N planner tasks across multiple weddings, this could scan many documents.

**Comparison**: list_meetings_planner (lines 1562-1566) uses identical query pattern without sorting edge-case handling.

**Recommendation**:
1. Add compound index at application startup or via migration:
```python
await tasks_collection.create_index([
    ("wedding_id", 1),
    ("category", 1),
    ("planner_email", 1),
    ("start_date", 1)
])
```
2. Add pagination metadata (skip param) to list_meetings_planner for consistency.

**Affected lines**: 1562-1566 (list_meetings_planner), 1646-1651 (list_meetings_couple)

---

### 🟡 CORRECTNESS: Race condition in reply_to_event_note parent note update (Lines 1375-1377)

**Issue**: Parent note status is updated in-memory without concurrency control. Another planner could have updated the same note status between read and write.

**Current code** (lines 1375-1377):
```python
# Also mark parent note as addressed if still pending/seen
if parent_note.get("status") in ("pending", "seen"):
    parent_note["status"] = "addressed"
```

**Problem**: The entire event_notes array is updated via `_save_wedding_events()` (line 1379), but if concurrent requests both check `parent_note.get("status")`, both could transition from "pending" → "addressed" simultaneously. Less critical than write-write conflicts, but inconsistent with the optimistic lock pattern used by `_save_wedding_events()`.

**Impact**: Low severity (idempotent state transition), but violates consistency model.

**Recommendation**: Use MongoDB atomic operator to avoid race:
```python
# Instead of modifying in-memory array:
await mongo.get_weddings_collection().update_one(
    {
        "_id": wedding["_id"],
        f"events.{event_index}.event_notes.id": note_id,
        f"events.{event_index}.event_notes.status": {"$in": ["pending", "seen"]}
    },
    {"$set": {f"events.{event_index}.event_notes.$.status": "addressed"}}
)
```

**Affected lines**: 1375-1377 (reply_to_event_note), 1424-1426 (reply_to_item_note)

---

## MEDIUM FINDINGS

### 🟡 SECURITY: Missing wedding_id validation in cancel_meeting (Line 1589)

**Issue**: `cancel_meeting()` accepts `wedding_id` as query parameter but doesn't validate it matches the retrieved task's `wedding_id`.

**Current code** (lines 1587-1608):
```python
@router.delete("/couple-portal/meetings/{meeting_id}", tags=["Couple Portal - Meetings"])
async def cancel_meeting(
    meeting_id: str = Path(...),
    wedding_id: str = Query(...),  # <-- Trusts query param
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Planner cancels a scheduled meeting. Removes from Google Calendar if synced."""
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    try:
        ObjectId(meeting_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")

    tasks_collection = mongo.get_planner_tasks_collection()
    task = await tasks_collection.find_one({
        "_id": ObjectId(meeting_id),
        "planner_email": current_user.email,
        "category": "meeting",
    })  # <-- Does NOT verify task.wedding_id == data.wedding_id
```

**Attack vector**: A planner could request `DELETE /couple-portal/meetings/{id_from_wedding_A}?wedding_id=wedding_B` and if they have access to wedding_B, the access check passes. Then deletion proceeds based on `meeting_id` alone.

**Recommendation**: Add assertion after task retrieval:
```python
task = await tasks_collection.find_one({
    "_id": ObjectId(meeting_id),
    "planner_email": current_user.email,
    "category": "meeting",
    "wedding_id": wedding_id,  # Add constraint here
})
```

**Affected lines**: 1601-1608

---

### 🟡 MAINTAINABILITY: Code duplication in note reply logic (Lines 1363-1384 vs 1412-1433)

**Issue**: `reply_to_event_note()` and `reply_to_item_note()` contain near-identical reply note creation and parent note update logic.

**Duplicated blocks**:
- Note construction: lines 1363-1371 vs 1412-1420 (99% identical)
- Parent note status update: lines 1375-1377 vs 1424-1426 (identical)

**Impact**: Maintainability burden; any bug fix (e.g., adding a field to replies) must be applied twice.

**Recommendation**: Extract to helper function:
```python
def _create_reply_note(author_email: str, parent_note_id: str, text: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "author_role": "planner",
        "author_name": author_email,
        "text": text,
        "status": "addressed",
        "reply_to": parent_note_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

# Then in both endpoints:
reply_note = _create_reply_note(current_user.email, note_id, data.text)
```

**Affected lines**: 1348-1433

---

### 🟡 MAINTAINABILITY: Inconsistent error handling in Google Calendar sync (Lines 1512-1532, 1611-1618)

**Issue**: Google Calendar sync failures are logged but silently ignored (non-blocking). However, inconsistent patterns:

**schedule_meeting** (lines 1512-1532):
```python
if data.sync_to_google:
    try:
        from app.services.google_calendar_service import google_calendar_service
        status = await google_calendar_service.get_connection_status(current_user.email)
        if status.get("connected"):
            google_event_id = await google_calendar_service.create_google_event(...)
            # ... update task
    except Exception as e:
        logger.error(f"Failed to sync meeting to Google Calendar: {e}")
```

**cancel_meeting** (lines 1611-1618):
```python
if task.get("synced_to_google") and task.get("google_event_id"):
    try:
        from app.services.google_calendar_service import google_calendar_service
        await google_calendar_service.delete_google_event(...)
    except Exception as e:
        logger.error(f"Failed to delete meeting from Google Calendar: {e}")
```

**Problem**:
1. `schedule_meeting` checks connection status first; `cancel_meeting` doesn't (inconsistent)
2. Both catch generic `Exception` rather than specific errors
3. No way for caller to know sync status (always returns success even if Google Calendar sync failed)

**Recommendation**: Return sync status in response:
```python
return {
    "message": "Meeting scheduled",
    "meeting": {...},
    "google_sync_status": "synced" if task_doc["synced_to_google"] else "pending"
}
```

**Affected lines**: 1512-1532, 1611-1618

---

## LOW FINDINGS

### 🟢 EDGE CASE: Missing end_date default in schedule_meeting (Line 1491)

**Issue**: If `end_date` is null, defaults to `start_date`. No validation that end_date >= start_date.

**Current code** (line 1491):
```python
"end_date": data.end_date or data.start_date,
```

**Edge case**: Client could send `start_date: 2026-03-25T10:00Z` and `end_date: 2026-03-25T09:00Z` (end before start). This is logically invalid but not rejected.

**Impact**: Low (Google Calendar would reject it), but bad data quality.

**Recommendation**: Add Pydantic validator:
```python
class ScheduleMeetingRequest(BaseModel):
    # ...
    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and v < values.get('start_date'):
            raise ValueError("end_date must be >= start_date")
        return v
```

**Affected lines**: 1442-1454 (ScheduleMeetingRequest model)

---

### 🟢 NAMING: Inconsistent author_name field (Lines 1366, 1415)

**Issue**: Reply note author_name is set to `current_user.email`. Couple notes use `couple_name or email` (lines 533, 579). Inconsistent.

**Current couple pattern** (line 533):
```python
"author_name": couple_name or couple["email"],
```

**Current planner pattern** (line 1366):
```python
"author_name": current_user.email,
```

**Problem**: UI might display "alice@planner.com" instead of "Alice Smith". Minor, but inconsistent with couple-side naming.

**Recommendation**: Update to use planner name if available:
```python
"author_name": current_user.full_name or current_user.email,
```

**Affected lines**: 1366, 1415

---

### 🟢 LOGGING: Missing wedding context in log messages (Lines 1383, 1432, 1534, 1622)

**Issue**: Log messages use `note_id` or `meeting_id` but should include `wedding_id` for traceability.

**Current** (line 1383):
```python
logger.info(f"Planner {current_user.email} replied to event note {note_id}")
```

**Better**:
```python
logger.info(f"Planner {current_user.email} replied to event note {note_id} on wedding {wedding['_id']}")
```

**Affected lines**: 1383, 1432, 1534, 1622

---

## COMPARISON WITH EXISTING PATTERNS

### ✅ Correct patterns observed:

1. **Auth checks**: Both P1-6 and P1-2 use `require_team_or_planner` dependency correctly (lines 1352, 1460, 1555, 1590)
2. **Couple auth**: `list_meetings_couple()` correctly uses `require_couple_auth` (line 1629)
3. **Wedding access**: Both reply endpoints call `_get_wedding_for_planner()` which enforces access control (lines 1355, 1399)
4. **Optimistic locking**: Note replies use `_save_wedding_events()` which applies optimistic concurrency check via updated_at (line 1379, 1428)
5. **Input validation**: ReplyToNoteRequest and ScheduleMeetingRequest use Pydantic with proper constraints (lines 1338-1342, 1442-1454)

### ❌ Inconsistencies:

1. **Archived wedding checks**: Note endpoints check archived status (520, 561); reply endpoints don't (see critical finding #1)
2. **ObjectId handling**: Both note operations and meeting operations use weak exception catching (see critical finding #2)
3. **Google Calendar imports**: Importing inside try block is consistent across both endpoints (1515, 1613)

---

## RECOMMENDATIONS SUMMARY

| Priority | Category | Lines | Action |
|----------|----------|-------|--------|
| P0 | Security | 1354-1433 | Add archived wedding check to note reply endpoints |
| P0 | Security | 1601-1608 | Add wedding_id constraint to cancel_meeting query |
| P1 | Correctness | 1375-1377, 1424-1426 | Use MongoDB atomic operators to avoid race on parent note status |
| P1 | Performance | 1562-1651 | Create compound index on planner_tasks(wedding_id, category, planner_email, start_date) |
| P2 | Maintainability | 1348-1433 | Extract reply note creation logic to helper function |
| P2 | Maintainability | 1512-1532, 1611-1618 | Return Google Calendar sync status in response; improve error specificity |
| P3 | Edge case | 1442-1454 | Add Pydantic validator for end_date >= start_date |
| P3 | Naming | 1366, 1415 | Use planner full_name instead of email for consistency |
| P3 | Logging | 1383, 1432, 1534, 1622 | Add wedding_id to log messages for traceability |

---

## TESTING RECOMMENDATIONS

1. **Test archived wedding rejection**: POST to note reply endpoint with archived wedding → expect 403
2. **Test concurrent note updates**: Simulate two planners replying to same note simultaneously
3. **Test invalid ObjectIds**: Test with malformed IDs in meeting endpoints
4. **Test wedding_id mismatch in cancel_meeting**: Request with mismatched wedding_id/meeting_id pair
5. **Test Google Calendar sync failure**: Mock google_calendar_service exception, verify meeting created locally
6. **Test end_date validation**: Create meeting with end_date < start_date

