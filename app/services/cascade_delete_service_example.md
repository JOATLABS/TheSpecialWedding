# Cascade Delete Service - Usage Examples

The `CascadeDeleteService` provides safe deletion of weddings and all dependent data across collections.

## Overview

### What Gets Deleted?

When a wedding is deleted, the following collections are affected:

**Direct References (wedding_id field):**
- guests
- tables
- activity_logs
- forms
- form_responses
- form_distributions
- budget_items
- budget_categories
- vendor_quotes
- budget_alerts
- gallery
- contracts
- vendor_assignments
- vendor_forms
- vendor_form_submissions
- payment_records
- payment_links
- scheduled_payments

**Indirect References (via guest_id):**
- plus_ones (references guest_id)
- rsvps (references guest_id)
- reminders_sent (references guest_id)
- support_tickets (references guest_id)
- checkins (references guest_id)

## Deletion Modes

### Soft Delete (Recommended)

Soft delete archives records without removing them from the database. It sets `deleted_at` and `deleted_by` fields on all records.

**Advantages:**
- Data is preserved for audit and recovery
- Can be reversed by removing the deleted_at field
- Complies with data retention policies
- Maintains database integrity

**API Usage:**
```python
# Via API (default behavior)
DELETE /api/weddings/{wedding_id}

# Response:
{
    "status": "success",
    "deletion_type": "soft",
    "wedding_id": "abc123",
    "deleted_at": "2026-03-11T15:30:00+00:00",
    "deleted_by": "admin@example.com",
    "records_archived": 245,
    "counts": {
        "guests": 42,
        "plus_ones": 8,
        "rsvps": 42,
        "tables": 5,
        "forms": 3,
        "form_responses": 120,
        "weddings": 1,
        ...
    },
    "message": "Wedding abc123 and all 245 dependent records archived"
}
```

**Service Usage:**
```python
from app.services.cascade_delete_service import cascade_delete_service

result = await cascade_delete_service.soft_delete_wedding(
    wedding_id="abc123",
    deleted_by="admin@example.com"
)
print(result)
```

### Hard Delete (Testing/Compliance Only)

Hard delete permanently removes all records from the database. **This operation is irreversible.**

**Advantages:**
- Completely removes all traces of a wedding
- Useful for compliance requirements (GDPR right to be forgotten)
- Cleans up test data

**Disadvantages:**
- Irreversible - no way to recover data
- Should only be used in specific scenarios

**API Usage:**
```python
# Via API with hard_delete parameter
DELETE /api/weddings/{wedding_id}?hard_delete=true

# Response:
{
    "status": "success",
    "deletion_type": "hard",
    "wedding_id": "abc123",
    "deleted_at": "2026-03-11T15:30:00+00:00",
    "deleted_by": "admin@example.com",
    "records_deleted": 245,
    "counts": {...},
    "message": "Wedding abc123 and all 245 dependent records permanently deleted"
}
```

**Service Usage:**
```python
result = await cascade_delete_service.hard_delete_wedding(
    wedding_id="abc123",
    deleted_by="admin@example.com"
)
```

## Additional Methods

### Get Dependent Counts

Count all dependent records before deletion (useful for confirmation dialogs):

```python
counts = await cascade_delete_service._get_dependent_counts(wedding_id="abc123")
print(counts)
# Output:
# {
#     "guests": 42,
#     "plus_ones_via_guest": 8,
#     "rsvps_via_guest": 42,
#     ...
# }
```

### Verify Deletion

Verify that a wedding and all dependents have been successfully deleted:

```python
verification = await cascade_delete_service.verify_deletion(wedding_id="abc123")
print(verification)
# Output for successful hard delete:
# {
#     "wedding_id": "abc123",
#     "is_fully_deleted": true,
#     "remaining_records": {},
#     "verified_at": "2026-03-11T15:30:00+00:00"
# }

# Output for soft delete (still has records with deleted_at):
# {
#     "wedding_id": "abc123",
#     "is_fully_deleted": false,
#     "remaining_records": {
#         "guests": "SOFT_DELETED",
#         "tables": "SOFT_DELETED"
#     },
#     "verified_at": "2026-03-11T15:30:00+00:00"
# }
```

## Error Handling

The service handles errors gracefully:

```python
try:
    result = await cascade_delete_service.soft_delete_wedding(wedding_id, user_email)
except ValueError as e:
    # Wedding not found
    print(f"Wedding not found: {e}")
except Exception as e:
    # Other database errors
    print(f"Deletion failed: {e}")
```

Errors during deletion are logged and will not leave partial deletes. If an error occurs while deleting from a specific collection, the operation is stopped and an exception is raised.

## Logging

All deletion operations are logged to the `activity_logs` collection with:
- wedding_id
- deletion_type (soft/hard)
- deleted_by (user email)
- deleted_at (timestamp)
- counts (records affected by collection)
- total_records

Example query to find deletion logs:
```python
logs = await mongo.db["activity_logs"].find({
    "event_type": "wedding_deletion",
    "wedding_id": "abc123"
}).to_list(length=None)
```

## Integration with Billing

For metered subscriptions, the API endpoint handles:
1. Meter reversal (credits back the wedding count)
2. Billing period tracking (prevents double-crediting)
3. Idempotency (safe to retry without side effects)

The cascade delete service focuses only on data deletion, while the API endpoint handles billing integration.

## Best Practices

1. **Use Soft Delete by Default**
   - Preserves data for audit and recovery
   - Better for customer trust and compliance
   - Easy to reverse if deletion was accidental

2. **Get Counts Before Deletion**
   - Display to user: "This will delete X guests, Y forms, Z responses"
   - Helps confirm the user intended the deletion

3. **Log Deletions**
   - All deletions are logged to activity_logs
   - Useful for compliance and audit trails

4. **Use Hard Delete Only When Necessary**
   - GDPR right to be forgotten
   - Test data cleanup
   - Compliance requirements
   - Always require additional confirmation

5. **Verify After Hard Delete**
   - Use verify_deletion() to confirm success
   - Especially important for critical operations

## Backward Compatibility

The soft delete also sets `status: "cancelled"` and `cancelled_at` on the wedding record for backward compatibility with existing code that checks these fields.
