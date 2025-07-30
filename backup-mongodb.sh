#!/bin/bash

# MongoDB Backup Script
# This script creates daily backups and keeps only the last 7 days

BACKUP_DIR="/root/backups"
DATE=$(date +%Y%m%d_%H%M%S)
CONTAINER_NAME="wedding-mongo"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

echo "Starting MongoDB backup at $(date)"

# Create backup inside container
docker exec $CONTAINER_NAME mongodump --archive=/tmp/backup_$DATE.gz --gzip --db wedding

# Copy backup from container to host
docker cp $CONTAINER_NAME:/tmp/backup_$DATE.gz $BACKUP_DIR/

# Remove backup from container
docker exec $CONTAINER_NAME rm /tmp/backup_$DATE.gz

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/backup_$DATE.gz"
echo "Backup size: $(du -h $BACKUP_DIR/backup_$DATE.gz | cut -f1)"

# List current backups
echo "Current backups:"
ls -lh $BACKUP_DIR/backup_*.gz 2>/dev/null | tail -5