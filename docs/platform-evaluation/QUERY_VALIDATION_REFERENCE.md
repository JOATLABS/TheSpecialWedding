# Query Validation Functions - Quick Reference

## Import All Validators

```python
from app.utils.query_validation import (
    # Pagination
    validated_page,
    validated_limit,
    validated_limit_extended,
    validated_skip,
    calculate_pagination_params,

    # String/Filter
    validated_string_filter,
    validated_date_string,
    validated_sort_field,
    validated_sort_direction,

    # Enums/Specific
    validated_enum_filter,
    validated_status_filter,
    validated_boolean_filter,
)
```

## Common Usage Patterns

### 1. Simple Pagination

```python
page: int = Query(1, ge=1, le=10000, description="Page number")
limit: int = Query(20, ge=1, le=100, description="Items per page")

# In endpoint:
skip, limit = calculate_pagination_params(page, limit)
results = await collection.find().skip(skip).limit(limit).to_list(length=limit)
```

### 2. Filter by Status

```python
status: Optional[str] = Query(None, description="Filter by status")

# In endpoint:
status = validated_status_filter(status, ['active', 'inactive', 'pending'])
if status:
    query['status'] = status
```

### 3. Free-text Search

```python
search: Optional[str] = Query(None, description="Search text")

# In endpoint:
search = validated_string_filter(search, max_length=100)
if search:
    query['$text'] = {'$search': search}  # Now safe to use
```

### 4. Enum Select (format, direction, etc.)

```python
format: str = Query("json", description="Export format")
direction: str = Query("asc", description="Sort direction")

# In endpoint:
format = validated_enum_filter(format, ["json", "csv"]) or "json"
direction = validated_enum_filter(direction, ["asc", "desc"]) or "asc"
```

### 5. Date Range Filter

```python
start_date: Optional[str] = Query(None, description="ISO date")
end_date: Optional[str] = Query(None, description="ISO date")

# In endpoint:
start_date = validated_date_string(start_date)
end_date = validated_date_string(end_date)

if start_date:
    query['date'] = {'$gte': datetime.fromisoformat(start_date)}
if end_date:
    query['date'].update({'$lte': datetime.fromisoformat(end_date)})
```

### 6. Sort Field Selection

```python
sort: str = Query("created_at", description="Sort field")

# In endpoint:
allowed_fields = ["created_at", "updated_at", "name", "status"]
sort = validate_sort_field(sort, allowed_fields, default_field="created_at")
```

## Function Signatures

### Pagination Functions

```python
def validated_page(page: int = Query(1, ge=1, le=10000)) -> int:
    """Validates page number for pagination."""

def validated_limit(limit: int = Query(20, ge=1, le=100)) -> int:
    """Validates limit/items per page (standard range)."""

def validated_limit_extended(limit: int = Query(50, ge=1, le=200)) -> int:
    """Validates limit for endpoints needing more items."""

def validated_skip(skip: int = Query(0, ge=0, le=100000)) -> int:
    """Validates skip parameter for pagination."""

def calculate_pagination_params(page: int, limit: int) -> tuple[int, int]:
    """Calculate skip and limit values. Returns (skip, limit)."""
```

### String/Filter Functions

```python
def validated_string_filter(
    value: Optional[str],
    max_length: int = 100,
    allow_regex: bool = False
) -> Optional[str]:
    """
    Validates and sanitizes string filters.
    Removes dangerous regex characters by default.
    Returns None if invalid.
    """

def validated_date_string(date_str: Optional[str]) -> Optional[str]:
    """Validates ISO 8601 date format. Returns None if invalid."""

def validate_sort_field(
    sort: str,
    allowed_fields: Optional[List[str]] = None,
    default_field: str = "created_at"
) -> str:
    """
    Validates sort field against allowlist.
    Supports ascending/descending with - prefix.
    Returns default_field if invalid.
    """

def validated_sort_direction(direction: str) -> int:
    """
    Converts sort direction to MongoDB format.
    Returns: 1 for ascending, -1 for descending
    """
```

### Enum/Type Functions

```python
def validated_enum_filter(value: Optional[str], allowed_values: List[str]) -> Optional[str]:
    """Validates enum value against allowed list. Returns None if invalid."""

def validated_status_filter(status: Optional[str], allowed_statuses: List[str]) -> Optional[str]:
    """Validates status against allowlist. Returns None if invalid."""

def validated_boolean_filter(value: Optional[bool]) -> Optional[bool]:
    """Validates and returns boolean value."""
```

## Common Allowed Values (Copy-Paste)

### Status Fields

```python
# Ticket/Support status
['open', 'in_progress', 'resolved', 'closed']

# Task status
['pending', 'in_progress', 'completed', 'on_hold']

# Contract status
['draft', 'sent', 'viewed', 'signed', 'active', 'completed', 'cancelled']

# General binary
['active', 'inactive']
```

### Priority Fields

```python
['low', 'medium', 'high', 'urgent']
```

### Export/Format Fields

```python
['json', 'csv']
```

### Direction Fields

```python
['asc', 'desc', 'next', 'prev']
```

### Category Fields (Wedding)

```python
['traditional', 'modern', 'intimate']
```

## Anti-Patterns (What NOT to do)

```python
# ❌ BAD: Direct user input to MongoDB
status = request.query_params.get("status")
query['status'] = status  # DANGER!

# ❌ BAD: Using regex without validation
search = request.query_params.get("search")
query['$text'] = {'$search': search}  # DANGER!

# ❌ BAD: No length limits
name = request.query_params.get("name")
# Could be millions of characters!

# ❌ BAD: Trust user for enum
direction = request.query_params.get("direction")
cursor.sort("field", direction)  # DANGER! Could be "1)" etc
```

## Correct Patterns

```python
# ✅ GOOD: Validate all inputs
status = validated_status_filter(status, ['open', 'in_progress'])
if status:
    query['status'] = status

# ✅ GOOD: Validate and sanitize strings
search = validated_string_filter(search, max_length=100)
if search:
    query['$text'] = {'$search': search}

# ✅ GOOD: Enforce bounds
limit = Query(50, ge=1, le=100)

# ✅ GOOD: Use enum validation
direction = validated_enum_filter(direction, ['asc', 'desc'])
sort_dir = 1 if direction == 'asc' else -1
cursor.sort("field", sort_dir)
```

## Testing Injection Patterns

When testing, try these injection patterns:

```bash
# Regex injection
?status={"$ne": null}
?status={$ne:null}
?status=$ne

# SQL injection
?name='; DROP TABLE--
?name=admin'--

# Path traversal
?file=../../etc/passwd

# Command injection
?query=`whoami`
?query=$(whoami)

# Large values
?limit=999999999
?page=9999999999

# Invalid types
?count=abc
?active=maybe
```

All should be safely rejected or sanitized by validation functions.
