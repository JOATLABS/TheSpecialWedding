#!/bin/bash

# Wedding App Backend Production Deployment Script
# Designed for backend-only deployment (no frontend files)
# Safe for use with already-running production environment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - ADJUST THESE FOR YOUR ENVIRONMENT
PROJECT_DIR="/var/www/wedding-app"  # Change this to your actual path
BACKUP_DIR="/var/backups/wedding-app"
LOG_FILE="/var/log/wedding-app-deploy.log"
MAX_BACKUPS=5
HEALTH_CHECK_URL="http://localhost:8000/health"  # Adjust if different

# Function to log messages
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a $LOG_FILE
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a $LOG_FILE
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a $LOG_FILE
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a $LOG_FILE
}

# Create necessary directories
mkdir -p $BACKUP_DIR
touch $LOG_FILE

log "========================================="
log "Starting Backend Deployment Process"
log "========================================="

# Navigate to project directory
cd $PROJECT_DIR || error "Failed to navigate to project directory at $PROJECT_DIR"

# Check current git status
info "Current git status:"
git status --short

# Store current commit for potential rollback
PREVIOUS_COMMIT=$(git rev-parse HEAD)
log "Current commit: $PREVIOUS_COMMIT"

# Backup critical files before deployment
log "Creating backup of critical files..."
BACKUP_TIMESTAMP=$(date +'%Y%m%d_%H%M%S')
BACKUP_PATH="$BACKUP_DIR/backup_$BACKUP_TIMESTAMP"
mkdir -p $BACKUP_PATH

# Backup .env file if it exists (may not exist on first deployment)
if [ -f .env ]; then
    cp .env "$BACKUP_PATH/.env"
    log "✓ Backed up existing .env file"
else
    log "No existing .env file found (will be created from GitHub Secrets)"
fi

# Backup docker-compose override if it exists
if [ -f docker-compose.prod.yml ]; then
    cp docker-compose.prod.yml "$BACKUP_PATH/docker-compose.prod.yml"
    log "✓ Backed up docker-compose.prod.yml"
fi

# Pull latest changes from Git (backend files only)
log "Pulling latest changes from repository..."
git fetch origin main || error "Failed to fetch from repository"
git pull origin main || {
    error "Failed to pull from repository. You may need to resolve conflicts manually."
}

NEW_COMMIT=$(git rev-parse HEAD)
log "New commit: $NEW_COMMIT"

# Check if deployment actually has changes
if [ "$PREVIOUS_COMMIT" = "$NEW_COMMIT" ]; then
    warning "No new changes detected. Skipping deployment."
    exit 0
fi

# Show what changed (backend files only)
info "Changes in this deployment:"
git diff --name-only $PREVIOUS_COMMIT $NEW_COMMIT | grep -E "^(app/(api|core|dependencies|middleware|models|services|tasks|utils)|scripts|requirements\.txt|Dockerfile|docker-compose)" || true

# Build .env file from GitHub Secrets (passed as environment variables)
# This will be populated by the GitHub Action
if [ ! -z "$ENV_FILE_CONTENT" ]; then
    log "Building .env file from GitHub Secrets..."
    echo "$ENV_FILE_CONTENT" > .env
    log "✓ Created .env file from GitHub Secrets"
elif [ -f "$BACKUP_PATH/.env" ]; then
    # Fallback to backup if no new env provided
    cp "$BACKUP_PATH/.env" .env
    log "✓ Restored production .env file from backup"
else
    error "No .env file available! Cannot proceed without environment configuration"
fi

# Verify required backend files exist
log "Verifying required backend files..."
required_files=("docker-compose.yml" "Dockerfile" "requirements.txt" "app/main.py")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        error "Required file $file not found! Rolling back..."
        git checkout $PREVIOUS_COMMIT
        cp "$BACKUP_PATH/.env" .env
        exit 1
    fi
done
log "✓ All required files present"

# Check disk space before proceeding
DISK_USAGE=$(df -h $PROJECT_DIR | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 85 ]; then
    warning "Disk usage is at ${DISK_USAGE}%. Consider cleaning up old images."
    docker image prune -f
fi

# Database backup (CRITICAL for production)
log "Creating database backup..."
if docker exec wedding-mongo mongodump --archive="/tmp/backup_$BACKUP_TIMESTAMP.archive" --db=wedding 2>/dev/null; then
    docker cp wedding-mongo:/tmp/backup_$BACKUP_TIMESTAMP.archive "$BACKUP_PATH/mongodb_backup.archive"
    log "✓ Database backed up successfully"
else
    warning "Database backup failed - continuing anyway (risky!)"
fi

# Build new backend images (without stopping current containers)
log "Building new Docker images for backend services..."
docker-compose build api celery-worker || {
    error "Failed to build Docker images. Rolling back..."
    git checkout $PREVIOUS_COMMIT
    cp "$BACKUP_PATH/.env" .env
    exit 1
}

# Graceful container replacement (minimal downtime)
log "Performing rolling update of backend services..."

# Update API service
log "Updating API service..."
docker-compose up -d --no-deps --build api || {
    error "Failed to update API service. Rolling back..."
    docker-compose up -d --force-recreate api
    git checkout $PREVIOUS_COMMIT
    cp "$BACKUP_PATH/.env" .env
    exit 1
}

# Wait for API to be healthy
log "Waiting for API service to be healthy..."
for i in {1..30}; do
    if curl -f $HEALTH_CHECK_URL 2>/dev/null; then
        log "✓ API service is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        error "API service failed health check after 30 seconds"
    fi
    sleep 1
done

# Update Celery worker
log "Updating Celery worker..."
docker-compose up -d --no-deps --build celery-worker || {
    warning "Failed to update Celery worker - continuing anyway"
}

# Run any database migrations or admin setup (if needed)
if [ -f "scripts/setup_admin_user.py" ]; then
    log "Running admin setup (if needed)..."
    docker-compose run --rm api python scripts/setup_admin_user.py --auto-create || true
fi

# Clean up old Docker images to save space
log "Cleaning up old Docker images..."
docker image prune -f

# Clean up old backups (keep only last MAX_BACKUPS)
log "Cleaning up old backups..."
ls -dt $BACKUP_DIR/backup_* 2>/dev/null | tail -n +$((MAX_BACKUPS+1)) | xargs rm -rf 2>/dev/null || true

# Verify all backend services are running
log "Verifying backend services status..."
services=("wedding-api" "wedding-celery-worker" "wedding-mongo" "wedding-redis")
all_healthy=true

for service in "${services[@]}"; do
    if [ "$(docker inspect -f '{{.State.Running}}' $service 2>/dev/null)" == "true" ]; then
        log "✓ $service is running"
    else
        warning "✗ $service is not running"
        all_healthy=false
    fi
done

# Show container status
info "Current container status:"
docker-compose ps

# Show recent API logs (last 10 lines)
info "Recent API logs:"
docker-compose logs --tail 10 api

# Final status
if [ "$all_healthy" = true ]; then
    log "========================================="
    log "✓ Backend deployment completed successfully!"
    log "========================================="
    echo -e "${GREEN}Deployment Summary:${NC}"
    echo "  Previous commit: $PREVIOUS_COMMIT"
    echo "  Current commit:  $NEW_COMMIT"
    echo "  Backup location: $BACKUP_PATH"
    echo "  All services:    HEALTHY"

    # Optional: Send success notification
    # curl -X POST -H 'Content-Type: application/json' \
    #      -d '{"text":"✅ Wedding App backend deployed successfully to production!"}' \
    #      $SLACK_WEBHOOK_URL 2>/dev/null || true
else
    error "Backend deployment completed with errors. Check logs at $LOG_FILE"

    # Optional: Send failure alert
    # curl -X POST -H 'Content-Type: application/json' \
    #      -d '{"text":"⚠️ Wedding App backend deployment had issues. Please check!"}' \
    #      $SLACK_WEBHOOK_URL 2>/dev/null || true
fi