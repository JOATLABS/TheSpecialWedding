# WeddingApp Backend Deployment Guide

This guide covers deploying the FastAPI backend to a VPS using GitHub Actions and Docker Compose.

## Architecture Overview

- **Backend Only**: This deployment configuration handles only the FastAPI backend
- **Frontend Separate**: Deploy Next.js frontend separately (Vercel, Netlify, or separate server)
- **Auto-Deploy**: Pushes to `main` or `production` branches trigger automatic deployment
- **Load Balanced**: 2 API replicas behind Nginx load balancer for high availability
- **Containerized**: Docker Compose orchestration with MongoDB, Redis, and FastAPI

## Prerequisites

### 1. VPS Requirements
- Ubuntu 20.04+ or Debian 11+
- Minimum 2GB RAM, 2 CPU cores, 20GB storage
- Docker and Docker Compose installed
- Git installed
- SSH access with key-based authentication

### 2. GitHub Repository
- Repository must be public or you need GitHub Actions enabled for private repos
- Admin access to repository settings for adding secrets

## VPS Setup

### Step 1: Initial Server Setup

SSH into your VPS and run:

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (replace 'username' with your username)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installations
docker --version
docker compose version

# Install Git if not already installed
sudo apt install git -y
```

### Step 2: Create Application Directory

```bash
# Create app directory
sudo mkdir -p /opt/weddingapp
sudo chown $USER:$USER /opt/weddingapp

# Clone your repository
cd /opt/weddingapp
git clone https://github.com/YOUR_USERNAME/WeddingWebApp.git .

# Checkout your production branch
git checkout main  # or 'production' if you use that branch
```

### Step 3: Set Up SSH Key for GitHub Actions

```bash
# Generate SSH key for GitHub Actions (if you don't have one)
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions

# Add the public key to authorized_keys
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys

# Display the private key (you'll add this to GitHub Secrets)
cat ~/.ssh/github_actions
# Copy this entire output including "-----BEGIN OPENSSH PRIVATE KEY-----" and "-----END OPENSSH PRIVATE KEY-----"
```

### Step 4: Configure Nginx (Host Level - Optional)

If you want to expose the API on a domain with SSL:

```bash
# Install Nginx
sudo apt install nginx certbot python3-certbot-nginx -y

# Create Nginx configuration for WeddingApp
sudo nano /etc/nginx/sites-available/weddingapp-backend
```

Add this configuration:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;  # Replace with your domain

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 10M;
    }
}
```

Enable the site:

```bash
# Enable the configuration
sudo ln -s /etc/nginx/sites-available/weddingapp-backend /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Get SSL certificate (replace with your domain and email)
sudo certbot --nginx -d api.yourdomain.com --email your@email.com --agree-tos --no-eff-email
```

## GitHub Configuration

### Step 1: Add GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

#### Required Secrets:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `VPS_HOST` | Your VPS IP address or domain | `123.45.67.89` |
| `VPS_USER` | SSH username | `ubuntu` or `root` |
| `VPS_SSH_KEY` | Private SSH key from Step 3 above | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `VPS_PORT` | SSH port (usually 22) | `22` |
| `MONGO_ROOT_PASSWORD` | MongoDB root password | Generate strong password |
| `MONGO_DB` | Database name | `wedding` |
| `SECRET_KEY` | JWT secret key | Generate 32+ char random string |
| `ROOT_ADMIN_EMAIL` | Admin email | `admin@yourdomain.com` |
| `ROOT_ADMIN_PASSWORD` | Admin password | Generate strong password |
| `API_URL` | Public API URL for health checks | `https://api.yourdomain.com` or `http://YOUR_VPS_IP:8000` |

#### Email Configuration:

| Secret Name | Description |
|------------|-------------|
| `RESEND_API_KEY` | Resend API key for emails |
| `RESEND_FROM_EMAIL` | From email address |

#### SMS Configuration (Twilio or Telnyx):

| Secret Name | Description |
|------------|-------------|
| `SMS_PROVIDER` | `twilio` or `telnyx` |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | Twilio Phone Number |
| `TELNYX_API_KEY` | Telnyx API Key (if using Telnyx) |
| `TELNYX_PUBLIC_KEY` | Telnyx Public Key |
| `TELNYX_PHONE_NUMBER` | Telnyx Phone Number |

#### Storage Configuration (Cloudflare R2 or S3):

| Secret Name | Description |
|------------|-------------|
| `S3_ENDPOINT_URL` | R2/S3 endpoint URL |
| `S3_ACCESS_KEY_ID` | Access key ID |
| `S3_SECRET_ACCESS_KEY` | Secret access key |
| `S3_BUCKET_NAME` | Bucket name |
| `MEDIA_DOMAIN` | Public CDN domain |

#### Stripe Configuration:

| Secret Name | Description |
|------------|-------------|
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key |

#### CORS Configuration:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated) | `https://yourdomain.com,https://www.yourdomain.com` |

### Step 2: Add GitHub Variables

Go to your GitHub repository → Settings → Secrets and variables → Actions → Variables tab → New repository variable

| Variable Name | Value | Description |
|--------------|-------|-------------|
| `DEPLOYMENT_TARGET` | `VPS` | Tells workflow to deploy to VPS |

## Deployment Workflow

### Automatic Deployment

The deployment triggers automatically when you:

1. Push to `main` or `production` branch
2. The workflow will:
   - Build Docker image and push to GitHub Container Registry
   - SSH into your VPS
   - Pull latest code
   - Generate `.env` file from GitHub secrets
   - Stop old containers
   - Pull latest images
   - Start new containers
   - Run admin setup
   - Verify health checks

### Manual Deployment

To manually trigger a deployment:

1. Go to Actions tab in GitHub
2. Select "Deploy WeddingApp Backend" workflow
3. Click "Run workflow"
4. Select the branch
5. Click "Run workflow" button

## Monitoring and Maintenance

### View Logs

SSH into your VPS:

```bash
cd /opt/weddingapp

# View all container logs
docker compose -f docker-compose.production.yml logs -f

# View specific service logs
docker compose -f docker-compose.production.yml logs -f api
docker compose -f docker-compose.production.yml logs -f mongo
docker compose -f docker-compose.production.yml logs -f redis
docker compose -f docker-compose.production.yml logs -f nginx
```

### Check Container Status

```bash
cd /opt/weddingapp
docker compose -f docker-compose.production.yml ps
```

### Restart Services

```bash
cd /opt/weddingapp

# Restart all services
docker compose -f docker-compose.production.yml restart

# Restart specific service
docker compose -f docker-compose.production.yml restart api
```

### Stop Services

```bash
cd /opt/weddingapp
docker compose -f docker-compose.production.yml down
```

### Database Backup

```bash
cd /opt/weddingapp

# Backup MongoDB
docker compose -f docker-compose.production.yml exec mongo mongodump --archive=/data/db/backup-$(date +%Y%m%d-%H%M%S).archive --db wedding

# Copy backup to host
docker cp weddingapp-mongo:/data/db/backup-YYYYMMDD-HHMMSS.archive ./backups/
```

## Scaling

### Increase API Replicas

Edit [docker-compose.production.yml](docker-compose.production.yml#L97):

```yaml
api:
  deploy:
    replicas: 4  # Increase from 2 to 4
```

Then redeploy:

```bash
docker compose -f docker-compose.production.yml up -d --scale api=4
```

### Resource Limits

Adjust CPU and memory limits in [docker-compose.production.yml](docker-compose.production.yml):

```yaml
deploy:
  resources:
    limits:
      cpus: '4'      # Increase CPU
      memory: 4G     # Increase memory
```

## Troubleshooting

### Deployment Failed

1. Check GitHub Actions logs for error details
2. SSH into VPS and check container logs
3. Verify all secrets are correctly set in GitHub

### Containers Not Starting

```bash
# Check container status
docker compose -f docker-compose.production.yml ps

# Check logs for errors
docker compose -f docker-compose.production.yml logs
```

### Database Connection Issues

```bash
# Test MongoDB connection
docker compose -f docker-compose.production.yml exec mongo mongosh -u admin -p YOUR_MONGO_PASSWORD --authenticationDatabase admin

# Check MongoDB logs
docker compose -f docker-compose.production.yml logs mongo
```

### Health Check Failing

```bash
# Test health endpoint locally on VPS
curl http://localhost:8000/health/

# Check API logs
docker compose -f docker-compose.production.yml logs api
```

## Security Best Practices

1. **Firewall Configuration**:
   ```bash
   sudo ufw allow 22/tcp      # SSH
   sudo ufw allow 80/tcp      # HTTP
   sudo ufw allow 443/tcp     # HTTPS
   sudo ufw enable
   ```

2. **Regular Updates**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   docker compose -f docker-compose.production.yml pull
   docker compose -f docker-compose.production.yml up -d
   ```

3. **Monitor Logs**: Set up log rotation and monitoring

4. **Backup Database**: Schedule regular backups

5. **SSL Certificates**: Use certbot to auto-renew certificates

## Frontend Integration

Your Next.js frontend should connect to the API using the public URL:

```typescript
// In your Next.js .env file
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
# or
NEXT_PUBLIC_API_URL=http://YOUR_VPS_IP:8000
```

Make sure the API URL is added to `CORS_ORIGINS` secret in GitHub.

## Cost Optimization

- **DigitalOcean**: $12-24/month (2-4GB RAM)
- **Linode**: $12-24/month (2-4GB RAM)
- **Hetzner**: €4-8/month (2-4GB RAM, cheaper)
- **AWS Lightsail**: $10-20/month (2-4GB RAM)

## Support

For issues or questions:
1. Check GitHub Actions logs
2. Review container logs on VPS
3. Verify all secrets are correctly configured
4. Check [CLAUDE.md](CLAUDE.md) for architecture details
