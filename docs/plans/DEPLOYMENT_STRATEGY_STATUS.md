# Deployment Strategy Status

**Last reviewed:** 2026-04-03

This document is the deployment source of truth for the current repo state. It exists because the repository still contains documentation from multiple deployment eras:

- the current single-container Coolify deployment
- a newer split-service Coolify path that is partially wired in the repo
- older Vercel + DigitalOcean and droplet-only deployment guides that are now historical

## Current Production Path

The active deployment path is the single-container Coolify runtime defined in [Dockerfile.coolify](../../Dockerfile.coolify).

Current process model:

- `supervisord` runs the frontend and backend in one container
- frontend process: `npm start` on port `3000`
- backend process: `/usr/local/bin/start-backend.sh` on port `8000`
- backend concurrency: `WEB_CONCURRENCY`, default `2`
- safety rule: if `REDIS_ENABLED` is not truthy, the backend forces `WEB_CONCURRENCY=1` to preserve SSE correctness across workers
- server-rendered wedding bootstrap requests use `INTERNAL_API_BASE_URL=http://127.0.0.1:8000`
- public wedding bootstrap revalidation is controlled by `WEDDING_PRIVACY_INFO_REVALIDATE_SECONDS`, default `30`

Why this path still makes sense right now:

- lowest operational change
- fastest path to keep deploying
- recent read-path and caching fixes made this shape materially healthier

Its limits:

- frontend and backend still compete for the same CPU and memory budget
- one deploy restarts both tiers
- scaling is coarse
- worker count is constrained by SSE fan-out correctness unless Redis-backed coordination is enabled

## Deployment Alternatives Reviewed

### 1. Single-Container Coolify

**Status:** current production path

Pros:

- operationally simplest
- lowest migration risk
- fastest path for a tight timeline
- one service to manage in Coolify

Cons:

- shared failure domain
- shared CPU and memory budget
- frontend SSR and backend API still contend with each other
- independent scaling and rollback are not possible

Recommended use:

- keep this as the short-term launch posture if speed of deployment matters more than infrastructure change this week

### 2. Split-Service Coolify

**Status:** best next-step architecture

Primary repo assets already exist:

- [Dockerfile.backend](../../Dockerfile.backend)
- [Dockerfile.frontend](../../Dockerfile.frontend)
- [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- [.github/workflows/deploy-coolify.yml](../../.github/workflows/deploy-coolify.yml)
- [COOLIFY_SPLIT_DEPLOY_GUIDE.md](./COOLIFY_SPLIT_DEPLOY_GUIDE.md)

Pros:

- frontend and backend stop fighting inside one container
- backend worker tuning becomes independent from Next.js runtime tuning
- frontend and backend can be rolled back independently
- CI-gated deploy flow is already present in the repo
- still preserves the modular-monolith code architecture

Cons:

- more environment management
- more DNS and Coolify resource setup
- more moving pieces during cutover
- SSE requires Redis-enabled coordination before scaling backend workers horizontally

Recommended use:

- this is the next deployment milestone after the current single-container setup is stable enough to stop firefighting

### 3. Vercel Frontend + DigitalOcean Backend

**Status:** historical

Pros:

- clean frontend/backend runtime split
- strong frontend hosting ergonomics

Cons:

- reintroduces split-platform operational complexity
- increases cross-origin and environment drift risk
- the current repo and workflows are now more Coolify-centric than Vercel-centric

Recommended use:

- not recommended as the next move unless there is a strong platform reason to go back

### 4. DOKS / Kubernetes

**Status:** historical or future-only

Related assets:

- [.github/workflows/deploy.yml](../../.github/workflows/deploy.yml)
- [.github/workflows/k8s-bootstrap.yml](../../.github/workflows/k8s-bootstrap.yml)

Pros:

- best control over scaling and rollout behavior
- strongest long-term platform flexibility

Cons:

- much higher operational overhead than Coolify
- not aligned with the current production platform
- too much complexity for the current deployment problem

Recommended use:

- not the next step

### 5. Microservices

**Status:** explicitly not recommended now

The repo ADR in [ADR-001-monolith-vs-microservices.md](../architecture/adr/ADR-001-monolith-vs-microservices.md) still points in the right direction: modular monolith first, extraction later only when justified.

Pros:

- independent component scaling
- strongest fault isolation

Cons:

- highest complexity
- slower product iteration
- premature for the current team and load shape

Recommended use:

- later, not now

## Split-Service Coolify Readiness

The split-service path is close enough to be credible, but it is not yet "flip the switch without thinking".

### Already Present

- separate frontend and backend Dockerfiles
- CI that builds and pushes both images
- image smoke tests in CI
- Coolify deployment workflow triggered by successful CI on `main`
- post-deploy health checks for frontend and backend

### Still Needs Attention

- create and verify two actual Coolify resources in production
- move environment variables into clearly separated frontend and backend scopes
- confirm Redis-backed SSE coordination before running multi-worker or multi-instance backend deployments
- perform a true cutover test with frontend and backend on separate Coolify services
- confirm package/image ownership alignment for GHCR image references if the repository owner changes

### Fixed During This Review

- the split-service Coolify deployment workflow now stores the pre-deploy image tag per service and rolls back to that recorded tag instead of blindly resetting to `latest`
- the split-service guide now matches the real workflow shape: API token + application UUIDs, not deploy webhooks

## Recommendation

If the goal is the fastest safe path:

1. Keep the hardened single-container Coolify deployment as the short-term production posture.
2. Treat split-service Coolify as the next infrastructure milestone, not as a distant idea.
3. Do not spend time reviving the Vercel + DigitalOcean path.
4. Do not move to microservices yet.

If the goal is the best next infrastructure change:

1. Create the two Coolify services.
2. Run the existing CI and Coolify deployment workflow against them.
3. Validate SSE, health checks, and env separation.
4. Cut over domains.
5. Retire the monolith service only after the split path proves stable.

## Historical Docs

These docs are useful for context, but they are not the current source of truth for deployment:

- [docs/architecture/Architecture_Doc.md](../architecture/Architecture_Doc.md)
- [docs/architecture/BRANCH_MANAGEMENT.md](../architecture/BRANCH_MANAGEMENT.md)
- [docs/automation/DEPLOYMENT.md](../automation/DEPLOYMENT.md)
- [docs/guides/DEPLOYMENT_SETUP.md](../guides/DEPLOYMENT_SETUP.md)

Use [README.md](../../README.md) for the current production path and [COOLIFY_SPLIT_DEPLOY_GUIDE.md](./COOLIFY_SPLIT_DEPLOY_GUIDE.md) for the recommended next-state rollout.
