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

**Current Status**: Notifications page attempts to call these endpoints but they don't exist:

```python
# /app/api/notification_management.py (NEW FILE NEEDED)

@router.get("/admin/notification-templates", tags=["ROOT_ADMIN"])
def list_notification_templates(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """List all notification templates"""

@router.post("/admin/notification-templates", tags=["ROOT_ADMIN"])
def create_notification_template(template_data: NotificationTemplateModel, ...):
    """Create a new notification template"""

@router.put("/admin/notification-templates/{template_id}", tags=["ROOT_ADMIN"])
def update_notification_template(...):
    """Update notification template"""

@router.delete("/admin/notification-templates/{template_id}", tags=["ROOT_ADMIN"])
def delete_notification_template(...):
    """Delete notification template"""

@router.post("/admin/notifications/send", tags=["ROOT_ADMIN"])
def send_platform_notification(
    notification_data: {
        "subject": str,
        "content": str,
        "recipient_filter": str,
        "target_emails": List[str]
    },
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Send notification to multiple users based on filters"""
    # Should integrate with your existing email service (Resend API)

@router.get("/admin/notifications/history", tags=["ROOT_ADMIN"])
def get_notification_history(...):
    """Get history of sent notifications with delivery metrics"""
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
3. **Low Priority**: Notification System (nice to have for announcements)

## 📝 **Current Workarounds**

The root admin pages currently:
- ✅ Show real user and subscription data where available
- ✅ Display appropriate "no data" states when endpoints don't exist
- ✅ Provide user-friendly error messages
- ✅ Log warnings instead of errors for missing endpoints
- ✅ Calculate basic metrics from existing user data

This means the pages work now with real data where possible, and gracefully handle missing endpoints until they're implemented.