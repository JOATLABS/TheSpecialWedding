#!/bin/bash

# MongoDB Security Setup Script
echo "Setting up MongoDB authentication..."

# Generate secure password
MONGO_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

# Add to .env file
echo "" >> .env
echo "# MongoDB Authentication (Added $(date))" >> .env
echo "MONGO_ROOT_USER=weddingadmin" >> .env
echo "MONGO_ROOT_PASSWORD=$MONGO_PASSWORD" >> .env

echo "MongoDB credentials added to .env file"
echo "Username: weddingadmin"
echo "Password: $MONGO_PASSWORD"
echo ""
echo "IMPORTANT: Save these credentials securely!"
echo ""
echo "To apply these changes:"
echo "1. Stop current containers: docker compose down"
echo "2. Use secure compose file: docker compose -f docker-compose.secure.yml up -d"