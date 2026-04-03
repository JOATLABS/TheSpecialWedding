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

### 2. Split-Service Coolify with Real Staging

**Status:** selected next-step rollout path

Primary repo assets already exist:

- [Dockerfile.backend](../../Dockerfile.backend)
- [Dockerfile.frontend](../../Dockerfile.frontend)
- [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- [.github/workflows/deploy-coolify.yml](../../.github/workflows/deploy-coolify.yml)
- [.github/workflows/promote-coolify-production.yml](../../.github/workflows/promote-coolify-production.yml)
- [.github/workflows/coolify-deploy-shared.yml](../../.github/workflows/coolify-deploy-shared.yml)
- [scripts/deploy/verify_environment.py](../../scripts/deploy/verify_environment.py)
- [COOLIFY_SPLIT_DEPLOY_GUIDE.md](./COOLIFY_SPLIT_DEPLOY_GUIDE.md)

Pros:

- frontend and backend stop fighting inside one container
- staging and production live on separate workload servers
- backend worker tuning becomes independent from Next.js runtime tuning
- frontend and backend can be rolled back independently by immutable SHA
- CI-gated deploy flow is present in the repo
- production deploys are manual promotions of a staged SHA, not rebuilds
- still preserves the modular-monolith code architecture

Cons:

- more environment management
- more DNS and Coolify resource setup
- more moving pieces during cutover
- SSE requires Redis-enabled coordination before scaling backend workers horizontally

Recommended use:

- this is now the intended launch rollout path: two DO workload servers, one production and one staging, both managed through Coolify Cloud

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

- create and verify the two full environment stacks in Coolify Cloud
- move environment variables into clearly separated frontend/backend and staging/production scopes
- configure `INTERNAL_API_BASE_URL` correctly on each frontend service for split-service SSR fetches
- confirm Redis-backed SSE coordination before running multi-worker or multi-instance backend deployments
- perform a true cutover test with staging promotion before production cutover
- confirm package/image ownership alignment for GHCR image references if the repository owner changes

### Fixed During This Review

- the split-service Coolify deployment workflow now stores the pre-deploy image tag per service and rolls back to that recorded tag instead of blindly resetting to `latest`
- the split-service guide now matches the real workflow shape: API token + application UUIDs, not deploy webhooks

## Recommendation

If the goal is the next launch-safe platform step:

1. Keep the current single-container Coolify runtime live until cutover day.
2. Build the two-server Coolify staging/production topology described in [COOLIFY_SPLIT_DEPLOY_GUIDE.md](./COOLIFY_SPLIT_DEPLOY_GUIDE.md).
3. Let `main` auto-deploy staging after CI.
4. Promote production manually by SHA only after staging validation passes.
5. Retire the monolith service only after the split path proves stable.

## Historical Docs

These docs are useful for context, but they are not the current source of truth for deployment:

- [docs/architecture/Architecture_Doc.md](../architecture/Architecture_Doc.md)
- [docs/architecture/BRANCH_MANAGEMENT.md](../architecture/BRANCH_MANAGEMENT.md)
- [docs/automation/DEPLOYMENT.md](../automation/DEPLOYMENT.md)
- [docs/guides/DEPLOYMENT_SETUP.md](../guides/DEPLOYMENT_SETUP.md)

Use [README.md](../../README.md) for the current production path and [COOLIFY_SPLIT_DEPLOY_GUIDE.md](./COOLIFY_SPLIT_DEPLOY_GUIDE.md) for the recommended next-state rollout.
