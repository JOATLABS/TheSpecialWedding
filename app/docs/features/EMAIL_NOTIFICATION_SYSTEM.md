# Email Notification System (Current Capabilities)

## Overview

The Wedding Web Application includes a basic notification service for storing announcements in MongoDB. Automatic email delivery to administrators is still a future enhancement—the Celery/Redis architecture described in earlier drafts has not been implemented.

## Architecture

### Components in the repository

1. **NotificationService** (`app/services/notification_service.py`)
   - Creates, updates, and deletes in-app notifications stored in MongoDB
   - `send_notification` currently marks records as "sent" without dispatching emails

2. **Email utilities**
   - `ResendEmailService` provides synchronous sending helpers for other flows
   - No queueing layer or worker process exists

## Features

### Automatic Email Triggers

Automatic triggers are **not** enabled. Notifications created with `target_audience: "root_admin"` remain in the database until polled by the UI.

### Email Templates

Email templates for admin alerts have not been developed. The system currently relies on the existing Resend transactional templates used elsewhere in the app.

### Retry Logic

There is no background worker or retry queue yet. Any resilience requirements should be addressed when the queueing layer is introduced.

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

`celery` and `redis` are **not** present in `requirements.txt`. Add them when the queue-backed implementation begins.

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

_Not applicable._ There is no Celery configuration or worker entrypoint.

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

Emails are **not** sent automatically today. Creating a notification stores it for in-app display only.

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

No automatic integrations are active yet. Planned triggers include:

- **Contact Form API** (`app/api/public_endpoints.py`) – send alert when a new inquiry arrives
- **User Registration** – notify admins about new planners and trial expirations
- **Payment Processing** – surface billing failures
- **Error Handling** – dispatch critical system alerts
- **Admin Dashboard** – manage notification templates and delivery preferences

These items should be revisited once the queue-backed delivery system is in place.