#!/bin/bash

# Script to build .env file from GitHub Secrets
# This is called during deployment to create the production .env file

set -e

# Function to add a variable to .env if it's set
add_env_var() {
    local var_name=$1
    local var_value="${!var_name}"

    if [ ! -z "$var_value" ]; then
        echo "${var_name}=${var_value}" >> .env
    fi
}

# Start with empty .env
> .env

echo "# Production Environment Configuration" >> .env
echo "# Generated from GitHub Secrets on $(date)" >> .env
echo "" >> .env

# ================================
# APPLICATION SETTINGS
# ================================
echo "# Application Settings" >> .env
add_env_var NODE_ENV
add_env_var PORT
add_env_var API_PORT
add_env_var PYTHONPATH
echo "" >> .env

# ================================
# DATABASE CONFIGURATION
# ================================
echo "# Database Configuration" >> .env
add_env_var MONGO_URI
add_env_var MONGO_DB
add_env_var MONGO_NAME
add_env_var MONGODB_URL
add_env_var DATABASE_NAME
echo "" >> .env

# ================================
# SECURITY CONFIGURATION
# ================================
echo "# Security Configuration" >> .env
add_env_var SECRET_KEY
add_env_var JWT_ALGORITHM
add_env_var JWT_EXPIRE_MINUTES
add_env_var API_KEY
add_env_var CORS_ORIGINS
add_env_var ENABLE_CSRF_PROTECTION
add_env_var CSRF_SECRET_KEY
add_env_var ENABLE_SECURITY_HEADERS
add_env_var ENABLE_RATE_LIMITING
add_env_var RATE_LIMIT_REQUESTS
add_env_var RATE_LIMIT_WINDOW
echo "" >> .env

# ================================
# ADMIN CONFIGURATION
# ================================
echo "# Admin Configuration" >> .env
add_env_var PRIMARY_ADMIN_EMAIL
add_env_var PRIMARY_ADMIN_PASSWORD
add_env_var PRIMARY_ADMIN_ROLE
echo "" >> .env

# ================================
# SMS CONFIGURATION
# ================================
echo "# SMS Configuration" >> .env
add_env_var SMS_PROVIDER
add_env_var TWILIO_ACCOUNT_SID
add_env_var TWILIO_AUTH_TOKEN
add_env_var TWILIO_PHONE_NUMBER
add_env_var TELNYX_API_KEY
add_env_var TELNYX_PUBLIC_KEY
add_env_var TELNYX_PHONE_NUMBER
add_env_var TELNYX_PROFILE_ID
add_env_var TELNYX_TEST_WEBHOOK_URL
echo "" >> .env

# ================================
# EMAIL CONFIGURATION
# ================================
echo "# Email Configuration" >> .env
add_env_var RESEND_API_KEY
add_env_var RESEND_FROM_EMAIL
add_env_var FROM_EMAIL
echo "" >> .env

# ================================
# FILE STORAGE CONFIGURATION
# ================================
echo "# File Storage Configuration" >> .env
add_env_var S3_ENDPOINT_URL
add_env_var S3_BUCKET_NAME
add_env_var S3_ACCESS_KEY_ID
add_env_var S3_SECRET_ACCESS_KEY
add_env_var CLOUDFLARE_ACCOUNT_ID
add_env_var CLOUDFLARE_ACCESS_KEY_ID
add_env_var CLOUDFLARE_SECRET_ACCESS_KEY
add_env_var AWS_ACCESS_KEY_ID
add_env_var AWS_SECRET_ACCESS_KEY
add_env_var AWS_S3_BUCKET
add_env_var AWS_REGION
add_env_var MAX_UPLOAD_SIZE
add_env_var ALLOWED_FILE_TYPES
echo "" >> .env

# ================================
# GALLERY CONFIGURATION
# ================================
echo "# Gallery Configuration" >> .env
add_env_var NEXT_PUBLIC_API_BASE_URL
echo "" >> .env

# ================================
# MAPS CONFIGURATION
# ================================
echo "# Maps Configuration" >> .env
add_env_var GOOGLE_MAPS_API_KEY
echo "" >> .env

# ================================
# SAAS CONFIGURATION
# ================================
echo "# SaaS Configuration" >> .env
add_env_var ENABLE_SAAS_FEATURES
add_env_var DEFAULT_TRIAL_DAYS
add_env_var STRIPE_PUBLISHABLE_KEY
add_env_var STRIPE_SECRET_KEY
add_env_var STRIPE_WEBHOOK_SECRET
echo "" >> .env

# ================================
# REDIS CONFIGURATION
# ================================
echo "# Redis Configuration" >> .env
add_env_var REDIS_URL
add_env_var REDIS_HOST
add_env_var REDIS_PORT
echo "" >> .env

# ================================
# MONITORING & ANALYTICS
# ================================
echo "# Monitoring & Analytics" >> .env
add_env_var LOG_LEVEL
add_env_var SENTRY_DSN
add_env_var GOOGLE_ANALYTICS_ID
add_env_var VERCEL_ANALYTICS_ENABLED
echo "" >> .env

# ================================
# FEATURE FLAGS
# ================================
echo "# Feature Flags" >> .env
add_env_var ENABLE_ADMIN_PANEL
add_env_var ENABLE_SMS_REMINDERS
add_env_var ENABLE_EMAIL_REMINDERS
add_env_var ENABLE_GALLERY_UPLOAD
add_env_var ENABLE_AUDIT_LOGGING
add_env_var ENABLE_PERFORMANCE_MONITORING
echo "" >> .env

# ================================
# ENVIRONMENT FLAGS
# ================================
echo "# Environment Flags" >> .env
add_env_var API_ENV
add_env_var DEBUG
add_env_var BYPASS_AUTH
add_env_var MOCK_SMS_PROVIDER
add_env_var MOCK_EMAIL_PROVIDER

echo "✓ .env file created with $(grep -c "=" .env) variables"