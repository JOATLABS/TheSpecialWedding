#!/bin/bash

# Deploy SAAS files to DigitalOcean droplet
# Server: 129.212.176.74
# Target directory: wedding-app

DROPLET_IP="129.212.176.74"
TARGET_DIR="wedding-backend"
SSH_USER="root"  # or your specific user

echo "Deploying SAAS files to DigitalOcean droplet..."
echo "Target: $SSH_USER@$DROPLET_IP:$TARGET_DIR"
echo "================================================"

# Check if SSH key exists
if [ ! -f ~/.ssh/id_rsa ] && [ ! -f ~/.ssh/id_ed25519 ]; then
    echo "Error: No SSH key found. Please ensure you have SSH access to the droplet."
    exit 1
fi

# Create backup directory on remote server
echo "Creating backup directory on remote server..."
ssh $SSH_USER@$DROPLET_IP "cd $TARGET_DIR && mkdir -p backups/$(date +%Y%m%d_%H%M%S)"

# Backup existing files before deployment
echo "Backing up existing files..."
ssh $SSH_USER@$DROPLET_IP "cd $TARGET_DIR && cp -r app/models/ backups/$(date +%Y%m%d_%H%M%S)/models_backup 2>/dev/null || true"
ssh $SSH_USER@$DROPLET_IP "cd $TARGET_DIR && cp -r app/dependencies/ backups/$(date +%Y%m%d_%H%M%S)/dependencies_backup 2>/dev/null || true"
ssh $SSH_USER@$DROPLET_IP "cd $TARGET_DIR && cp -r app/core/ backups/$(date +%Y%m%d_%H%M%S)/core_backup 2>/dev/null || true"
ssh $SSH_USER@$DROPLET_IP "cd $TARGET_DIR && cp -r scripts/ backups/$(date +%Y%m%d_%H%M%S)/scripts_backup 2>/dev/null || true"

# Transfer new model files
echo "Transferring new model files..."
scp app/models/saas.py $SSH_USER@$DROPLET_IP:$TARGET_DIR/app/models/
scp app/models/user_extended.py $SSH_USER@$DROPLET_IP:$TARGET_DIR/app/models/

# Transfer updated model files
echo "Transferring updated model files..."
scp app/models/wedding.py $SSH_USER@$DROPLET_IP:$TARGET_DIR/app/models/

# Transfer updated core files
echo "Transferring updated core files..."
scp app/core/database.py $SSH_USER@$DROPLET_IP:$TARGET_DIR/app/core/

# Transfer new dependency files
echo "Transferring new dependency files..."
scp app/dependencies/auth_extended.py $SSH_USER@$DROPLET_IP:$TARGET_DIR/app/dependencies/

# Transfer migration script
echo "Transferring migration script..."
scp scripts/migrate_to_saas.py $SSH_USER@$DROPLET_IP:$TARGET_DIR/scripts/

# Set proper permissions
echo "Setting proper permissions..."
ssh $SSH_USER@$DROPLET_IP "cd $TARGET_DIR && chmod +x scripts/migrate_to_saas.py"
ssh $SSH_USER@$DROPLET_IP "cd $TARGET_DIR && chown -R www-data:www-data app/ scripts/ 2>/dev/null || true"

echo "================================================"
echo "Deployment completed successfully!"
echo ""
echo "Next steps:"
echo "1. SSH into the droplet: ssh $SSH_USER@$DROPLET_IP"
echo "2. Navigate to the wedding-app directory: cd $TARGET_DIR"
echo "3. Run the migration script: python3 scripts/migrate_to_saas.py"
echo "4. Restart the backend services: docker-compose restart"
echo ""
echo "Files deployed:"
echo "- app/models/saas.py (new SAAS models)"
echo "- app/models/user_extended.py (extended user models)"
echo "- app/models/wedding.py (updated with SAAS fields)"
echo "- app/core/database.py (updated with new collections)"
echo "- app/dependencies/auth_extended.py (extended authentication)"
echo "- scripts/migrate_to_saas.py (database migration script)"