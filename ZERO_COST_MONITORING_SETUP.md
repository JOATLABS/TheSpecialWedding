# Zero-Cost Monitoring & Operations Setup

**Complete self-hosted monitoring solution using services you already have!**

No Sentry, no Datadog, no New Relic - just smart use of free tiers and self-built dashboards.

---

## 🎯 What You Get

✅ **Error Tracking** - Self-hosted alternative to Sentry
✅ **Platform Metrics** - Business & technical KPIs
✅ **Automated Backups** - Daily MongoDB backups to Cloudflare R2
✅ **Email Alerts** - Critical errors & downtime notifications
✅ **Uptime Monitoring** - 5-minute health checks
✅ **Performance Monitoring** - Slow endpoint detection
✅ **Historical Trending** - Charts & analytics

**Total Monthly Cost: $0** 🎉

---

## 📦 What's Included

### Backend (FastAPI)
- `app/api/admin_platform_metrics.py` - Metrics API endpoint
- `app/api/admin_backup.py` - Backup trigger endpoint
- `app/middleware/error_handler.py` - MongoDB error logging + email alerts with secure responses
- `app/utils/migrations.py` - Async database migrations

### Frontend (Next.js)
- Will be created: `app/admin/dashboard/page.tsx` - ROOT_ADMIN monitoring dashboard
- Will be created: `app/admin/errors/[errorId]/page.tsx` - Error details page

### Cloudflare Workers (FREE)
- `cloudflare-workers/backup-cron.js` - Daily backups (2 AM UTC)
- `cloudflare-workers/metrics-snapshot-cron.js` - Hourly metrics snapshots

### Vercel Cron (FREE on Pro)
- `app/api/cron/uptime-check/route.ts` - Backend health checks (every 5 min)

---

## 🚀 Setup Instructions

### Step 1: Install Required Dependencies

```bash
# Backend dependencies
pip install psutil resend boto3

# psutil - System metrics (CPU, disk, memory)
# resend - Email alerts (you already use this!)
# boto3 - R2 uploads (you already use this for gallery!)
```

### Step 2: Update Environment Variables

Add to your `.env` file:

```bash
# Generate a secure backup secret
openssl rand -hex 32

# Add to .env
BACKUP_SECRET=<generated-secret-here>

# Email alerts (you already have these!)
RESEND_API_KEY=your_resend_key
ROOT_ADMIN_EMAIL=your@email.com

# R2 Storage (you already have these!)
S3_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
S3_BUCKET_NAME=wedding-gallery
S3_ACCESS_KEY_ID=your_key
S3_SECRET_ACCESS_KEY=your_secret
```

### Step 3: Deploy Cloudflare Workers

#### A. Daily Backup Worker

1. Go to **Cloudflare Dashboard** → **Workers & Pages**
2. Click **Create Application** → **Create Worker**
3. Name it: `wedding-backup-cron`
4. Paste code from `cloudflare-workers/backup-cron.js`
5. Click **Save and Deploy**
6. Go to **Settings** → **Triggers**
7. Add **Cron Trigger**: `0 2 * * *` (daily at 2 AM UTC)
8. Go to **Settings** → **Variables**
9. Add environment variables:
   - `API_URL` = `https://api.thespecialwedding.com`
   - `BACKUP_SECRET` = (your backup secret from .env)
   - `ALERT_EMAIL` = (your email for backup notifications)

#### B. Metrics Snapshot Worker (Optional)

1. Create another Worker: `wedding-metrics-snapshot`
2. Paste code from `cloudflare-workers/metrics-snapshot-cron.js`
3. Add Cron Trigger: `0 * * * *` (every hour)
4. Add environment variables:
   - `API_URL` = `https://api.thespecialwedding.com`
   - `ADMIN_TOKEN` = (get JWT token from logging into your admin panel)

**Note:** Admin token will expire after 60 minutes by default. For cron jobs, you may want to:
- Increase JWT expiration in settings.py, OR
- Use a long-lived service token, OR
- Manually update the token weekly

### Step 4: Deploy Vercel Cron

The uptime check cron is already configured in `vercel.json`. Just deploy:

```bash
git add .
git commit -m "Add zero-cost monitoring system"
git push

# Vercel will automatically detect and enable the cron job
```

Verify in **Vercel Dashboard** → **Your Project** → **Cron Jobs**

### Step 5: Test Everything

#### Test Error Tracking

```bash
# Trigger a test error to see email alerts
curl -X GET https://api.thespecialwedding.com/this-will-404

# Check MongoDB errors collection
mongo
use wedding
db.errors.find().limit(1).pretty()
```

#### Test Backup System

```bash
# Manually trigger a backup
curl -X POST https://api.thespecialwedding.com/admin/backup/trigger \
  -H "Authorization: Bearer YOUR_BACKUP_SECRET"

# Check backup history in dashboard
open https://admin.thespecialwedding.com/admin/platform/metrics
```

#### Test Metrics API

```bash
# Get current metrics (requires admin JWT token)
curl -X GET https://api.thespecialwedding.com/admin/platform/metrics \
  -H "Authorization: Bearer YOUR_ADMIN_JWT"
```

---

## 📊 ROOT_ADMIN Dashboard

Access your monitoring dashboard at:

**https://admin.thespecialwedding.com/admin/dashboard**

### Dashboard Features

1. **System Health**
   - Database status & latency
   - Disk usage
   - Memory usage
   - CPU usage

2. **Error Monitoring**
   - Total errors (24h)
   - Critical errors
   - Recent errors list
   - Error details with stack traces

3. **Business Metrics**
   - Total users
   - Active subscriptions
   - MRR/ARR
   - Trial conversion rate
   - Active weddings

4. **Performance**
   - Slow endpoints (>1s)
   - Request volume
   - Average response times

5. **Backup Status**
   - Last backup date/time
   - Backup file size
   - Backup history
   - Restore instructions

---

## 🔔 Alert Configuration

### Critical Error Alerts (via Resend)

Automatically sent when:
- 500 errors occur
- Database connection fails
- Payment/Stripe errors
- Authentication system errors

**You get:**
- Email with full stack trace
- Error ID for tracking
- Link to error details in dashboard
- Request context (IP, user agent, endpoint)

### Backup Alerts (via Cloudflare Workers)

Sent daily after backup:
- ✓ Success notification with file size
- ✗ Failure alert if backup fails

### Downtime Alerts (via Vercel Cron)

Sent when backend is down:
- Checks every 5 minutes
- Email alert with troubleshooting steps
- SSH commands to fix the issue

---

## 💰 Cost Breakdown

| Service | Free Tier | What You Use | Cost |
|---------|-----------|--------------|------|
| **Cloudflare Workers** | 100,000 req/day | 2 workers, ~50 req/day | **$0** |
| **Cloudflare R2** | 10 GB storage | ~2-5 GB for backups | **$0** |
| **Vercel Cron** | Included on Pro | 1 cron (288 req/day) | **$0** |
| **Resend** | 100 emails/day | ~5 alerts/day | **$0** |
| **MongoDB** | Self-hosted or Atlas Free (512MB) | < 512MB | **$0** |
| **Total** | | | **$0/month** |

---

## 📈 Scaling Considerations

### When You Outgrow Free Tiers

**Cloudflare Workers** ($5/month = 10M requests)
- You'll hit this at ~300,000 requests/day
- For reference: That's ~83 million users/month
- You'll be making money long before this!

**Resend** ($20/month = 50,000 emails)
- You'll hit 100 emails/day when you have ~20 critical errors/day
- If you're getting 20 critical errors/day, you have bigger problems! 😅

**R2 Storage** ($0.015/GB/month)
- 100 GB of backups = $1.50/month
- That's ~1 year of daily 300MB backups
- Old backups auto-delete after 30 days anyway

**You're good for YEARS before you need to pay anything.**

---

## 🛠️ Maintenance

### Weekly Tasks (5 minutes)
- [ ] Check dashboard for any critical errors
- [ ] Verify latest backup completed
- [ ] Review slow endpoints

### Monthly Tasks (15 minutes)
- [ ] Review error trends
- [ ] Check backup storage usage
- [ ] Update metrics snapshot worker token (if using)
- [ ] Review business metrics (MRR, conversions)

### Quarterly Tasks (30 minutes)
- [ ] Audit old errors (cleanup acknowledged errors)
- [ ] Review backup retention policy
- [ ] Check system resource trends
- [ ] Optimize slow endpoints

---

## 🔒 Security Notes

### Backup Secret
- Treat `BACKUP_SECRET` like a password
- Store in Cloudflare Workers environment variables (encrypted)
- Rotate every 90 days
- Never commit to git

### Admin JWT Token
- For metrics snapshot worker, use a long-lived token OR
- Increase JWT expiration for service accounts OR
- Manually refresh weekly (recommended for security)

### Error Data
- Error collection stores stack traces and request data
- Passwords/tokens are filtered out in middleware
- Set retention policy (auto-delete after 90 days)

---

## 📚 API Reference

### Platform Metrics

```bash
GET /admin/platform/metrics
Authorization: Bearer {admin_jwt}

Returns:
- health: {database, disk, memory, cpu}
- errors: {total_24h, critical_24h, recent_errors}
- business: {users, subscriptions, mrr, arr}
- performance: {slow_endpoints}
```

### Recent Errors

```bash
GET /admin/platform/errors/recent?limit=50
Authorization: Bearer {admin_jwt}

Query params:
- limit: 1-200 (default: 50)
- severity: all|critical|warning
- acknowledged: true|false
```

### Error Details

```bash
GET /admin/platform/errors/{error_id}
Authorization: Bearer {admin_jwt}

Returns full error with stack trace
```

### Backup History

```bash
GET /admin/backup/history?limit=30
Authorization: Bearer {admin_jwt}

Returns list of backups with status
```

### Trigger Manual Backup

```bash
POST /admin/backup/trigger
Authorization: Bearer {backup_secret}

Triggers immediate backup
```

---

## 🎨 Next Steps

Now that the backend is ready, let's build the frontend dashboard!

Continue to build:
1. ROOT_ADMIN Dashboard (`app/admin/dashboard/page.tsx`)
2. Error Details Page (`app/admin/errors/[errorId]/page.tsx`)
3. Backup Management Page (optional)
4. Metrics Charts (optional, using Chart.js)

---

## 🆘 Troubleshooting

### "Backup failed: mongodump command not found"

Install MongoDB tools on your VPS:

```bash
# Ubuntu/Debian
sudo apt-get install mongodb-database-tools

# Or via Docker
docker run -v /tmp:/backup mongo:5.0 mongodump --uri="..." --archive=/backup/dump.gz
```

### "psutil not installed"

```bash
pip install psutil
# Then restart your FastAPI app
```

### "Email alerts not sending"

Check Resend API key:

```bash
# Test Resend
curl -X POST https://api.resend.com/emails \
  -H "Authorization: Bearer YOUR_RESEND_KEY" \
  -H "Content-Type: application/json" \
  -d '{"from":"test@yourdomain.com","to":["your@email.com"],"subject":"Test","html":"Test"}'
```

### "Cloudflare Worker not triggering"

1. Check worker logs in Cloudflare Dashboard
2. Verify cron trigger is added
3. Test worker manually (click "Send Test Event")
4. Check environment variables are set

---

## 📞 Support

Questions? Issues?

1. Check error logs in dashboard
2. Review Cloudflare Worker logs
3. Check FastAPI logs: `docker-compose logs api --tail=100`
4. Verify all environment variables are set

---

**Built with ❤️ by a solo developer, for solo developers.**

No expensive SaaS subscriptions required! 🎉
