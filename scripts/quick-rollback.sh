#!/bin/bash

# Emergency Rollback Script for Production
# Use when deployment goes wrong and you need to quickly revert

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
PROJECT_DIR="/var/www/wedding-app"
BACKUP_DIR="/var/backups/wedding-app"

echo -e "${YELLOW}[ROLLBACK]${NC} Starting emergency rollback..."

cd $PROJECT_DIR

# Find the most recent backup
LATEST_BACKUP=$(ls -dt $BACKUP_DIR/backup_* 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo -e "${RED}[ERROR]${NC} No backup found to rollback to!"
    exit 1
fi

echo -e "${YELLOW}[ROLLBACK]${NC} Using backup: $LATEST_BACKUP"

# Get the previous commit from git reflog
PREVIOUS_COMMIT=$(git reflog -n 2 --format='%H' | tail -1)

if [ -z "$PREVIOUS_COMMIT" ]; then
    echo -e "${RED}[ERROR]${NC} Cannot determine previous commit!"
    exit 1
fi

echo -e "${YELLOW}[ROLLBACK]${NC} Rolling back to commit: $PREVIOUS_COMMIT"

# Stop containers
docker-compose down

# Rollback git
git checkout -f $PREVIOUS_COMMIT

# Restore .env file
if [ -f "$LATEST_BACKUP/.env" ]; then
    cp "$LATEST_BACKUP/.env" .env
    echo -e "${GREEN}✓${NC} Restored .env file"
fi

# Restore docker-compose.prod.yml if exists
if [ -f "$LATEST_BACKUP/docker-compose.prod.yml" ]; then
    cp "$LATEST_BACKUP/docker-compose.prod.yml" docker-compose.prod.yml
    echo -e "${GREEN}✓${NC} Restored docker-compose.prod.yml"
fi

# Rebuild and restart with previous version
docker-compose build api celery-worker
docker-compose up -d

# Wait for services
sleep 10

# Check status
echo -e "${YELLOW}[ROLLBACK]${NC} Service status after rollback:"
docker-compose ps

echo -e "${GREEN}[ROLLBACK COMPLETE]${NC} System rolled back to previous version"
echo "Current commit: $(git rev-parse HEAD)"
echo "If database restore is needed, use:"
echo "  docker exec -i wedding-mongo mongorestore --archive < $LATEST_BACKUP/mongodb_backup.archive"