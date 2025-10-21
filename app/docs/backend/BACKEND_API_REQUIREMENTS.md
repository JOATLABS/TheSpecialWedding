# Backend API Requirements for Root Admin Pages

The root admin pages have been updated to remove hardcoded data and use real API endpoints. However, several backend endpoints need to be implemented to fully support these features.

## ✅ **Already Implemented Endpoints**

These endpoints already exist and are being used:

- `GET /api/admin/users` - List all users (user_management.py)
- `GET /api/admin/users/{user_id}` - Get user details 
- `PUT /api/admin/users/{user_id}` - Update user details
- `DELETE /api/admin/users/{user_id}` - Delete user
- `GET /api/admin/subscription-plans` - List subscription plans (subscription_management.py)
- `POST /api/admin/subscription-plans` - Create subscription plan
- `PUT /api/admin/subscription-plans/{plan_id}` - Update subscription plan
- `DELETE /api/admin/subscription-plans/{plan_id}` - Delete subscription plan

## ❌ **Missing Endpoints That Need Implementation**

### 1. Platform Metrics Endpoints

**Current Status**: Platform Metrics page now calculates basic metrics from user data, but several endpoints would enhance functionality:

```python
# /app/api/admin_metrics.py (NEW FILE NEEDED)

@router.get("/admin/metrics", tags=["ROOT_ADMIN"])
def get_platform_metrics(
    timeframe: str = Query("30days", description="7days, 30days, 90days, 1year"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Get comprehensive platform metrics for root admin dashboard"""
    # Calculate real metrics from:
    # - User growth and activity
    # - Subscription revenue (MRR, ARR, churn)
    # - Wedding and form usage statistics
    # - Email/SMS communication stats
    # - System performance metrics

@router.get("/admin/analytics/revenue", tags=["ROOT_ADMIN"])
def get_revenue_analytics(...):
    """Detailed revenue breakdown with historical data"""

@router.get("/admin/analytics/usage", tags=["ROOT_ADMIN"]) 
def get_usage_analytics(...):
    """Platform usage statistics (weddings, forms, guests, etc.)"""
```

### 2. Notification System Endpoints

**Current Status**: ✅ **IMPLEMENTED** - Notification system is fully functional

The notification system is already implemented in `/app/api/notification_management.py` with the following endpoints:

```python
# /app/api/notification_management.py (EXISTING FILE)

@router.post("/admin/notifications", tags=["Notifications"])
def create_notification(notification_data: NotificationCreateModel, current_user: ExtendedAuthUser = Depends(require_root_admin))

@router.get("/admin/notifications", tags=["Notifications"])
def get_notifications(page: int = 1, limit: int = 20, filters..., current_user: ExtendedAuthUser = Depends(require_root_admin))

@router.get("/admin/notifications/{notification_id}", tags=["Notifications"])
def get_notification(notification_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin))

@router.put("/admin/notifications/{notification_id}", tags=["Notifications"])
def update_notification(notification_id: str, notification_data: NotificationUpdateModel, current_user: ExtendedAuthUser = Depends(require_root_admin))

@router.delete("/admin/notifications/{notification_id}", tags=["Notifications"])
def delete_notification(notification_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin))

@router.post("/admin/notifications/{notification_id}/send", tags=["Notifications"])
def send_notification(notification_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin))

# User notification endpoints
@router.get("/admin/user/notifications", tags=["User Notifications"])
def get_user_notifications(...)

@router.put("/admin/user/notifications/{notification_id}/read", tags=["User Notifications"])
def mark_notification_read(...)

@router.put("/admin/user/notifications/{notification_id}/dismiss", tags=["User Notifications"])
def dismiss_notification(...)

@router.get("/admin/user/notifications/count", tags=["User Notifications"])
def get_notification_count(...)
```

**Contact Form Integration**: ✅ **WORKING**
- Contact form submissions automatically create notifications in MongoDB
- Notifications appear in admin panel with proper field mapping
- Frontend successfully displays notification history

**Important Note: Email Notifications**
🚨 **The notification system currently stores notifications in MongoDB for in-app display only. NO emails are automatically sent to `thedeveloper@thespecialwedding.com` or any other email addresses when notifications are created.**

The `send_notification` function in `/app/services/notification_service.py` (lines 187-215) is currently a placeholder that only marks notifications as "sent" in the database. To enable actual email notifications, you would need to:
1. Integrate with the existing Resend email service
2. Modify the `send_notification` function to actually send emails
3. Add email templates for notifications
4. Configure which notification types should trigger emails

**Optional Template Endpoints** (Minor enhancement):
```python
# These endpoints are called by frontend but not critical for core functionality:
@router.get("/admin/notification-templates", tags=["ROOT_ADMIN"])
@router.post("/admin/notification-templates", tags=["ROOT_ADMIN"])
# Frontend gracefully handles 404s for these endpoints
```

### 3. Support System Endpoints

**Current Status**: Support page attempts to call these endpoints but they don't exist:

```python
# /app/api/support_management.py (NEW FILE NEEDED)

@router.get("/admin/support/tickets", tags=["ROOT_ADMIN"])
def list_support_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """List all support tickets with filtering"""

@router.get("/admin/support/tickets/{ticket_id}", tags=["ROOT_ADMIN"])
def get_support_ticket(ticket_id: str, ...):
    """Get support ticket details"""

@router.patch("/admin/support/tickets/{ticket_id}/status", tags=["ROOT_ADMIN"])
def update_ticket_status(ticket_id: str, status_data: {"status": str}, ...):
    """Update support ticket status"""

@router.post("/admin/support/tickets/{ticket_id}/respond", tags=["ROOT_ADMIN"])
def respond_to_ticket(ticket_id: str, response_data: {"message": str}, ...):
    """Send response to support ticket"""

@router.get("/admin/support/metrics", tags=["ROOT_ADMIN"])
def get_support_metrics(...):
    """Get support performance metrics"""

# Public endpoint for users to create support tickets
@router.post("/support/tickets", tags=["Support"])
def create_support_ticket(ticket_data: SupportTicketModel, ...):
    """Create a new support ticket (authenticated users)"""
```

## 📊 **Data Models Needed**

### Notification Models
```python
class NotificationTemplateModel(BaseModel):
    name: str
    subject: str
    content: str
    type: Literal['system_update', 'maintenance', 'security', 'marketing', 'feature_announcement']

class NotificationHistoryModel(BaseModel):
    template_name: str
    subject: str
    recipients_count: int
    sent_at: datetime
    delivery_status: Literal['sent', 'delivered', 'failed']
    open_rate: Optional[float]
    click_rate: Optional[float]
```

### Support Models
```python
class SupportTicketModel(BaseModel):
    user_id: str
    subject: str
    message: str
    category: Literal['technical', 'billing', 'feature_request', 'bug_report', 'general']
    priority: Literal['low', 'medium', 'high', 'urgent'] = 'medium'
    status: Literal['open', 'in_progress', 'resolved', 'closed'] = 'open'

class SupportResponseModel(BaseModel):
    ticket_id: str
    message: str
    responder_id: str
    is_internal: bool = False
```

## 🗄️ **Database Collections Needed**

### MongoDB Collections
1. **notification_templates** - Store reusable notification templates
2. **notification_history** - Track sent notifications and delivery metrics
3. **support_tickets** - Store support tickets and responses
4. **support_responses** - Store responses to support tickets
5. **platform_analytics** - Store aggregated metrics data (optional, for performance)

## 🔧 **Integration Points**

### Email Service Integration
The notification system should integrate with your existing Resend API service:
```python
# In notification_management.py
from app.services.email_service import EmailService  # Your existing service

async def send_bulk_notification(users: List[str], subject: str, content: str):
    email_service = EmailService()
    for user_email in users:
        await email_service.send_email(
            to=user_email,
            subject=subject,
            content=content
        )
```

### Activity Logging
Consider adding activity logging to track:
- User actions (for metrics)
- Email/SMS sending (for communication stats)
- Support ticket creation/updates
- Platform usage statistics

## 🚀 **Implementation Priority**

1. **High Priority**: Platform Metrics endpoints (users want to see real data immediately)
2. **Medium Priority**: Support System (important for customer service)
3. ~~**Low Priority**: Notification System~~ ✅ **COMPLETED** - Fully functional contact form → notification pipeline

## 📝 **Current Workarounds**

The root admin pages currently:
- ✅ Show real user and subscription data where available
- ✅ Display appropriate "no data" states when endpoints don't exist
- ✅ Provide user-friendly error messages
- ✅ Log warnings instead of errors for missing endpoints
- ✅ Calculate basic metrics from existing user data

This means the pages work now with real data where possible, and gracefully handle missing endpoints until they're implemented.