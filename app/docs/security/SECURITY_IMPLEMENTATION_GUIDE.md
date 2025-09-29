# Security Implementation Guide
## Production Deployment of Security Fixes

This guide provides step-by-step instructions for deploying the comprehensive security fixes to production.

---

## Deployment Checklist

### Phase 1: Pre-Deployment Preparation

1. **Backup Current System**
 ```bash
 # Backup database
 mongodump --host localhost --port 27017 --db wedding_app --out backup_$(date +%Y%m%d)
 
 # Backup application files
 cp -r /path/to/WeddingWebApp /path/to/backup/WeddingWebApp_backup_$(date +%Y%m%d)
 ```

2. **Review Security Files**
 - [ ] `app/utils/security_validator.py` - Input validation and security controls
 - [ ] `app/utils/secure_error_handler.py` - Secure error handling
 - [ ] `app/services/guest_verification_service_secure.py` - Secure guest verification
 - [ ] `app/api/guest_verification_secure.py` - Secure API endpoints
 - [ ] `app/middleware/error_handler_secure.py` - Secure error middleware
 - [ ] `app/middleware/security_headers_enhanced.py` - Security headers
 - [ ] `app/utils/path_validator.py` - Path traversal prevention

### Phase 2: Environment Configuration

3. **Set Environment Variables**
 ```bash
 # Add to your environment configuration
 export DEBUG=false
 export SECURITY_LOGGING=true
 export CSRF_SECRET_KEY="$(openssl rand -base64 32)"
 export SECURITY_AUDIT_ENABLED=true
 export RATE_LIMIT_ENABLED=true
 export MAX_LOGIN_ATTEMPTS=5
 export LOCKOUT_DURATION=300
 ```

4. **Create Security Log Directory**
 ```bash
 mkdir -p /var/log/wedding_security
 chown wedding_app:wedding_app /var/log/wedding_security
 chmod 750 /var/log/wedding_security
 ```

### Phase 3: Database Security Setup

5. **Create Security Collections**
 ```javascript
 // Run in MongoDB shell
 use wedding_app;
 
 // Create security audit logs collection
 db.createCollection("security_audit_logs");
 db.security_audit_logs.createIndex({"timestamp": 1}, {"expireAfterSeconds": 2592000}); // 30 days
 db.security_audit_logs.createIndex({"client_ip": 1});
 db.security_audit_logs.createIndex({"event_type": 1});
 
 // Create access logs collection with indexes
 db.access_logs.createIndex({"wedding_id": 1});
 db.access_logs.createIndex({"timestamp": 1});
 db.access_logs.createIndex({"client_ip": 1});
 ```

### Phase 4: Application Updates

6. **Update Import Statements**
 
 **In `main_optimized.py` (or your main application file):**
 ```python
 # Add secure middleware imports
 from app.middleware.error_handler_secure import SecureErrorHandlerMiddleware
 from app.middleware.security_headers_enhanced import EnhancedSecurityHeadersMiddleware
 
 # Replace existing middleware
 app.add_middleware(SecureErrorHandlerMiddleware)
 app.add_middleware(EnhancedSecurityHeadersMiddleware, 
 hsts_max_age=31536000,
 enable_csp_reporting=True,
 debug_mode=os.getenv("DEBUG", "false").lower() == "true")
 ```

7. **Update Router Imports**
 
 **In your main router configuration:**
 ```python
 # Replace guest verification routes
 from app.api.guest_verification_secure import router as secure_guest_router
 
 # Add secure routes
 app.include_router(secure_guest_router, prefix="/api")
 ```

8. **Update Service Usage**
 
 **Replace existing guest verification service calls:**
 ```python
 # Replace this:
 from app.services.guest_verification_service import GuestVerificationService
 verification_service = GuestVerificationService()
 
 # With this:
 from app.services.guest_verification_service_secure import secure_guest_verification_service
 verification_service = secure_guest_verification_service
 ```

### Phase 5: Security Configuration

9. **Configure Logging**
 
 **Add to your logging configuration:**
 ```python
 import logging.config
 
 LOGGING_CONFIG = {
 'version': 1,
 'disable_existing_loggers': False,
 'formatters': {
 'security': {
 'format': '[{asctime}] {levelname} {name}: {message}',
 'style': '{',
 },
 },
 'handlers': {
 'security_file': {
 'level': 'INFO',
 'class': 'logging.handlers.RotatingFileHandler',
 'filename': '/var/log/wedding_security/security.log',
 'maxBytes': 10485760, # 10MB
 'backupCount': 5,
 'formatter': 'security',
 },
 'security_console': {
 'level': 'WARNING',
 'class': 'logging.StreamHandler',
 'formatter': 'security',
 },
 },
 'loggers': {
 'wedding_security': {
 'handlers': ['security_file', 'security_console'],
 'level': 'INFO',
 'propagate': False,
 },
 'wedding_security_verification': {
 'handlers': ['security_file', 'security_console'],
 'level': 'INFO',
 'propagate': False,
 },
 },
 }
 
 logging.config.dictConfig(LOGGING_CONFIG)
 ```

10. **Update CORS Configuration**
 ```python
 from fastapi.middleware.cors import CORSMiddleware
 
 # Update CORS with secure defaults
 app.add_middleware(
 CORSMiddleware,
 allow_origins=["https://yourdomain.com"], # Replace with your actual domain
 allow_credentials=True,
 allow_methods=["GET", "POST", "PUT", "DELETE"],
 allow_headers=["*"],
 expose_headers=["X-Request-ID", "X-Rate-Limit-Remaining"]
 )
 ```

---

## Testing Deployment

### 1. Run Security Tests

```bash
# Run the comprehensive penetration test
python security_penetration_test.py http://localhost:8002

# Expected output should show 95%+ security score
```

### 2. Test Key Security Features

**Test Input Validation:**
```bash
curl -X POST http://localhost:8002/weddings/verify-guest-access/test \
 -H "Content-Type: application/json" \
 -d '{"name": "../../etc/passwd"}'
# Should return 400 with sanitized error
```

**Test Rate Limiting:**
```bash
# Run multiple rapid requests
for i in {1..10}; do
 curl -X POST http://localhost:8002/weddings/verify-guest-access/test \
 -H "Content-Type: application/json" \
 -d '{"name": "test"}' &
done
wait
# Should start returning 429 after several attempts
```

**Test Security Headers:**
```bash
curl -I http://localhost:8002/
# Should include: X-Frame-Options, CSP, X-XSS-Protection, etc.
```

### 3. Monitor Security Logs

```bash
# Watch security logs in real-time
tail -f /var/log/wedding_security/security.log

# Check for security events
grep -i "security event" /var/log/wedding_security/security.log
```

---

## Configuration Options

### Security Validator Configuration

```python
# In app/utils/security_validator.py, adjust these settings:
class SecurityValidator:
 def __init__(self):
 self.max_attempts = 5 # Failed attempts before lockout
 self.lockout_duration = 300 # Lockout duration in seconds
 self.max_input_length = 1000 # Maximum input length
 self.progressive_delays = [1, 2, 4, 8, 16] # Progressive delay sequence
```

### Rate Limiting Configuration

```python
# Customize rate limits per endpoint
RATE_LIMITS = {
 "/weddings/verify-guest-access": {"requests": 10, "window": 60}, # 10 requests per minute
 "/admin/": {"requests": 100, "window": 60}, # 100 requests per minute for admin
 "default": {"requests": 60, "window": 60} # Default rate limit
}
```

### Security Headers Configuration

```python
# Customize CSP policy
CSP_POLICY = {
 "default-src": ["'self'"],
 "script-src": ["'self'", "'nonce-{nonce}'", "https://trusted-cdn.com"],
 "style-src": ["'self'", "'nonce-{nonce}'", "https://fonts.googleapis.com"],
 "img-src": ["'self'", "data:", "https:"],
 "connect-src": ["'self'", "https://api.yourdomain.com"],
}
```

---

## Monitoring and Maintenance

### 1. Security Metrics Dashboard

Monitor these key metrics:
- Failed authentication attempts per hour
- Rate limiting triggers per day 
- Injection attempt detections
- Error rates by endpoint
- Geographic distribution of failed attempts

### 2. Log Analysis

```bash
# Daily security report
grep "$(date +%Y-%m-%d)" /var/log/wedding_security/security.log | \
 grep -c "BLOCKED\|FAILED\|SUSPICIOUS"

# Top IPs with failed attempts 
grep "failed_attempt" /var/log/wedding_security/security.log | \
 grep "$(date +%Y-%m-%d)" | \
 awk '{print $8}' | sort | uniq -c | sort -nr | head -10
```

### 3. Automated Security Checks

```bash
#!/bin/bash
# security_health_check.sh

# Run daily security validation
python security_penetration_test.py http://localhost:8002 > security_check.log 2>&1

# Check for critical issues
if grep -q "CRITICAL" security_check.log; then
 echo "ALERT: Critical security issues detected" | mail -s "Security Alert" admin@yourdomain.com
fi

# Rotate security logs
logrotate -f /etc/logrotate.d/wedding_security
```

---

## Incident Response

### If Security Issues Are Detected:

1. **Immediate Response**
 ```bash
 # Block suspicious IP
 iptables -A INPUT -s SUSPICIOUS_IP -j DROP
 
 # Review recent logs
 grep -i "SUSPICIOUS_IP" /var/log/wedding_security/security.log
 ```

2. **Investigation**
 - Check security audit logs for the timeframe
 - Review database for any unauthorized changes
 - Verify integrity of critical data

3. **Recovery**
 - Apply any necessary security patches
 - Update rate limiting rules
 - Enhance monitoring for detected attack patterns

---

## Production Readiness Checklist

- [ ] All security files deployed
- [ ] Environment variables configured
- [ ] Database indexes created
- [ ] Logging configured and tested
- [ ] Security tests passing (95%+ score)
- [ ] Rate limiting working
- [ ] Error handling sanitized
- [ ] Security headers present
- [ ] Monitoring dashboard setup
- [ ] Incident response plan documented
- [ ] Team trained on security features

---

## Success Criteria

Your deployment is successful when:

1. **Security Test Score**: 95%+ on penetration tests
2. **No Information Disclosure**: Error messages contain no system details
3. **Rate Limiting Active**: Brute force attempts are blocked
4. **Headers Present**: All security headers in responses
5. **Logs Generated**: Security events are logged correctly
6. **Performance Maintained**: <5% performance overhead

---

## Support and Troubleshooting

### Common Issues:

**Issue**: Security middleware not loading
```python
# Solution: Check middleware order in main_optimized.py
# SecurityHeaders must be before ErrorHandler
app.add_middleware(EnhancedSecurityHeadersMiddleware)
app.add_middleware(SecureErrorHandlerMiddleware) 
```

**Issue**: Database connection errors in security logs
```bash
# Solution: Verify MongoDB connection and create indexes
mongo wedding_app --eval "db.security_audit_logs.createIndex({'timestamp': 1})"
```

**Issue**: Rate limiting too aggressive
```python
# Solution: Adjust limits in SecurityValidator
self.max_attempts = 10 # Increase from 5
self.lockout_duration = 180 # Reduce from 300
```

---

This implementation guide ensures a smooth deployment of all security fixes with comprehensive monitoring and maintenance procedures. The Wedding Application will be production-ready with enterprise-grade security upon successful completion of these steps.