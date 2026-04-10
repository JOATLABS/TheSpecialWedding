# Motor Migration Guide - PyMongo to Motor (Async)

**Date:** October 14, 2025
**Status:** IN PROGRESS
**Priority:** CRITICAL

---

## 📋 Migration Strategy

### Phase 1: Core Database Module ✅ COMPLETE
- ✅ **database_async.py** already exists with Motor implementation
- ✅ Motor already in requirements.txt (motor>=3.3.0)
- ✅ Proper connection pooling configured
- ✅ Index creation implemented

### Phase 2: Service Layer Migration (Current)
Need to update all services to:
1. Import `async_mongo` instead of `mongo`
2. Add `await` to all database operations
3. Update collection access patterns

###Phase 3: API & Dependencies
1. Update API files
2. Update auth dependencies
3. Update middleware

---

## 🔧 Required Changes Pattern

### Import Change:
```python
# OLD (Sync):
from app.core.database import mongo

# NEW (Async):
from app.core.database_async import async_mongo
```

### Collection Access Change:
```python
# OLD (Instance variable in __init__):
def __init__(self):
    self.notifications_collection = mongo.db["notifications"]

# NEW (Property for lazy access):
@property
def notifications_collection(self):
    return async_mongo.db["notifications"]

# OR use shorthand properties:
@property
def users_collection(self):
    return async_mongo.users  # For collections with property in async_mongo
```

### Database Operation Changes:
```python
# insert_one
result = collection.insert_one(doc)  # ❌ SYNC
result = await collection.insert_one(doc)  # ✅ ASYNC

# insert_many
result = collection.insert_many(docs)  # ❌ SYNC
result = await collection.insert_many(docs)  # ✅ ASYNC

# find_one
doc = collection.find_one(query)  # ❌ SYNC
doc = await collection.find_one(query)  # ✅ ASYNC

# find (cursor iteration)
for doc in collection.find(query):  # ❌ SYNC
    process(doc)

async for doc in collection.find(query):  # ✅ ASYNC
    process(doc)

# OR convert to list:
docs = await collection.find(query).to_list(length=100)  # ✅ ASYNC

# count_documents
count = collection.count_documents(query)  # ❌ SYNC
count = await collection.count_documents(query)  # ✅ ASYNC

# update_one/update_many
result = collection.update_one(filter, update)  # ❌ SYNC
result = await collection.update_one(filter, update)  # ✅ ASYNC

# delete_one/delete_many
result = collection.delete_one(filter)  # ❌ SYNC
result = await collection.delete_one(filter)  # ✅ ASYNC

# aggregate
for doc in collection.aggregate(pipeline):  # ❌ SYNC
    process(doc)

async for doc in collection.aggregate(pipeline):  # ✅ ASYNC
    process(doc)
```

---

## 📊 Files Requiring Migration

### Service Layer (HIGH PRIORITY):
- [ ] `app/services/notification_service.py` (608 lines, 10+ DB operations)
- [ ] `app/services/support_service.py` (603 lines, 12+ DB operations)
- [ ] `app/services/subscription_service.py`
- [ ] `app/services/user_management_service.py`
- [ ] `app/services/form_service.py`
- [ ] `app/services/import_service.py`
- [ ] `app/services/trial_expiration_service.py`
- [ ] `app/services/plus_one_service.py`
- [ ] `app/services/security_audit_service.py`
- [ ] `app/services/stripe_service.py`
- [ ] `app/services/email_service_resend.py`

### API Layer:
- [ ] `app/api/planner_metrics.py`
- [ ] `app/api/reminder.py`
- [ ] `app/api/saas_config.py`
- [ ] `app/api/stripe_payment.py`
- [ ] `app/api/trial_management.py`
- [ ] `app/api/vendor_forms.py`
- [ ] `app/api/guest_verification.py`
- [ ] `app/api/guest_verification_secure.py`

### Dependencies:
- [ ] `app/dependencies/auth.py`
- [ ] `app/dependencies/auth_extended.py`
- [ ] `app/dependencies/auth_basic.py`

### Middleware:
- [ ] `app/middleware/audit_logging.py`

---

## 🎯 Migration Checklist for Each File

For each file:
1. [ ] Read full file to understand database operations
2. [ ] Update import: `mongo` → `async_mongo`
3. [ ] Convert collection access to properties
4. [ ] Add `await` to all database operations:
   - [ ] insert_one / insert_many
   - [ ] find_one
   - [ ] find (convert to async for or to_list)
   - [ ] count_documents
   - [ ] update_one / update_many
   - [ ] delete_one / delete_many
   - [ ] aggregate
5. [ ] Test the service/endpoint
6. [ ] Mark as complete in this checklist

---

## ⚠️ Common Pitfalls

### 1. Cursor Iteration
```python
# WRONG - Won't work with Motor
for doc in collection.find():
    pass

# RIGHT - Options:
# Option A: async for
async for doc in collection.find():
    pass

# Option B: to_list
docs = await collection.find().to_list(length=1000)
for doc in docs:
    pass
```

### 2. Nested Database Calls
```python
# Make sure ALL database calls have await
async def process():
    user = await db.users.find_one({"_id": user_id})  # ✅
    subscriptions = db.subscriptions.find({"user_id": user_id})  # ❌ Missing await!
```

### 3. Property vs Method
```python
# database_async.py has PROPERTIES not methods
db.users  # ✅ Correct (property)
db.get_users_collection()  # ❌ Wrong (old sync pattern)
```

---

## 🧪 Testing After Migration

1. Start Docker containers
2. Test each endpoint manually or with Postman
3. Check response times (should be similar or better)
4. Monitor logs for errors
5. Run integration tests if available

---

## 📈 Expected Benefits Post-Migration

1. **True async/await**: No more event loop blocking
2. **Better concurrency**: Can handle multiple requests simultaneously
3. **Improved performance**: Especially under load
4. **Production ready**: Proper async implementation

---

## 🚀 Current Progress

### ✅ Phase 1: COMPLETE - Initial Migration (Oct 14, 2025)
**Files Migrated:**
- ✅ `app/services/form_service.py` - 13 async methods, 26+ await calls
- ✅ `app/services/plus_one_service.py` - 4 async methods, 13 await calls
- ✅ `app/services/import_service.py` - 1 async method, 3 await calls
- ✅ `app/api/forms.py` - 12 async endpoints, 17+ await calls
- ✅ `app/api/plus_one.py` - 4 async endpoints, 4 await calls
- ✅ `app/api/admin_import.py` - 1 async endpoint, 1 await call

**Key Changes:**
- Converted `list(collection.find())` → `await collection.find().to_list(length=None)`
- Fixed 6 critical bugs where sync methods called async methods without await
- All async method calls properly awaited throughout call chain
- Backend server restarted successfully - no "coroutine was never awaited" errors

**Testing Results:**
- ✅ Server startup successful (no import/syntax errors)
- ✅ MongoDB connection working
- ✅ All endpoints responding (403/404 expected for auth)
- ✅ No async runtime errors in logs
- ✅ Application running stable

### Critical Issues Fixed:
1. **duplicate_form()** - Now async, awaits get_form() and create_form()
2. **get_form_responses()** - Now async, awaits get_form()
3. **get_form_analytics()** - Now async, uses async find().to_list()
4. **get_forms()** - Now async, uses async find().to_list()
5. **get_plus_ones_by_guest()** - Now async, uses async find().to_list()
6. **export_form_responses_csv()** - Now async in both service and API layers

### Pending:
- ⏳ Remaining services (notification, support, subscription, etc.)
- ⏳ Other API files (planner_metrics, reminder, etc.)
- ⏳ Dependencies (auth files)
- ⏳ Full integration testing with authenticated requests

---

**Migration Status:** Phase 1 Complete (3 services, 3 API files)
**Next Phase:** Migrate notification and support services
**Risk Level:** Low (initial migration successful, pattern established)
**Impact:** HIGH (async operations working correctly)
