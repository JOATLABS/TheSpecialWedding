# WeddingApp Deployment Checklist

Use this checklist to ensure you don't miss any steps during deployment.

## 📋 Pre-Deployment Checklist

### VPS Preparation
- [ ] VPS/Droplet created (min 2GB RAM, 2 CPU cores)
- [ ] Ubuntu 20.04+ or Debian 11+ installed
- [ ] SSH access verified
- [ ] Static IP address assigned
- [ ] (Optional) Domain name configured and DNS pointing to VPS

### Local Repository
- [ ] All code committed to GitHub
- [ ] Code on correct branch (`main` or `production`)
- [ ] `.env` files NOT committed (check `.gitignore`)
- [ ] `requirements.txt` up to date

## 🔧 VPS Setup Checklist

### System Updates
- [ ] Run `sudo apt update && sudo apt upgrade -y`
- [ ] Reboot if kernel updated

### Docker Installation
- [ ] Docker installed: `curl -fsSL https://get.docker.com | sh`
- [ ] Docker Compose installed: `sudo apt install docker-compose-plugin -y`
- [ ] User added to docker group: `sudo usermod -aG docker $USER`
- [ ] Logged out and back in (or `newgrp docker`)
- [ ] Verified: `docker --version && docker compose version`

### Application Directory
- [ ] Created: `sudo mkdir -p /opt/weddingapp`
- [ ] Ownership set: `sudo chown $USER:$USER /opt/weddingapp`
- [ ] Repository cloned: `git clone https://github.com/YOUR_USERNAME/WeddingWebApp.git /opt/weddingapp`
- [ ] Correct branch checked out: `cd /opt/weddingapp && git checkout main`

### SSH Key Setup
- [ ] Key generated: `ssh-keygen -t ed25519 -f ~/.ssh/github_actions -N ""`
- [ ] Public key added: `cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys`
- [ ] Private key copied (for GitHub secrets)
- [ ] Permissions correct: `chmod 600 ~/.ssh/github_actions`

### Firewall (Optional but Recommended)
- [ ] UFW installed: `sudo apt install ufw -y`
- [ ] SSH allowed: `sudo ufw allow 22/tcp`
- [ ] HTTP allowed: `sudo ufw allow 80/tcp`
- [ ] HTTPS allowed: `sudo ufw allow 443/tcp`
- [ ] Firewall enabled: `sudo ufw enable`
- [ ] Status checked: `sudo ufw status`

## 🔐 GitHub Configuration Checklist

### Repository Settings
- [ ] Go to: Settings → Secrets and variables → Actions

### Essential Secrets (Required)
- [ ] `VPS_HOST` - VPS IP address
- [ ] `VPS_USER` - SSH username (e.g., `ubuntu`, `root`)
- [ ] `VPS_SSH_KEY` - Private SSH key (entire content including headers)
- [ ] `VPS_PORT` - SSH port (default: `22`)
- [ ] `MONGO_ROOT_PASSWORD` - Strong random password (20+ chars)
- [ ] `MONGO_DB` - Database name (default: `wedding`)
- [ ] `SECRET_KEY` - JWT secret (32+ chars, random)
- [ ] `ROOT_ADMIN_EMAIL` - Admin email address
- [ ] `ROOT_ADMIN_PASSWORD` - Strong admin password (20+ chars)
- [ ] `API_URL` - Public API URL (e.g., `http://YOUR_IP:8000` or `https://api.yourdomain.com`)
- [ ] `CORS_ORIGINS` - Frontend URLs (comma-separated, e.g., `https://yourdomain.com,https://www.yourdomain.com`)

### Email Service Secrets (Resend)
- [ ] `RESEND_API_KEY` - Resend API key
- [ ] `RESEND_FROM_EMAIL` - Verified sender email
- [ ] `RESEND_FROM_NAME` - Customer-visible sender name used by storefront inquiry and DNS-instruction mail

### SMS Service Secrets (Choose One)
**Twilio:**
- [ ] `SMS_PROVIDER=twilio`
- [ ] `TWILIO_ACCOUNT_SID`
- [ ] `TWILIO_AUTH_TOKEN`
- [ ] `TWILIO_PHONE_NUMBER`

**OR Telnyx:**
- [ ] `SMS_PROVIDER=telnyx`
- [ ] `TELNYX_API_KEY`
- [ ] `TELNYX_PUBLIC_KEY`
- [ ] `TELNYX_PHONE_NUMBER`

### Storage Secrets (Cloudflare R2 or AWS S3)
- [ ] `S3_ENDPOINT_URL` - R2/S3 endpoint
- [ ] `S3_REGION=auto` for Cloudflare R2
- [ ] `S3_ACCESS_KEY_ID` - Access key
- [ ] `S3_SECRET_ACCESS_KEY` - Secret key
- [ ] `S3_BUCKET_NAME` - Primary gallery/profile/document bucket
- [ ] `MEDIA_DOMAIN` - Public CDN URL for the primary media bucket
- [ ] `S3_GUEST_MEDIA_BUCKET_NAME` - Guest memories bucket when guest uploads are enabled
- [ ] `GUEST_MEDIA_DOMAIN` - Public CDN URL for guest media assets if guest media is served through a dedicated domain
- [ ] `S3_AD_BUCKET_NAME` - Dedicated ad-assets bucket when vendor ads/logo storage is enabled
- [ ] `AD_MEDIA_DOMAIN` - Public CDN URL for ad assets
- [ ] `S3_BLOG_BUCKET_NAME` - Dedicated blog/knowledge-base bucket when blog image uploads are enabled
- [ ] `BLOG_MEDIA_DOMAIN` - Public CDN URL for blog assets

### Planner Storefront Infrastructure

- [ ] Complete [`docs/guides/STOREFRONT_INFRASTRUCTURE_SETUP.md`](../guides/STOREFRONT_INFRASTRUCTURE_SETUP.md)
- [ ] `S3_STOREFRONT_STAGING_BUCKET_NAME` points to a dedicated private bucket
- [ ] Staging-bucket `r2.dev` access is disabled and no enabled custom domain is attached
- [ ] An enabled deletion lifecycle covers `storefront/` within `STOREFRONT_STAGING_LIFECYCLE_MAX_AGE_DAYS`
- [ ] Staging-bucket CORS allows browser `PUT` with `Content-Type` from the exact frontend origin
- [ ] `CLOUDFLARE_ACCOUNT_ID` matches the account in `S3_ENDPOINT_URL`
- [ ] `CLOUDFLARE_API_TOKEN` is limited to the R2 control-plane reads required by the privacy doctor
- [ ] `CLOUDFLARE_SAAS_API_TOKEN` is a separate token scoped only to the SaaS zone with `Zone Read` and `SSL and Certificates Write`; it is never the R2 token
- [ ] `CLOUDFLARE_ZONE_ID` is the exact Cloudflare for SaaS zone
- [ ] `STOREFRONT_FALLBACK_ORIGIN` is configured as the active fallback origin
- [ ] `STOREFRONT_CNAME_TARGET` is the active Cloudflare-for-SaaS CNAME target
- [ ] `STOREFRONT_PLATFORM_DOMAINS` is identical on frontend and backend
- [ ] `STOREFRONT_RUNTIME_REVISION` is the immutable deployed Git SHA or image digest, not `unknown`
- [ ] `STOREFRONT_CUSTOM_DOMAINS_ENABLED=false` for the initial read-only deploy
- [ ] `STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED=false` for the initial read-only deploy
- [ ] `STOREFRONT_DOMAIN_CONNECT_DISCOVERY_ENABLED=false` and `STOREFRONT_DOMAIN_CONNECT_AUTHORIZATION_ENABLED=false` until external onboarding receipts exist
- [ ] `STOREFRONT_CUSTOM_DOMAIN_ROLLOUT_MODE=allowlist` with exact `STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES` and/or `STOREFRONT_CUSTOM_DOMAIN_PILOT_OWNER_IDS` before any pilot provisioning
- [ ] `STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED=true` before the first provider create and throughout rollback/cleanup
- [ ] `DOMAIN_CONNECT_PROVIDER_ID`, `DOMAIN_CONNECT_SERVICE_ID`, and `DOMAIN_CONNECT_TEMPLATE_VERSION` match the accepted template exactly
- [ ] `DOMAIN_CONNECT_PRIVATE_KEY` is backend-only; `DOMAIN_CONNECT_KEY_ID`, `DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN`, and `DOMAIN_CONNECT_CALLBACK_URL` match published DNS and the exact HTTPS callback
- [ ] Production Compose plus focused storefront configuration/template checks pass without printing secrets
- [ ] Current-source deterministic storefront Playwright run has a passing cleanup and source-bound manifest
- [ ] Separate visible playback is approved in the user-selected in-app Chrome browser
- [ ] Same-zone canary and independently authoritative customer-zone receipts are tracked separately; external provider remains `BLOCKED` until the latter passes

### Payment Secrets (Stripe)
- [ ] `STRIPE_SECRET_KEY` - Stripe secret key
- [ ] `STRIPE_WEBHOOK_SECRET` - Webhook signing secret
- [ ] `STRIPE_PUBLISHABLE_KEY` - Publishable key

### GitHub Variables
- [ ] Go to: Settings → Secrets and variables → Actions → Variables tab
- [ ] Add: `DEPLOYMENT_TARGET` with value `VPS`

## 🚀 Deployment Checklist

### Pre-Deployment Verification
- [ ] All GitHub secrets added
- [ ] GitHub variables configured
- [ ] VPS accessible via SSH
- [ ] Git repository accessible from VPS: `cd /opt/weddingapp && git pull`

### Trigger Deployment
Choose one method:

**Method A: Push to Branch**
- [ ] Commit all changes
- [ ] Push to `main` or `production` branch
- [ ] GitHub Actions workflow starts automatically

**Method B: Manual Trigger**
- [ ] Go to GitHub → Actions tab
- [ ] Select "Deploy WeddingApp Backend"
- [ ] Click "Run workflow"
- [ ] Select branch
- [ ] Click green "Run workflow" button

### Monitor Deployment
- [ ] Watch GitHub Actions progress
- [ ] Build job completed successfully
- [ ] Deploy job completed successfully
- [ ] Database setup job completed
- [ ] Health check job passed

## ✅ Post-Deployment Verification

### SSH into VPS
```bash
ssh your_user@your_vps_ip
cd /opt/weddingapp
```

### Check Container Status
- [ ] All containers running: `docker compose -f docker-compose.production.yml ps`
- [ ] Expected containers: `api` (×2), `mongo`, `redis`, `nginx`
- [ ] All show "Up" status
- [ ] Health checks passing (healthy)

### Test API Locally on VPS
- [ ] Health endpoint: `curl http://localhost:8000/health/`
- [ ] Should return `{"status":"healthy"}`

### Test API Publicly
- [ ] Health endpoint: `curl http://YOUR_VPS_IP:8000/health/`
- [ ] OR with domain: `curl https://api.yourdomain.com/health/`
- [ ] Should return `{"status":"healthy"}`

### Check Logs
- [ ] No error messages: `docker compose -f docker-compose.production.yml logs`
- [ ] API logs look normal: `docker compose -f docker-compose.production.yml logs api`
- [ ] MongoDB connected: `docker compose -f docker-compose.production.yml logs mongo | grep "Waiting for connections"`
- [ ] Redis connected: `docker compose -f docker-compose.production.yml logs redis | grep "Ready to accept connections"`

### Verify Admin User
- [ ] Test admin login via API:
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"YOUR_ROOT_ADMIN_EMAIL","password":"YOUR_ROOT_ADMIN_PASSWORD"}'
```
- [ ] Should return JWT token

### Database Verification
- [ ] Connect to MongoDB:
```bash
docker compose -f docker-compose.production.yml exec mongo mongosh -u admin -p YOUR_MONGO_PASSWORD --authenticationDatabase admin
```
- [ ] Check database exists: `show dbs`
- [ ] Should see `wedding` database
- [ ] Check collections: `use wedding` then `show collections`
- [ ] Verify admin user: `db.users.findOne({"email":"YOUR_ROOT_ADMIN_EMAIL"})`

## 🌐 Frontend Integration Checklist

### Update Frontend Environment
- [ ] Frontend `.env` updated with API URL:
  ```bash
  NEXT_PUBLIC_API_URL=http://YOUR_VPS_IP:8000
  # OR
  NEXT_PUBLIC_API_URL=https://api.yourdomain.com
  ```
- [ ] Frontend deployed/restarted
- [ ] CORS origins include frontend URL (check GitHub secrets)

### Test Frontend-Backend Connection
- [ ] Frontend can reach API
- [ ] Login functionality works
- [ ] API requests successful
- [ ] No CORS errors in browser console

## 🛡️ Security Checklist

### SSL/TLS (If using domain)
- [ ] Nginx installed on host
- [ ] Certbot installed
- [ ] SSL certificate obtained
- [ ] Auto-renewal configured
- [ ] HTTPS working: `https://api.yourdomain.com/health/`
- [ ] HTTP redirects to HTTPS

### Security Headers
- [ ] CSP headers present (check API response headers)
- [ ] CORS properly configured
- [ ] Rate limiting enabled

### Firewall
- [ ] Only necessary ports open (22, 80, 443)
- [ ] MongoDB port NOT exposed (27017 should be internal only)
- [ ] Redis port NOT exposed (6379 should be internal only)

### Secrets Management
- [ ] No secrets in code
- [ ] No secrets in git history
- [ ] `.env` file NOT in repository
- [ ] GitHub secrets properly configured

## 📊 Monitoring Setup (Optional)

### Log Rotation
- [ ] Docker logs configured with max size/files
- [ ] Host logs rotated
- [ ] Old logs cleaned up regularly

### Uptime Monitoring
- [ ] Uptime monitoring service configured (UptimeRobot, etc.)
- [ ] Health endpoint monitored: `/health/`
- [ ] Alerts configured for downtime

### Backup Strategy
- [ ] Database backup script created
- [ ] Backup schedule configured
- [ ] Backup restoration tested
- [ ] Off-site backup storage configured

## 🔄 Ongoing Maintenance Checklist

### Weekly
- [ ] Check container status
- [ ] Review logs for errors
- [ ] Monitor resource usage (CPU, RAM, disk)

### Monthly
- [ ] Update system packages: `sudo apt update && sudo apt upgrade -y`
- [ ] Pull latest Docker images: `docker compose -f docker-compose.production.yml pull`
- [ ] Review and clean old Docker images: `docker image prune -a`
- [ ] Test database backup restoration

### After Each Deployment
- [ ] Verify health checks pass
- [ ] Test critical functionality
- [ ] Review deployment logs
- [ ] Monitor for errors in first 24 hours

## 📞 Emergency Contacts

Document your emergency contacts:

- **VPS Provider Support**: _________________
- **DNS Provider Support**: _________________
- **Domain Registrar**: _________________
- **Backup Location**: _________________
- **Team Members**:
  - _________________
  - _________________

## 📝 Notes Section

Use this space for deployment-specific notes:

```
Date: _______________
VPS IP: _______________
Domain: _______________
Notes:
_____________________
_____________________
_____________________
```

---

**Status Legend:**
- ✅ Done
- ⏳ In Progress
- ❌ Not Done
- ⚠️ Issue/Blocker
- 🔄 Needs Retry

**Completion Date:** _______________
**Deployed By:** _______________
**Sign-off:** _______________
