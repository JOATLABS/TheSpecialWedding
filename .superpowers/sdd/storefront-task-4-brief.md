# Task 4 — Storefront configuration, operator guide, and deployment contracts

## Context

Wire every storefront/custom-domain/media/inquiry configuration value into typed
settings, examples, production Compose, testbed, validation, and operator docs.
Do not create or mutate live Cloudflare/R2/DNS resources with the current
insufficient token. Never commit secrets.

## Required behavior

1. Add typed settings and examples for independent flags and contracts:
   - `STOREFRONT_CUSTOM_DOMAINS_ENABLED`
   - `STOREFRONT_DOMAIN_CONNECT_DISCOVERY_ENABLED`
   - `STOREFRONT_DOMAIN_CONNECT_AUTHORIZATION_ENABLED`
   - `STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED`
   - `CLOUDFLARE_SAAS_API_TOKEN`
   - `CLOUDFLARE_ZONE_ID`
   - `STOREFRONT_FALLBACK_ORIGIN`
   - `STOREFRONT_CNAME_TARGET`
   - `STOREFRONT_PLATFORM_DOMAINS`
   - `DOMAIN_CONNECT_PROVIDER_ID`
   - `DOMAIN_CONNECT_SERVICE_ID`
   - `DOMAIN_CONNECT_TEMPLATE_VERSION`
   - `DOMAIN_CONNECT_PRIVATE_KEY`
   - `DOMAIN_CONNECT_KEY_ID`
   - `DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN`
   - `DOMAIN_CONNECT_CALLBACK_URL`
   - current R2/media/Resend values including `S3_REGION` and
     `RESEND_FROM_NAME`.
2. Use `CLOUDFLARE_SAAS_API_TOKEN` for custom hostnames. Do not reuse the R2
   control-plane token. Keep legacy token compatibility disabled or explicit,
   never silent.
3. Pass every runtime value through `docker-compose.production.yml`; add contract
   tests that fail on omissions.
4. Startup/doctor validates configuration without provider mutations. Invalid
   custom-domain configuration disables only new custom-domain setup and emits
   a friendly readiness state; slug storefront, media, and inquiries remain
   independently available according to their own configuration.
5. Update the operator guide with:
   - actual roles: customer DNS provider, The Special Wedding, Cloudflare for
     SaaS;
   - `storefront-origin.thespecialwedding.com` fallback origin;
   - `domains.thespecialwedding.com` CNAME target;
   - `domainconnect.thespecialwedding.com` signing-key domain;
   - least-privilege tokens and key rotation;
   - Domain Connect template validation/repository submission/Cloudflare
     approval and external gate;
   - manual provider guides for Cloudflare, GoDaddy, Namecheap, Squarespace,
     Route 53, and generic DNS;
   - greenfield versus assisted migration;
   - status/support/retry/disconnect/tombstone/rollback;
   - R2 CORS/lifecycle and Resend inquiry/instruction mail;
   - exact operator doctor and deployment acceptance commands.
6. Add the template and public-key publication instructions but no real private
   key or fabricated approval receipt.
7. Update `CHANGELOG.md` with engineering truth and explicit remaining external
   dependencies.

## TDD and verification contract

- Configuration contract tests fail first, then settings/Compose/docs changes
  make them pass.
- Run focused Python settings/startup tests, frontend deployment/testbed contract
  tests, Compose config with placeholders where safe, and Ruff for changed
  Python.
- Never print secret values. Report presence/absence only.
- Do not commit. Shared dirty checkout.

## Report

Write `.superpowers/sdd/storefront-task-4-report.md`; return status, changed
files, red/green commands/counts, and external blockers.
