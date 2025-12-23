# WeddingApp Deployment - Quick Start

This is a condensed version of the deployment guide. For detailed instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## 🚀 Quick Setup (5 Steps)

### 1️⃣ VPS Setup (5 minutes)

```bash
# SSH into your VPS
ssh your_user@your_vps_ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh

# Create app directory and clone
sudo mkdir -p /opt/weddingapp && sudo chown $USER:$USER /opt/weddingapp
cd /opt/weddingapp
git clone https://github.com/YOUR_USERNAME/WeddingWebApp.git .

# Generate SSH key for GitHub Actions
ssh-keygen -t ed25519 -f ~/.ssh/github_actions -N ""
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_actions  # Copy this for GitHub secrets
```

### 2️⃣ GitHub Secrets (10 minutes)

Go to: **GitHub Repo → Settings → Secrets and variables → Actions → New secret**

#### Essential Secrets (Minimum to deploy):

```bash
VPS_HOST=123.45.67.89                    # Your VPS IP
VPS_USER=ubuntu                           # Your SSH user
VPS_SSH_KEY=-----BEGIN OPENSSH...        # From step 1
VPS_PORT=22                               # SSH port
MONGO_ROOT_PASSWORD=YourSecurePassword123!
MONGO_DB=wedding
SECRET_KEY=YourRandomSecretKey32CharsMin!
ROOT_ADMIN_EMAIL=admin@yourdomain.com
ROOT_ADMIN_PASSWORD=AdminSecurePass123!
API_URL=http://YOUR_VPS_IP:8000          # For health checks
CORS_ORIGINS=https://yourdomain.com      # Your frontend URL
```

#### Service Secrets (Add as needed):

**Email (Resend)**:
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`

**SMS (Twilio)**:
- `SMS_PROVIDER=twilio`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`

**Storage (Cloudflare R2)**:
- `S3_ENDPOINT_URL`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `MEDIA_DOMAIN`

**Stripe**:
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PUBLISHABLE_KEY`

### 3️⃣ GitHub Variables

Go to: **Settings → Secrets and variables → Actions → Variables tab**

```bash
DEPLOYMENT_TARGET=VPS
```

### 4️⃣ Deploy

```bash
# Option A: Push to main branch
git push origin main

# Option B: Manual trigger
# Go to Actions tab → Deploy WeddingApp Backend → Run workflow
```

### 5️⃣ Verify

```bash
# Check deployment status in GitHub Actions

# SSH into VPS and verify
ssh your_user@your_vps_ip
cd /opt/weddingapp
docker compose -f docker-compose.production.yml ps

# Test API
curl http://localhost:8000/health/
```

## 📊 What Gets Deployed

```
┌─────────────────────────────────────┐
│  Nginx Load Balancer (Port 8000)   │
│  ↓ Distributes traffic to:         │
├─────────────────────────────────────┤
│  API Replica 1  │  API Replica 2   │ (FastAPI)
├─────────────────────────────────────┤
│  MongoDB (Data) │  Redis (Cache)   │
└─────────────────────────────────────┘
```

## 🔍 Common Commands

```bash
# View logs
docker compose -f docker-compose.production.yml logs -f

# Restart services
docker compose -f docker-compose.production.yml restart

# Check status
docker compose -f docker-compose.production.yml ps

# Stop all
docker compose -f docker-compose.production.yml down
```

## 🛡️ Firewall Setup (Optional but Recommended)

```bash
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable
```

## 🌐 SSL Setup with Domain (Optional)

```bash
# Install Certbot
sudo apt install nginx certbot python3-certbot-nginx -y

# Configure Nginx for your domain
sudo nano /etc/nginx/sites-available/weddingapp-backend
```

Add:
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable and get SSL
sudo ln -s /etc/nginx/sites-available/weddingapp-backend /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.yourdomain.com
```

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Deployment fails | Check GitHub Actions logs |
| Containers won't start | `docker compose logs` |
| Can't connect to API | Check firewall: `sudo ufw status` |
| Database errors | `docker compose logs mongo` |
| Health check fails | `curl http://localhost:8000/health/` |

## 📝 Environment Variables Generated

The workflow automatically creates `.env` on your VPS with all secrets from GitHub. Never commit `.env` to version control!

## 🔗 Frontend Connection

In your Next.js frontend `.env`:

```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
# or
NEXT_PUBLIC_API_URL=http://YOUR_VPS_IP:8000
```

Make sure this URL is in the `CORS_ORIGINS` GitHub secret!

## 💰 Estimated Costs

- **DigitalOcean Droplet (2GB)**: $12/month
- **Hetzner Cloud (2GB)**: €4/month (~$4.50)
- **Linode (2GB)**: $12/month
- **AWS Lightsail (2GB)**: $10/month

## 📚 More Information

- Full deployment guide: [DEPLOYMENT.md](DEPLOYMENT.md)
- Architecture details: [CLAUDE.md](CLAUDE.md)
- GitHub Actions workflow: [.github/workflows/deploy.yml](.github/workflows/deploy.yml)
- Production compose file: [docker-compose.production.yml](docker-compose.production.yml)

---

**Need help?** Check the full [DEPLOYMENT.md](DEPLOYMENT.md) for detailed troubleshooting and advanced configurations.
