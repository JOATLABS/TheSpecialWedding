# Backend Deployment Setup Guide

> Historical reference. This guide targets an older droplet-based backend deployment flow and is no longer the primary deployment path for this repo. Use [docs/plans/DEPLOYMENT_STRATEGY_STATUS.md](../plans/DEPLOYMENT_STRATEGY_STATUS.md) for the current recommendation.

## Overview

This guide explains how to set up automated deployment of the Wedding App backend to your DigitalOcean droplet using GitHub Actions.

## Prerequisites

1. **DigitalOcean Droplet** with:

   - Ubuntu 20.04+ or similar Linux distribution
   - Docker and Docker Compose installed
   - Git installed
   - SSH access configured
2. **GitHub Repository** with:

   - Your Wedding App code
   - GitHub Actions enabled

## Initial Server Setup

### 1. SSH into your droplet

```bash
ssh root@your-droplet-ip
```

### 2. Create deployment user (optional but recommended)

```bash
adduser deploy
usermod -aG docker deploy
usermod -aG sudo deploy
```

### 3. Set up project directory

```bash
mkdir -p /var/www/wedding-app
chown -R deploy:deploy /var/www/wedding-app
cd /var/www/wedding-app
```

### 4. Clone your repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git .
```

### 5. Create and configure .env file

```bash
cp .env.example .env
nano .env  # Edit with your production values
```

## GitHub Secrets Configuration

You need to configure the following secrets in your GitHub repository. The deployment now builds the `.env` file from GitHub Secrets, giving you centralized secret management.

### Required Secrets Setup

1. **Navigate to GitHub Repository Settings**
   - Go to your repository on GitHub
   - Click on "Settings" → "Secrets and variables" → "Actions"
   - Click "New repository secret" for each secret below

### Infrastructure Secrets (Required)

#### DROPLET_HOST

- **Description**: Your DigitalOcean droplet's IP address or domain
- **Example**: `165.232.150.25` or `api.yourwedding.com`

#### DROPLET_USERNAME

- **Description**: SSH username for deployment
- **Example**: `root` or `deploy` (if you created a deployment user)

#### DROPLET_PORT

- **Description**: SSH port (usually 22)
- **Example**: `22`

#### DROPLET_SSH_KEY

- **Description**: Private SSH key for accessing your droplet
- **How to get it**:
  ```bash
  # On your local machine
  cat ~/.ssh/id_rsa  # or your specific key file
  ```
- **Important**: Copy the ENTIRE content including:
  ```
  -----BEGIN RSA PRIVATE KEY-----
  [key content]
  -----END RSA PRIVATE KEY-----
  ```

### Application Secrets (Required)

These secrets will be used to build your production `.env` file:

#### Core Configuration

- `PORT`: Backend port (e.g., `8000`)
- `API_PORT`: API port (e.g., `8000`)

#### Database

- `MONGO_URI`: MongoDB connection string (e.g., `mongodb://mongo:27017`)
- `MONGO_DB`: Database name (e.g., `wedding`)
- `DATABASE_NAME`: Same as MONGO_DB

#### Security (CRITICAL - Generate strong values!)

- `SECRET_KEY`: JWT secret key (generate a long random string)
- `JWT_ALGORITHM`: Algorithm for JWT (e.g., `HS256`)
- `JWT_EXPIRE_MINUTES`: Token expiry (e.g., `60`)
- `API_KEY`: API authentication key
- `CSRF_SECRET_KEY`: CSRF protection key
- `CORS_ORIGINS`: Allowed origins (e.g., `https://yourfrontend.com`)

#### Admin Account

- `ROOT_ADMIN_EMAIL`: Root admin email
- `ROOT_ADMIN_PASSWORD`: Admin password (change immediately after first login)

#### SMS Configuration (if using)

- `SMS_PROVIDER`: Either `twilio` or `telnyx`
- `TWILIO_ACCOUNT_SID`: Twilio account SID
- `TWILIO_AUTH_TOKEN`: Twilio auth token
- `TWILIO_PHONE_NUMBER`: Twilio phone number

#### Email Configuration

- `RESEND_API_KEY`: Resend API key for emails
- `RESEND_FROM_EMAIL`: From email address
- `FROM_EMAIL`: Default from email

#### Storage (Cloudflare R2 or AWS S3)

- `S3_ENDPOINT_URL`: S3/R2 endpoint URL (for R2: `https://<account_id>.r2.cloudflarestorage.com`)
- `S3_BUCKET_NAME`: Bucket name
- `S3_ACCESS_KEY_ID`: Access key ID
- `S3_SECRET_ACCESS_KEY`: Secret access key
- `S3_REGION`: Region (use `auto` for Cloudflare R2)

#### Stripe (if using SaaS features)

- `STRIPE_SECRET_KEY`: Stripe secret key
- `STRIPE_WEBHOOK_SECRET`: Stripe webhook secret

#### Feature Flags

- `ENABLE_CSRF_PROTECTION`: `true` or `false`
- `ENABLE_SECURITY_HEADERS`: `true` or `false`
- `ENABLE_RATE_LIMITING`: `true` or `false`
- `ENABLE_SAAS_FEATURES`: `true` or `false`
- `ENABLE_SMS_REMINDERS`: `true` or `false`
- `ENABLE_EMAIL_REMINDERS`: `true` or `false`
- `ENABLE_AUDIT_LOGGING`: `true` or `false`

#### Monitoring (optional)

- `LOG_LEVEL`: Logging level (e.g., `INFO`)
- `SENTRY_DSN`: Sentry DSN for error tracking

### Quick Setup Script

To quickly add all secrets, you can use GitHub CLI:

```bash
# Install GitHub CLI if not already installed
# https://cli.github.com/

# Set required secrets
gh secret set DROPLET_HOST --body "your-droplet-ip"
gh secret set DROPLET_USERNAME --body "root"
gh secret set DROPLET_PORT --body "22"
gh secret set DROPLET_SSH_KEY < ~/.ssh/your_key

# Set application secrets
gh secret set MONGO_URI --body "mongodb://mongo:27017"
gh secret set MONGO_DB --body "wedding"
gh secret set DATABASE_NAME --body "wedding"
gh secret set SECRET_KEY --body "$(openssl rand -hex 32)"
gh secret set CSRF_SECRET_KEY --body "$(openssl rand -hex 32)"
gh secret set API_KEY --body "$(openssl rand -hex 24)"
# ... continue for other secrets
```

## SSH Key Setup

### Generate SSH key pair (if not already done)

```bash
# On your local machine
ssh-keygen -t rsa -b 4096 -C "deploy@wedding-app"
```

### Add public key to droplet

```bash
# On your droplet
mkdir -p ~/.ssh
echo "YOUR_PUBLIC_KEY_CONTENT" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

## Deployment Workflows

### 1. Automatic Deployment

The main workflow (`deploy-backend-production.yml`) will:

- Trigger on pushes to `main` branch
- Only deploy when backend files are changed
- Run tests before deployment
- Execute the deployment script
- Perform health checks

### 2. Manual Rollback

The rollback workflow (`rollback-backend.yml`) allows:

- Manual triggering with specific commit SHA
- Quick rollback to previous versions
- Logging of rollback reasons

## Testing the Setup

### 1. Test SSH connection locally

```bash
ssh -i ~/.ssh/your_key deploy@your-droplet-ip "echo 'Connection successful!'"
```

### 2. Test deployment script on server

```bash
# SSH into your droplet
cd /var/www/wedding-app
bash scripts/deploy.sh
```

### 3. Test GitHub Actions

- Make a small change to a backend file
- Commit and push to `main` branch
- Check Actions tab in GitHub to monitor deployment

## Environment Variables

Ensure your production `.env` file on the droplet includes:

```env
# Database
MONGO_URI=mongodb://mongo:27017
DATABASE_NAME=wedding

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Security
SECRET_KEY=your-production-secret-key
CSRF_SECRET_KEY=your-csrf-secret

# API Configuration
API_ENV=production
DEBUG=false

# External Services
RESEND_API_KEY=your-resend-api-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token

# Storage (Cloudflare R2 or AWS S3)
S3_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
S3_BUCKET_NAME=your-bucket-name
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_REGION=auto

STRIPE_SECRET_KEY=your-stripe-secret
```

## Monitoring and Logs

### View deployment logs

```bash
# On your droplet
tail -f /var/log/wedding-app-deploy.log
```

### View container logs

```bash
docker-compose logs -f api
docker-compose logs -f celery-worker
```

### Check container status

```bash
docker-compose ps
```

## Troubleshooting

### Common Issues

1. **Permission Denied**

   - Ensure deploy user is in docker group
   - Check file permissions in /var/www/wedding-app
2. **Container fails to start**

   - Check .env file is present and configured
   - Review docker-compose logs
   - Ensure ports are not already in use
3. **GitHub Actions fails**

   - Verify all secrets are correctly set
   - Check SSH key format (include headers/footers)
   - Ensure droplet firewall allows SSH connections
4. **Database connection issues**

   - Verify MongoDB container is running
   - Check MONGO_URI in .env file
   - Ensure database name matches configuration

## Security Recommendations

1. **Use deployment user instead of root**
2. **Configure firewall (ufw)**
   ```bash
   ufw allow 22/tcp    # SSH
   ufw allow 80/tcp    # HTTP
   ufw allow 443/tcp   # HTTPS
   ufw enable
   ```
3. **Set up SSL/TLS with nginx reverse proxy**
4. **Regular security updates**
   ```bash
   apt update && apt upgrade -y
   ```
5. **Monitor logs for suspicious activity**
6. **Use strong passwords and SSH keys**
7. **Consider fail2ban for brute force protection**

## Maintenance

### Regular tasks

- Monitor disk space: `df -h`
- Clean up old Docker images: `docker image prune -a`
- Backup database regularly
- Review and rotate logs
- Keep dependencies updated

## Support

For issues or questions:

1. Check GitHub Actions logs
2. Review server logs on droplet
3. Verify all environment variables
4. Ensure Docker services are running
