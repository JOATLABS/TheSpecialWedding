#!/bin/bash

# Complete MongoDB Security Setup for Production
# Run this on your droplet

echo "=== MongoDB Security Setup ==="
echo ""

# 1. Copy scripts to droplet
echo "1. Copying security scripts..."
cp setup-mongodb-auth.sh /root/
cp backup-mongodb.sh /root/
chmod +x /root/setup-mongodb-auth.sh
chmod +x /root/backup-mongodb.sh

# 2. Run auth setup
echo "2. Setting up MongoDB authentication..."
cd /root/wedding-backend
/root/setup-mongodb-auth.sh

# 3. Set up backup cron job
echo "3. Setting up automated backups..."
mkdir -p /root/backups

# Add cron job for daily backups at 2 AM
(crontab -l 2>/dev/null | grep -v backup-mongodb; echo "0 2 * * * /root/backup-mongodb.sh >> /var/log/mongodb-backup.log 2>&1") | crontab -

echo "4. Creating backup now..."
/root/backup-mongodb.sh

echo ""
echo "=== Security Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. docker compose down"
echo "2. docker compose -f docker-compose.secure.yml up -d"
echo "3. Your MongoDB is now:"
echo "   - Not exposed to the internet"
echo "   - Protected with authentication"
echo "   - Automatically backed up daily"
echo ""
echo "Backups location: /root/backups/"
echo "Backup schedule: Daily at 2 AM"