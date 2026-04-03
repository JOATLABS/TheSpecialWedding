# Split-Service Coolify Deployment with GitHub Actions CI Gate

> This is the recommended next-state deployment path for this repo. The current production path is still the single-container Coolify runtime in `Dockerfile.coolify`. See [DEPLOYMENT_STRATEGY_STATUS.md](./DEPLOYMENT_STRATEGY_STATUS.md) for the current-state vs next-state decision.

## Overview

This guide migrates from a single monolith container (`Dockerfile.coolify`) to two independent services (backend + frontend) deployed via Coolify, with GitHub Actions gating every deploy through CI validation.

### What Changes

| Before | After |
|--------|-------|
| Single container (supervisord) | Two independent services |
| Manual deploy via Coolify UI | Automated: push → CI → deploy |
| No CI gate on deploys | Deploy only after tests pass |
| No rollback | Instant rollback per service |
| `:latest` tags only | SHA-tagged images for traceability |

### Architecture

```
Push to main
     │
     ▼
GitHub Actions CI
  ├─ Lint (frontend + backend)
  ├─ Test (frontend + backend)
  ├─ Security audit
  ├─ Build & push images (SHA-tagged to GHCR)
  └─ Smoke test (container health check in CI)
     │
     ▼ (only if ALL above pass)
GitHub Actions Deploy
  ├─ Read current Coolify image tag (backend/frontend)
  ├─ Patch Coolify image tag via API
  ├─ Restart backend/frontend via API
  ├─ Wait for deploys to complete
  ├─ Post-deploy health checks
  └─ On failure: restore previous image tag via API
```

---

## Step 1: Coolify Dashboard Setup

### 1a. Create the Backend Service

1. In Coolify, go to **Projects → your project → New Resource → Docker Image**
2. Configure:
   - **Name**: `wedding-backend`
   - **Image**: `ghcr.io/etastic/wedding-app-backend:latest` (GitHub Actions will override the tag)
   - **Port**: `8000`
   - **Health Check Path**: `/health/readyz`
   - **Health Check Interval**: `30s`
   - **Health Check Timeout**: `10s`
   - **Health Check Retries**: `3`
   - **Health Check Start Period**: `15s`
3. **Environment Variables**: Copy all backend env vars from your current Coolify service (MONGODB_URL, SECRET_KEY, REDIS_URL, etc.)
4. **Domains**: Point `api.thespecialwedding.io` to this service
5. **Important**: Under **General → Build**, disable "Auto Deploy" — GitHub Actions will manage deploys through the Coolify API
6. Copy the application **UUID** from **General** — the workflow deploys by UUID, not by webhook
7. If you plan to run backend workers greater than `1`, verify Redis-backed SSE coordination is enabled first

### 1b. Create the Frontend Service

1. Same as above: **Projects → your project → New Resource → Docker Image**
2. Configure:
   - **Name**: `wedding-frontend`
   - **Image**: `ghcr.io/etastic/wedding-app-frontend:latest`
   - **Port**: `3000`
   - **Health Check Path**: `/`
   - **Health Check Interval**: `30s`
   - **Health Check Retries**: `3`
   - **Health Check Start Period**: `10s`
3. **Environment Variables**: Add frontend-specific vars (NEXT_PUBLIC_API_BASE_URL, NODE_ENV, etc.)
4. **Domains**: Point `thespecialwedding.io` to this service
5. Disable "Auto Deploy" and copy the application **UUID**

### 1c. Keep Your Old Service (Temporarily)

Don't delete the monolith service yet. Keep it running while you test the split services. Once both new services are verified, disable the monolith.

---

## Step 2: GitHub Repository Secrets

Add these secrets in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Description | Where to find |
|--------|-------------|---------------|
| `COOLIFY_BASE_URL` | Your Coolify instance URL (e.g. `https://coolify.yourdomain.com`) | Your browser address bar when logged into Coolify |
| `COOLIFY_API_TOKEN` | Coolify API token for deploy/rollback | Coolify → Settings → API → Create Token |
| `COOLIFY_BACKEND_UUID` | Backend application UUID | Coolify → Backend service → General → UUID |
| `COOLIFY_FRONTEND_UUID` | Frontend application UUID | Coolify → Frontend service → General → UUID |

---

## Step 3: Verify the Existing Workflow Files

These files already exist in the repo and should be treated as the split-service deployment path:

1. **`.github/workflows/ci.yml`** — Updated CI with smoke tests and image tagging
2. **`.github/workflows/deploy-coolify.yml`** — API-driven Coolify deploy after CI passes

Review before cutover:

- GHCR image naming and ownership
- Coolify application UUIDs
- backend/frontend env separation
- Redis/SSE readiness for multi-worker backend mode

---

## Step 4: Cutover Checklist

- [ ] Both services created in Coolify with correct env vars
- [ ] Health check paths configured (`/health/readyz` for backend, `/` for frontend)
- [ ] Auto-deploy disabled on both services
- [ ] Coolify API token saved as GitHub secret
- [ ] Backend and frontend UUIDs saved as GitHub secrets
- [ ] DNS pointing correctly (api.thespecialwedding.io → backend, thespecialwedding.io → frontend)
- [ ] Redis-enabled SSE coordination verified before backend worker count exceeds `1`
- [ ] First push to main triggers CI → deploy → health check successfully
- [ ] Old monolith service disabled

---

## Rollback

### Automatic
If post-deploy health checks fail, the `deploy-coolify.yml` workflow restores the previously recorded image tag for the failed service and restarts it.

### Manual
1. Go to Coolify → the failing service → Deployments
2. Click "Rollback" on the previous deployment
3. Or: re-run the GitHub Actions deploy workflow with a specific image tag via `workflow_dispatch`

---

## Monitoring

After deployment, the workflow posts a summary to the GitHub Actions run with:
- Image tags deployed
- Health check results
- Deploy duration
- Links to Coolify dashboard

You can also set up GitHub Actions notifications (Slack, email) on workflow failure.
