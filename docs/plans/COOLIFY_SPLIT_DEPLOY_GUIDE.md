# Two-Server Coolify Deployment Guide

> This is the implemented next-state rollout path in the repo. The live production environment may still be on the older single-container Coolify service until you cut over, but the GitHub Actions workflows and runtime config now target this two-server staging-first model.

## Overview

This guide moves the platform from one combined app container to two separate environments, each with its own frontend, backend, MongoDB, and Redis resources, all managed through **Coolify Cloud**.

### Target topology

| Environment | Server | Resources |
| --- | --- | --- |
| Production | DO production server | `frontend-prod`, `backend-prod`, `mongodb-prod`, `redis-prod` |
| Staging | DO staging server | `frontend-staging`, `backend-staging`, `mongodb-staging`, `redis-staging` |

### Release model

1. Push to `main`
2. GitHub Actions CI passes
3. The same immutable SHA-tagged images deploy to **staging**
4. Staging smoke checks pass
5. You manually promote that same SHA to **production**
6. Rollback means redeploying the previous known-good SHA tag

This keeps staging real, keeps production promotion manual, and avoids rebuilding the frontend for each environment.

If you need to bootstrap the first staging image after enabling the workflow chain, manually run the `CI` workflow on `main` first. That produces the initial SHA-tagged frontend and backend images in GHCR; staging can then auto-deploy from the completed CI run or be redeployed manually by the same SHA tag.

---

## Workflow assets in this repo

These files now implement the rollout:

| File | Purpose |
| --- | --- |
| [`.github/workflows/ci.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/ci.yml) | Lint, test, build, push immutable images to GHCR, and smoke-test the built images |
| [`.github/workflows/deploy-coolify.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/deploy-coolify.yml) | Auto-deploy staging after CI succeeds on `main`, or manually redeploy staging by tag |
| [`.github/workflows/promote-coolify-production.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/promote-coolify-production.yml) | Manual production promotion of an explicit SHA tag |
| [`.github/workflows/coolify-deploy-shared.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/coolify-deploy-shared.yml) | Shared deploy, verify, and rollback logic for both environments, using environment-scoped `FRONTEND_URL` and `NEXT_PUBLIC_API_BASE_URL` |
| [`.github/workflows/calendar-scheduler.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/calendar-scheduler.yml) | Runs production calendar invite jobs every 5 minutes and calendar maintenance every 15 minutes; staging can be triggered manually |
| [`scripts/deploy/verify_environment.py`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/scripts/deploy/verify_environment.py) | Post-deploy smoke verification used by both workflows |
| [`scripts/deploy/trigger_scheduler.py`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/scripts/deploy/trigger_scheduler.py) | Sends HMAC-signed scheduler requests to backend cron endpoints |

---

## Step 1: Register two servers in Coolify Cloud

In Coolify Cloud:

1. Add your **production DO server**
2. Add your **staging DO server**
3. Confirm each server is reachable and the Coolify proxy is healthy

Do **not** try to share one MongoDB or Redis between staging and production for launch. Each environment should be self-contained.

---

## Step 2: Create the Coolify resources

Create these resources in Coolify Cloud.

### Production server

- `frontend-prod`
- `backend-prod`
- `mongodb-prod`
- `redis-prod`

### Staging server

- `frontend-staging`
- `backend-staging`
- `mongodb-staging`
- `redis-staging`

### App resource type

For both frontend and backend:

1. Use **Docker Image**
2. Point the resource at the lowercase GHCR image name already produced by CI
3. Set the initial image tag to any valid SHA tag or a temporary placeholder tag that exists
4. Disable **Auto Deploy from Source**

The GitHub Actions workflows drive deploys by calling the Coolify API and changing the image tag on the existing app resources.

Use these exact image names:

- frontend: `ghcr.io/lopewale/wedding-app-frontend`
- backend: `ghcr.io/lopewale/wedding-app-backend`

Do not point Coolify at digest-pinned image names such as `...@sha256`. The deploy workflows manage tag-based promotion and rollback.

---

## Step 3: Configure domains

### Production

- frontend: `thespecialwedding.io`
- backend: `api.thespecialwedding.io`

### Staging

- frontend: `staging.thespecialwedding.io`
- backend: `api.staging.thespecialwedding.io`

Recommended health checks:

- frontend: `/`
- backend: `/health/readyz`

---

## Step 4: Configure environment variables

Keep staging and production variables fully separate.

### Frontend app variables

Required for both `frontend-prod` and `frontend-staging`:

- `NODE_ENV=production`
- `FRONTEND_URL=https://thespecialwedding.io` or `https://staging.thespecialwedding.io`
- `INTERNAL_API_BASE_URL=...`
- `NEXT_PUBLIC_API_BASE_URL=https://api.thespecialwedding.io` or `https://api.staging.thespecialwedding.io`

Important note:

- The frontend image is now runtime-portable. Browser API calls resolve from the current hostname, so the same image can move from staging to production.
- `INTERNAL_API_BASE_URL` is still important for **server-rendered** fetches. In split-service deployments this should point at the backend reachable from the frontend container.

Use one of these patterns:

1. Preferred: a Coolify-private backend URL if your Coolify network exposes one
2. Acceptable: the public API domain for that environment

Examples:

- production frontend:
  - `FRONTEND_URL=https://thespecialwedding.io`
  - `INTERNAL_API_BASE_URL=https://api.thespecialwedding.io`
- staging frontend:
  - `FRONTEND_URL=https://staging.thespecialwedding.io`
  - `INTERNAL_API_BASE_URL=https://api.staging.thespecialwedding.io`

`NEXT_PUBLIC_API_BASE_URL` is no longer the deployment-critical knob for browser routing in this split-service setup. It can still be set if you want explicit public override behavior, but it is no longer required for staging-first promotion.

### Backend app variables

Required:

- Mongo URL for that environment only
- Redis URL for that environment only
- `FRONTEND_URL` for that environment
- environment-specific `CORS_ORIGINS`
- environment-specific host validation inputs (`ALLOWED_HOSTS` or derived config)
- environment-specific `SCHEDULER_HMAC_SECRET`

Examples:

- production backend:
  - `FRONTEND_URL=https://thespecialwedding.io`
  - `CORS_ORIGINS=["https://thespecialwedding.io","https://api.thespecialwedding.io"]`
- staging backend:
  - `FRONTEND_URL=https://staging.thespecialwedding.io`
  - `CORS_ORIGINS=["https://staging.thespecialwedding.io","https://api.staging.thespecialwedding.io"]`

### Data services

- `backend-prod` points only to `mongodb-prod` and `redis-prod`
- `backend-staging` points only to `mongodb-staging` and `redis-staging`

Do not clone live planner or guest data into staging. Use fixtures or sanitized seed data instead.

---

## Step 5: Add GitHub Actions secrets

Add these repository secrets.

### Shared Coolify access

- `COOLIFY_BASE_URL`
- `COOLIFY_API_TOKEN`

### Production app UUIDs

- `COOLIFY_PRODUCTION_FRONTEND_UUID`
- `COOLIFY_PRODUCTION_BACKEND_UUID`

### Staging app UUIDs

- `COOLIFY_STAGING_FRONTEND_UUID`
- `COOLIFY_STAGING_BACKEND_UUID`

### Staging smoke credentials

- `STAGING_SMOKE_ADMIN_EMAIL`
- `STAGING_SMOKE_ADMIN_PASSWORD`
- `STAGING_SMOKE_COUPLE_EMAIL`
- `STAGING_SMOKE_COUPLE_PASSWORD`
- `STAGING_SMOKE_PUBLIC_WEDDING_SLUG`
- `STAGING_SCHEDULER_HMAC_SECRET`

### Production smoke credentials

- `PRODUCTION_SMOKE_ADMIN_EMAIL`
- `PRODUCTION_SMOKE_ADMIN_PASSWORD`
- `PRODUCTION_SMOKE_PUBLIC_WEDDING_SLUG`
- `PRODUCTION_SCHEDULER_HMAC_SECRET`

Use dedicated smoke accounts. Do not use a real planner or couple account as your deploy verification identity.

Runtime note:

- GitHub deploy secrets only power workflow verification.
- Backend runtime seeding now reads either generic `SMOKE_*` vars or environment-scoped `STAGING_SMOKE_*` / `PRODUCTION_SMOKE_*` vars from the container environment.
- `*_SMOKE_PUBLIC_WEDDING_SLUG` should be the public wedding path segment, but the runtime seeder and verifier also tolerate a full URL and normalize it back to the slug.

### Automate secret sync and later rotation

The repo now includes a helper script so you do not have to hand-enter these in the GitHub UI every time you rotate them.

Files:

- [`scripts/deploy/github-secrets.example.env`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/scripts/deploy/github-secrets.example.env)
- [`scripts/deploy/sync_github_secrets.sh`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/scripts/deploy/sync_github_secrets.sh)

Recommended flow:

1. Copy the example file to a local, ignored file:

   ```bash
   cp scripts/deploy/github-secrets.example.env scripts/deploy/github-secrets.local.env
   ```

2. Fill in the real values.

3. Run a dry run first:

   ```bash
   scripts/deploy/sync_github_secrets.sh \
     --env-file scripts/deploy/github-secrets.local.env \
     --repo YOUR_GITHUB_OWNER/WeddingWebApp \
     --scope all \
     --dry-run
   ```

4. If the secret list looks correct, run the real sync:

   ```bash
   scripts/deploy/sync_github_secrets.sh \
     --env-file scripts/deploy/github-secrets.local.env \
     --repo YOUR_GITHUB_OWNER/WeddingWebApp \
     --scope all
   ```

Useful subsets:

- `--scope shared` when rotating only `COOLIFY_BASE_URL`, `COOLIFY_API_TOKEN`, or the Coolify app UUIDs
- `--scope staging` when rotating only staging smoke credentials and the staging scheduler HMAC secret
- `--scope production` when rotating only production smoke credentials and the production scheduler HMAC secret

Important note:

- The current deploy workflows use **repository secrets**, not GitHub environment secrets, because they reference names like `COOLIFY_STAGING_BACKEND_UUID` directly in the workflow callers. The sync script matches that current workflow contract.

---

## Step 6: Understand the deploy flow

### Automatic staging deploy

When CI succeeds on `main`:

1. `ci.yml` builds the backend and frontend once
2. CI pushes SHA-tagged images to GHCR
3. `deploy-coolify.yml` deploys that SHA to staging
4. `verify_environment.py` checks:
   - frontend health
   - backend liveness/readiness
   - public wedding route
   - admin login
   - planner read path
   - notification SSE
   - couple login
   - couple dashboard
5. If verification fails, the workflow restores the previous SHA tag for the changed services

### Manual production promotion

When staging is good:

1. Run [`.github/workflows/promote-coolify-production.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/promote-coolify-production.yml)
2. Enter the exact image tag that passed staging
3. Select `both`, `frontend`, or `backend`
4. The workflow deploys that SHA to production
5. It re-checks:
   - frontend health
   - backend readiness
   - public wedding route
   - admin login
   - planner read path
6. If verification fails, the workflow restores the previous SHA tag for the changed service

You can also use the production workflow as a manual rollback tool by supplying an earlier known-good SHA tag.

### Scheduled calendar jobs

The shared planner calendar now depends on two recurring backend scheduler calls:

1. `POST /scheduler/calendar-invite-jobs`
2. `POST /scheduler/calendar-maintenance`

Those calls are now versioned in the repo through [`.github/workflows/calendar-scheduler.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/calendar-scheduler.yml).

Default behavior:

- production invite queue runs every 5 minutes against the production
  environment-scoped `SCHEDULER_BASE_URL`
- production calendar maintenance runs every 15 minutes against the same
  production environment-scoped `SCHEDULER_BASE_URL`
- staging is manual-only so test scheduling does not spam staging invite recipients

The workflow signs requests with HMAC using the environment-specific scheduler secret. That secret must match the backend `SCHEDULER_HMAC_SECRET` for the same environment.
The workflow also reads the environment-scoped GitHub Actions variable `SCHEDULER_BASE_URL` for the target API base URL.

Required GitHub configuration:

- environment variable `SCHEDULER_BASE_URL=https://api.staging.thespecialwedding.io`
  on the `staging` GitHub environment
- environment variable `SCHEDULER_BASE_URL=https://api.thespecialwedding.io`
  on the `production` GitHub environment

The scheduler workflow probes `GET /health/readyz` and the scheduler routes
before triggering jobs. If the configured target is missing, unhealthy, or does
not expose the scheduler endpoints yet, the run is skipped successfully instead
of failing.

Manual examples:

1. Trigger staging invite processing after validating a test meeting flow.
2. Trigger production maintenance on demand after resolving a Google quota incident.

---

## Step 7: Cutover checklist

- [ ] Production DO server registered in Coolify Cloud
- [ ] Staging DO server registered in Coolify Cloud
- [ ] Production frontend/backend/Mongo/Redis resources created
- [ ] Staging frontend/backend/Mongo/Redis resources created
- [ ] Source-based auto deploy disabled on both frontend and backend app resources
- [ ] Domains assigned correctly
- [ ] Health checks configured correctly
- [ ] `FRONTEND_URL` and `INTERNAL_API_BASE_URL` set correctly on both frontend apps
- [ ] GitHub environment variable `FRONTEND_URL` set on both environments
- [ ] GitHub environment variable `NEXT_PUBLIC_API_BASE_URL` set on both environments
- [ ] Backend env vars separated by environment
- [ ] GitHub secrets added
- [ ] GitHub environment variable `SCHEDULER_BASE_URL` set on both environments
- [ ] `SCHEDULER_HMAC_SECRET` set on both backend environments
- [ ] Calendar scheduler workflow has production secrets and succeeds on a manual dry run
- [ ] Dedicated smoke-test accounts created
- [ ] Staging seed data loaded
- [ ] First `main` merge reaches staging successfully
- [ ] Manual production promotion by SHA succeeds
- [ ] Rollback tested by redeploying a previous SHA

---

## Operational notes

### Why this is still simpler than Kubernetes

Pros:

- real staging
- controlled production promotion
- independent frontend/backend deploys
- separate staging and production failure domains
- much lower operational overhead than DOKS/GKE before launch

Cons:

- production app and production data still share one server
- no Kubernetes rolling-update orchestration
- scaling is still environment-level, not cluster-level

That tradeoff is intentional for launch.

### SSE and Redis

Keep Redis enabled in both environments. SSE, caching, and rate limiting all depend on it. Do not experiment with no-Redis production rollouts in this two-server model.

### Backups

Keep production and staging snapshots independent. Never use production as staging’s backup source.
