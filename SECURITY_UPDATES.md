# Security Updates

## Changes Made

### 1. Environment Configuration
- Created `.env.example` with placeholder values
- Removed `.env` from git tracking
- All sensitive data now in environment variables

### 2. JWT Authentication
- Created `app/dependencies/auth.py` with JWT middleware
- `get_current_user` dependency for authentication
- `require_admin` dependency for role-based access
- Role-based access control system

### 3. API Restructuring
- All admin endpoints now under `/admin` prefix
- Removed hardcoded API keys
- Consistent authentication across all admin endpoints

### 4. Updated Endpoints
- `/admin/token` - Login endpoint
- `/admin/rsvps` - Get all RSVPs (JWT protected)
- `/admin/rsvps/export` - Export RSVPs (JWT protected)
- `/admin/guests/import` - Import guests (JWT protected)

### 5. Admin GUI Updates
- Added login dialog
- Updated API client to use JWT tokens
- Removed hardcoded API keys

## Testing

Run the test script to verify authentication:
```bash
python scripts/test_auth.py
```

## Setup

1. Copy `.env.example` to `.env`
2. Update values in `.env`
3. Install dependencies: `pip install -r requirements.txt`
4. Create admin user: `python scripts/setup_admin_user.py --auto-create`
5. Start the server: `uvicorn app.main:app --reload`