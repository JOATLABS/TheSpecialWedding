# Email Notification System

## Overview

The Wedding Web Application now includes a comprehensive email notification system that automatically sends emails to the root administrator (`thedeveloper@thespecialwedding.com`) when important platform events occur. The system uses Celery task queues with Redis as a broker to ensure reliable email delivery with retry logic.

## Architecture

### Components

1. **Celery Task Queue** (`app/core/celery_app.py`)
   - Redis broker configuration
   - Queue routing for emails and notifications
   - Retry policies and rate limiting

2. **Email Tasks** (`app/tasks/email_tasks.py`)
   - Asynchronous email sending with retry logic
   - Admin notification task for different event types
   - Failure tracking and logging

3. **Enhanced Services**
   - `ResendEmailService` - Added admin notification queuing
   - `NotificationService` - Auto-triggers emails for root_admin notifications

4. **Worker Process** (`celery_worker.py`)
   - Entry point for running Celery workers

## Features

### Automatic Email Triggers

The system automatically sends emails for:
- **Contact Form Submissions** - New inquiries from the SAAS landing page
- **New User Registrations** - Wedding planner account creation
- **Payment Events** - Subscription and billing notifications
- **System Alerts** - Error conditions and critical events

### Email Templates

All emails feature:
- **Professional HTML design** with JOAT Labs branding
- **Responsive layout** optimized for mobile and desktop
- **Rich metadata** including form data and admin panel links
- **Consistent styling** across all notification types

### Retry Logic

- **3 retry attempts** with exponential backoff
- **Maximum 10-minute delay** between retries
- **Failure logging** to MongoDB for manual review
- **Rate limiting** to respect email provider limits

## Configuration

### Environment Variables

Required in `.env`:

```bash
# Redis Configuration (Celery Broker)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Optional
REDIS_DB=0

# Email Configuration
RESEND_API_KEY=your_resend_api_key
RESEND_FROM_EMAIL=noreply@thespecialwedding.com
ROOT_ADMIN_EMAIL=thedeveloper@thespecialwedding.com

# Application URLs
FRONTEND_URL=https://www.thespecialwedding.com
```

### Dependencies

Added to `requirements.txt`:
```
celery[redis]>=5.3.0
redis>=5.0.0
```

## Setup and Deployment

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Start Redis Server

```bash
# Ubuntu/Debian
sudo systemctl start redis-server

# Or using Docker
docker run -d -p 6379:6379 redis:alpine
```

### 3. Start Celery Worker

```bash
# In the project root directory
celery -A celery_worker worker --loglevel=info
```

### 4. Production Deployment

For production, use a process manager like supervisord or systemd:

```ini
# /etc/supervisor/conf.d/celery-worker.conf
[program:celery-worker]
command=/path/to/venv/bin/celery -A celery_worker worker --loglevel=info
directory=/path/to/wedding-app
user=www-data
autostart=true
autorestart=true
```

## Usage

### Automatic Triggering

Emails are automatically sent when notifications are created with `target_audience: "root_admin"`:

```python
from app.services.notification_service import NotificationService

notification_service = NotificationService()
await notification_service.create_notification({
    "title": "New Contact Form Submission",
    "message": "A new inquiry has been received",
    "type": "info",
    "target_audience": "root_admin",
    "priority": "medium",
    "source": "contact_form",
    "is_dismissible": True,
    # Metadata for email template
    "name": "John Doe",
    "email": "john@example.com",
    "company": "Example Corp"
}, "system")
```

### Manual Email Sending

For custom admin notifications:

```python
from app.services.email_service_resend import ResendEmailService

email_service = ResendEmailService()
result = email_service.send_admin_notification(
    notification_type="system_alert",
    subject="Critical System Event",
    content="Description of the event",
    metadata={"additional": "data"}
)
```

## Email Templates

### Contact Form Template

- **Professional header** with gradient background
- **Contact details grid** with name, email, company, phone
- **Message display** with proper formatting
- **Admin panel link** for direct access
- **Response priority badge** indicating urgency

### New User Template

- **Welcome-style design** for new registrations
- **User details** including email, company, subscription plan
- **Quick access** to admin user management

### System Alert Template

- **Alert-focused design** with warning indicators
- **Event details** and timestamp information
- **Action buttons** for immediate response

## Monitoring and Logging

### Email Logs

All sent emails are logged to the `email_logs` collection:

```javascript
{
  "to": "thedeveloper@thespecialwedding.com",
  "subject": "New Contact Form Submission",
  "email_type": "admin_contact_form",
  "status": "success",
  "resend_id": "re_abc123",
  "sent_at": "2024-01-15T10:30:00Z"
}
```

### Failure Tracking

Failed emails after max retries are logged to `email_failures`:

```javascript
{
  "to_email": "thedeveloper@thespecialwedding.com",
  "subject": "Failed Email Subject",
  "status": "max_retries_exceeded",
  "retries": 3,
  "failed_at": "2024-01-15T10:35:00Z"
}
```

### Celery Monitoring

Monitor task queue status:

```bash
# Check active tasks
celery -A celery_worker inspect active

# Check worker status
celery -A celery_worker inspect stats

# Monitor failed tasks
celery -A celery_worker events
```

## Security Considerations

### Email Content

- **No sensitive data exposure** in email templates
- **Sanitized user input** to prevent XSS in emails
- **Rate limiting** to prevent email bombing
- **Secure token handling** for admin panel links

### Access Control

- **Root admin only** - emails sent exclusively to configured admin address
- **Authenticated links** - admin panel access requires login
- **Audit logging** - all email activities are logged

## Troubleshooting

### Common Issues

1. **Celery worker not processing tasks**
   - Check Redis connection
   - Verify worker is running: `ps aux | grep celery`
   - Check worker logs for errors

2. **Emails not being sent**
   - Verify `RESEND_API_KEY` is valid
   - Check Resend account status and limits
   - Review email logs in MongoDB

3. **Redis connection errors**
   - Ensure Redis server is running
   - Check Redis configuration in `.env`
   - Test connection: `redis-cli ping`

### Debug Mode

Enable verbose logging:

```bash
celery -A celery_worker worker --loglevel=debug
```

### Health Checks

Verify system components:

```bash
# Test Redis connection
python3 -c "import redis; r=redis.Redis(); print(r.ping())"

# Test Celery task creation
python3 -c "from app.tasks.email_tasks import send_admin_notification; print('Tasks imported successfully')"

# Test email service
python3 -c "from app.services.email_service_resend import ResendEmailService; print('Email service ready')"
```

## Performance Optimization

### Queue Management

- **Separate queues** for emails vs notifications
- **Rate limiting** to respect provider limits
- **Worker scaling** based on load

### Email Efficiency

- **Template caching** for repeated sends
- **Batch processing** for multiple notifications
- **Connection pooling** for Redis and MongoDB

## Future Enhancements

### Planned Features

1. **Email Templates Management** - Admin interface for customizing templates
2. **Delivery Tracking** - Open and click tracking for emails
3. **A/B Testing** - Template performance comparison
4. **Webhook Integration** - Real-time delivery status updates
5. **Multi-language Support** - Localized email templates

### Scalability Improvements

1. **Multiple Workers** - Horizontal scaling for high volume
2. **Priority Queues** - Critical vs normal priority handling
3. **Dead Letter Queues** - Advanced failure handling
4. **Metrics Dashboard** - Real-time monitoring interface

---

## Integration Points

This email system integrates with:

- **Contact Form API** (`app/api/public_endpoints.py`) - Automatic email on form submission
- **User Registration** - New account notifications
- **Payment Processing** - Billing event notifications
- **Error Handling** - System alert notifications
- **Admin Dashboard** - Notification management interface

The system is designed to be extensible and can easily accommodate new notification types and email templates as the platform grows.