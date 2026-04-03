# Branch Management Workflow

> Historical reference. This document still describes the older Vercel + DigitalOcean deployment flow and should not be used as the current production deployment guide. Use [docs/plans/DEPLOYMENT_STRATEGY_STATUS.md](../plans/DEPLOYMENT_STRATEGY_STATUS.md) instead.

This document outlines the branching strategy for the Special Wedding web application.

## Branch Structure

### Main Branches

- **`main`**: Production branch - deployed to Vercel and DigitalOcean
- **`development/[feature-name]`**: Feature development branches

### Current Branches

- **`main`**: Stable production code
- **`development/saas-features`**: SAAS platform implementation

## Development Workflow

### 1. Creating Feature Branches

```bash
# Create and switch to a new feature branch
git checkout -b development/feature-name

# Example for SAAS features
git checkout -b development/saas-features
```

### 2. Development Process

1. **Make Changes**: Implement features in the development branch
2. **Test Locally**: Run `npm run dev` to test changes locally
3. **Commit Changes**: Make meaningful commits with clear messages
4. **Test Features**: Ensure all functionality works as expected

### 3. Testing Strategy

#### Backend Testing (DigitalOcean Droplet)

- Deploy backend changes to droplet for testing
- Run migration scripts on test database
- Verify API endpoints work correctly

#### Frontend Testing (Local Development)

- Test all UI components and interactions
- Verify responsive design works
- Test all user flows (signup, navigation, etc.)

#### Integration Testing

- Test frontend-backend integration
- Verify authentication flows
- Test SAAS functionality end-to-end

### 4. Merging to Main

When ready to deploy to production:

```bash
# Switch to main branch
git checkout main

# Merge the feature branch
git merge development/saas-features

# Push to trigger deployment
git push origin main
```

## SAAS Features Development

### Backend Changes (DigitalOcean)

The following backend files were deployed to the droplet:

- `app/models/saas.py` - New SAAS models
- `app/models/user_extended.py` - Extended user models
- `app/models/wedding.py` - Updated with SAAS fields
- `app/core/database.py` - New collection methods
- `app/dependencies/auth_extended.py` - Extended auth system
- `scripts/migrate_to_saas.py` - Database migration script

### Frontend Changes (Vercel)

The following frontend files are ready for deployment:

- `app/saas/page.tsx` - SAAS landing page
- `app/saas/layout.tsx` - SAAS layout
- `app/admin/saas/page.tsx` - ROOT_ADMIN dashboard
- `app/page.tsx` - Root redirect to SAAS page

### Database Migration

The production database has been successfully migrated with:

- 3 subscription plans (Starter, Professional, Enterprise)
- SAAS content collections with default content
- ROOT_ADMIN user migrated from existing admin
- 2 existing weddings updated with SAAS fields
- Database indexes for performance

## Deployment Architecture

### Production Environment

- **Frontend**: Vercel (handles Next.js app)
- **Backend**: DigitalOcean droplet (handles FastAPI)
- **Database**: MongoDB on DigitalOcean droplet

### Development Environment

- **Frontend**: Local Next.js dev server (`npm run dev`)
- **Backend**: Points to production API or local API
- **Database**: Can use production database or local MongoDB

## Current Status

### Completed Features

1. **Multi-tenant SAAS architecture**

   - Role-based access control (ROOT_ADMIN, wedding_planner, vendor)
   - Subscription plans and billing ready
   - AI usage tracking system
2. **SAAS Landing Page**

   - Professional design with Modern3D background
   - Pricing tiers with monthly/yearly toggle
   - Feature showcase and testimonials
   - Signup modal with plan selection
3. **ROOT_ADMIN Dashboard**

   - Overview with key metrics
   - Subscription plan management
   - SAAS content editing interface
   - Wedding planner management
4. **Backend Infrastructure**

   - New database collections
   - Extended authentication system
   - Backward compatibility maintained
   - Production database migrated

### Ready for Production

The `development/saas-features` branch is fully tested and ready to merge to `main` for production deployment.

### Next Steps

1. **Merge to Main**: Merge feature branch to main for production
2. **Vercel Deployment**: Frontend will auto-deploy from main branch
3. **API Integration**: Connect frontend to backend APIs
4. **Stripe Integration**: Implement payment processing
5. **AI Features**: Add presentation generator, email assistant, etc.

## Commands Reference

### Local Development

```bash
# Start development server
npm run dev

# Test migration locally
python3 scripts/local_migration_test.py
```

### Git Operations

```bash
# Check current branch
git branch -v

# Switch branches
git checkout branch-name

# Stage changes
git add .

# Commit changes
git commit -m "feat: description of changes"

# Push changes
git push origin branch-name
```

### Deployment

```bash
# Deploy backend files to droplet
./deploy_saas_files.sh

# Run migration on production
ssh root@129.212.176.74 "cd wedding-backend && docker exec wedding-api python /migrate_to_saas.py"
```

## Branch Protection

- **`main`**: Production branch - should only receive tested code
- **Feature branches**: Can be freely modified during development
- **Backup strategy**: Always create commits before major changes

## Rollback Strategy

If issues arise in production:

1. **Quick Fix**: Make minimal changes in new branch and merge
2. **Rollback**: Revert to previous main commit
3. **Database**: Keep backups before running migrations

---

**Note**: This workflow ensures stable production deployment while allowing flexible feature development.
