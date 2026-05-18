#!/usr/bin/env bash
#
# prepare_new_prod.sh — Generate env vars and a checklist for bootstrapping
# a fresh new-prod Coolify project.
#
# What this script does:
#   1. Prompts for the prod-specific values (domains, new Coolify container
#      UUIDs, R2 account, Stripe/Twilio/Resend keys, etc.).
#   2. Generates fresh secrets where secrets should not be reused between
#      environments (SECRET_KEY, API_KEY, BACKUP_SECRET, CRON_SECRET,
#      SCHEDULER_HMAC_SECRET, PLATFORM_METRICS_TOKEN).
#   3. Writes three files into ./new-prod-bootstrap/:
#        - backend.env           → paste into Coolify backend-prod env vars
#        - frontend.env          → paste into Coolify frontend-prod env vars
#        - checklist.md          → step-by-step Coolify setup instructions
#        - secrets-to-rotate.md  → reminder of secrets that must be updated
#                                  in external services (Stripe, Cloudflare
#                                  worker, GitHub secrets, etc.)
#
# Nothing in this script touches Coolify, MongoDB, or any live service. It
# only produces local files for you to copy/paste.
#
# Usage:
#   ./prepare_new_prod.sh
#
# Optional env vars (skip the prompt for any of these):
#   PROD_FRONTEND_URL        e.g. https://thespecialwedding.io
#   PROD_API_URL             e.g. https://api.thespecialwedding.io
#   PROD_INTERNAL_API_BASE_URL
#                             runtime backend URL for frontend SSR/proxy
#                             (from the prod Coolify/GitHub environment)
#   PROD_MONGO_CONTAINER     UUID of wedding-prod MongoDB in new Coolify
#   PROD_MONGO_PASSWORD      root password for wedding-prod
#   PROD_REDIS_CONTAINER     UUID of redis-prod in new Coolify
#   PROD_REDIS_PASSWORD      password for redis-prod
#   OUTPUT_DIR               where to write generated files (default: ./new-prod-bootstrap)

set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-./new-prod-bootstrap}"

# ---- Color helpers --------------------------------------------------------
if [ -t 1 ]; then
  C_BOLD="$(tput bold 2>/dev/null || true)"
  C_RESET="$(tput sgr0 2>/dev/null || true)"
  C_GREEN="$(tput setaf 2 2>/dev/null || true)"
  C_YELLOW="$(tput setaf 3 2>/dev/null || true)"
  C_BLUE="$(tput setaf 4 2>/dev/null || true)"
else
  C_BOLD="" C_RESET="" C_GREEN="" C_YELLOW="" C_BLUE=""
fi

log()   { printf '%s[prepare]%s %s\n' "$C_BLUE"  "$C_RESET" "$*"; }
ok()    { printf '%s[ ok ]%s %s\n'    "$C_GREEN" "$C_RESET" "$*"; }
warn()  { printf '%s[warn]%s %s\n'    "$C_YELLOW" "$C_RESET" "$*"; }

prompt() {
  local var="$1" msg="$2" secret="${3:-no}" default="${4:-}" current="${!var:-}"
  if [ -n "$current" ]; then return; fi
  local suffix=""
  [ -n "$default" ] && suffix=" [$default]"
  if [ "$secret" = "yes" ]; then  # pragma: allowlist secret
    read -r -s -p "$msg$suffix: " value
    printf '\n'
  else
    read -r -p "$msg$suffix: " value
  fi
  [ -z "$value" ] && value="$default"
  printf -v "$var" '%s' "$value"
}

# ---- Secret generators ----------------------------------------------------
gen_base64()  { openssl rand -base64 32 | tr -d '\n'; }
gen_hex()     { openssl rand -hex 32; }
gen_url_safe() { openssl rand -base64 48 | tr '+/' '-_' | tr -d '=\n'; }

# ---- Gather inputs --------------------------------------------------------
log "This script generates env vars and a checklist for bootstrapping new-prod."
log "It asks for public values plainly and sensitive values with hidden input."
log "Output will be written to: $(printf '%s%s%s' "$C_BOLD" "$OUTPUT_DIR" "$C_RESET")"
echo

prompt PROD_FRONTEND_URL      "Production frontend URL"      no "https://thespecialwedding.io"
prompt PROD_API_URL           "Production API URL"           no "https://api.thespecialwedding.io"
prompt PROD_INTERNAL_API_BASE_URL "Production frontend INTERNAL_API_BASE_URL" no
if [ -z "$PROD_INTERNAL_API_BASE_URL" ]; then
  printf '%s\n' "PROD_INTERNAL_API_BASE_URL is required; set it from the prod environment variable/secrets source."
  exit 1
fi

echo
log "--- New Coolify resources (container UUIDs and passwords) ---"
prompt PROD_MONGO_CONTAINER   "wedding-prod MongoDB container UUID" no
prompt PROD_MONGO_PASSWORD    "wedding-prod MongoDB root password"  yes
prompt PROD_REDIS_CONTAINER   "redis-prod container UUID"           no
prompt PROD_REDIS_PASSWORD    "redis-prod password"                 yes

echo
log "--- Root admin account for new prod (created by startup script) ---"
prompt PROD_ROOT_ADMIN_EMAIL    "Root admin email"    no "thedeveloper@thespecialwedding.io"
prompt PROD_ROOT_ADMIN_PASSWORD "Root admin password" yes

echo
log "--- External service credentials ---"
log "(leave blank to skip an optional service and fill it in later)"
prompt STRIPE_SECRET_KEY        "Stripe secret key (sk_live_... or sk_test_...)" yes
prompt STRIPE_PUBLISHABLE_KEY   "Stripe publishable key (pk_live_... or pk_test_...)" no
prompt STRIPE_WEBHOOK_SECRET    "Stripe webhook signing secret (whsec_...)" yes
prompt RESEND_API_KEY           "Resend API key (re_...)" yes
prompt GOOGLE_MAPS_API_KEY      "Google Maps API key" yes

echo
log "--- R2 credentials (same account as staging, but scope a fresh token) ---"
prompt R2_ACCOUNT_ID        "Cloudflare account ID" no "78885567ce761574f5914f46808cde6a"
prompt R2_ACCESS_KEY_ID     "R2 Access Key ID (prod-scoped)"     no
prompt R2_SECRET_ACCESS_KEY "R2 Secret Access Key (prod-scoped)" yes

echo
log "Generating fresh secrets unique to prod…"
SECRET_KEY="$(gen_base64)"
API_KEY="$(gen_base64)"
BACKUP_SECRET="$(gen_base64)"
CRON_SECRET="$(gen_base64)"
SCHEDULER_HMAC_SECRET="$(gen_base64)"
PLATFORM_METRICS_TOKEN="$(gen_url_safe)"
ok "Secrets generated."

# ---- Compute derived values -----------------------------------------------
MONGO_URI="mongodb://root:${PROD_MONGO_PASSWORD}@${PROD_MONGO_CONTAINER}:27017/?directConnection=true"
S3_ENDPOINT_URL="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

mkdir -p "$OUTPUT_DIR"

# ---- Write backend.env ----------------------------------------------------
cat > "${OUTPUT_DIR}/backend.env" <<EOF
# Generated by prepare_new_prod.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Paste these into Coolify → backend-prod → Environment Variables

# --- Environment -----------------------------------------------------------
ENVIRONMENT=production
APP_NAME=The Special Wedding
APP_VERSION=2.0.0
ENABLE_API_DOCS=false

# --- Frontend / CORS -------------------------------------------------------
FRONTEND_URL=${PROD_FRONTEND_URL}
ALLOWED_HOSTS=["$(echo "$PROD_FRONTEND_URL" | sed 's|https\?://||')","$(echo "$PROD_API_URL" | sed 's|https\?://||')"]
CORS_ORIGINS=["${PROD_FRONTEND_URL}","${PROD_API_URL}"]
CORS_CREDENTIALS=true

# --- MongoDB ---------------------------------------------------------------
MONGO_URI=${MONGO_URI}
MONGO_DB=wedding

# --- Redis -----------------------------------------------------------------
REDIS_HOST=${PROD_REDIS_CONTAINER}
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=${PROD_REDIS_PASSWORD}
REDIS_ENABLED=true
CACHE_ENABLED=true
CACHE_TTL=300

# --- Auth / secrets (freshly generated, unique to prod) --------------------
SECRET_KEY=${SECRET_KEY}
API_KEY=${API_KEY}
BACKUP_SECRET=${BACKUP_SECRET}
CRON_SECRET=${CRON_SECRET}
SCHEDULER_HMAC_SECRET=${SCHEDULER_HMAC_SECRET}
PLATFORM_METRICS_TOKEN=${PLATFORM_METRICS_TOKEN}

# --- Root admin (auto-created on first startup if absent) ------------------
ROOT_ADMIN_EMAIL=${PROD_ROOT_ADMIN_EMAIL}
ROOT_ADMIN_PASSWORD=${PROD_ROOT_ADMIN_PASSWORD}

# --- Stripe ----------------------------------------------------------------
STRIPE_ENABLED=true
STRIPE_PUBLISHABLE_KEY=${STRIPE_PUBLISHABLE_KEY}
STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}

# --- Email / notifications -------------------------------------------------
RESEND_API_KEY=${RESEND_API_KEY}
RESEND_FROM_EMAIL=hello@thespecialwedding.io
RESEND_FROM_NAME=The Special Wedding
ALERT_EMAIL=alerts@thespecialwedding.io

# --- Google Maps -----------------------------------------------------------
GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY}

# --- S3 / R2 (backend-facing bucket creds) ---------------------------------
S3_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
S3_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
S3_ENDPOINT_URL=${S3_ENDPOINT_URL}
S3_BUCKET_NAME=the-special-wedding-platform
S3_AD_BUCKET_NAME=vendor-ad-assets
S3_BLOG_BUCKET_NAME=knowledgeable-saas-blogs
S3_GUEST_MEDIA_BUCKET_NAME=wedding-guest-memories
CLOUDFLARE_ACCOUNT_ID=${R2_ACCOUNT_ID}

# --- Domains (R2 bucket public URLs / custom domains) ---------------------
MEDIA_DOMAIN=media.thespecialwedding.io
AD_MEDIA_DOMAIN=ad-media.thespecialwedding.io
BLOG_MEDIA_DOMAIN=blogs.thespecialwedding.io

# --- Logging ---------------------------------------------------------------
AUDIT_LOG_FILE=logs/audit.log
SECURITY_LOG_FILE=logs/security_audit.log
SECURITY_LOG_TO_FILE=true
SLOW_REQUEST_THRESHOLD_SECONDS=1.0

# --- Rate limiting (review defaults before going live) ---------------------
RATE_LIMIT_CALLS=100
RATE_LIMIT_PERIOD=60
RATE_LIMIT_AUTH_CALLS=10
RATE_LIMIT_AUTH_PERIOD=60
EOF

ok "Wrote ${OUTPUT_DIR}/backend.env"

# ---- Write frontend.env ---------------------------------------------------
cat > "${OUTPUT_DIR}/frontend.env" <<EOF
# Generated by prepare_new_prod.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Paste these into Coolify → frontend-prod → Environment Variables
#
# NEXT_PUBLIC_* vars may be used by server-side fallbacks and deploy tooling.
# Change the "Available at Buildtime" checkbox to true for those.
# INTERNAL_API_BASE_URL is server-only, runtime only, and also drives /api/proxy.

ENVIRONMENT=production
FRONTEND_URL=${PROD_FRONTEND_URL}

# Public API fallback (must match public domain + be valid TLS)
NEXT_PUBLIC_API_BASE_URL=${PROD_API_URL}

# Server-side rendering and runtime /api/proxy. Keep this environment-scoped;
# do not bake prod/staging topology into the image or source code.
INTERNAL_API_BASE_URL=${PROD_INTERNAL_API_BASE_URL}
BACKEND_SERVICE_URL=${PROD_INTERNAL_API_BASE_URL}

# Public asset domains (same R2 buckets as backend)
NEXT_PUBLIC_MEDIA_DOMAIN=media.thespecialwedding.io
NEXT_PUBLIC_AD_MEDIA_DOMAIN=ad-media.thespecialwedding.io
NEXT_PUBLIC_BLOG_MEDIA_DOMAIN=blogs.thespecialwedding.io

GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY}
EOF

ok "Wrote ${OUTPUT_DIR}/frontend.env"

# ---- Write checklist.md ---------------------------------------------------
cat > "${OUTPUT_DIR}/checklist.md" <<EOF
# New Prod Bootstrap Checklist

Generated $(date -u +%Y-%m-%dT%H:%M:%SZ).

## 0. Prerequisites
- [ ] New DigitalOcean droplet provisioned and Coolify installed
- [ ] Coolify proxy (Traefik) running and reachable on ports 80/443
- [ ] GitHub Container Registry pull credentials added to Coolify Sources

## 1. Create Coolify project + resources
- [ ] Create a new project "TheSpecialWedding" on the new Coolify server
- [ ] Create an environment named "prod"
- [ ] Inside prod, create these resources **in this order**:
  1. \`wedding-prod\` — MongoDB 7 (match image version with old prod)
     - Note the container UUID and root password — you'll paste the UUID into backend env
  2. \`redis-prod\` — Redis 7.2
     - Note the container UUID and password
  3. \`backend-prod\` — Docker Image app:
     - Image: \`ghcr.io/lopewale/wedding-app-backend\`
     - Tag: (matches the commit you want live; use the latest CI-built tag)
     - Port Exposes: \`8000\`
     - Domain: \`${PROD_API_URL}\`
     - Network alias must match the host portion of \`${PROD_INTERNAL_API_BASE_URL}\` when using a private Coolify URL
  4. \`frontend-prod\` — Docker Image app:
     - Image: \`ghcr.io/lopewale/wedding-app-frontend\`
     - Port Exposes: \`3000\`
     - Domain: \`${PROD_FRONTEND_URL}\`
     - Network Aliases: \`frontend-prod\`

## 2. Paste env vars
- [ ] Open \`backend-prod\` → Environment Variables → "Normal view"
- [ ] Paste contents of \`backend.env\` into the textarea
- [ ] Save
- [ ] Open \`frontend-prod\` → Environment Variables
- [ ] Paste contents of \`frontend.env\`
- [ ] For each \`NEXT_PUBLIC_*\` var, check "Available at Buildtime"
- [ ] Save

## 3. Resource limits (don't skip this)
- [ ] backend-prod → Resource Limits → CPU: \`1.5\`, Memory: \`2048m\`, Memory reservation: \`512m\`
- [ ] frontend-prod → Resource Limits → CPU: \`1.0\`, Memory: \`1024m\`
- [ ] wedding-prod → Resource Limits → CPU: \`1.0\`, Memory: \`1024m\`
- [ ] redis-prod → Resource Limits → Memory: \`256m\` (Redis is memory-bound)

## 4. DNS preparation (DO NOT flip yet)
- [ ] Add A records in Cloudflare pointing to the new-prod server IP:
  - \`${PROD_FRONTEND_URL#https://}\`
  - \`${PROD_API_URL#https://}\`
  - Start with **DNS only** (grey cloud) so Let's Encrypt HTTP-01 works
- [ ] **Lower the TTL on the existing prod DNS records to 60s** on old prod,
      **at least an hour before cutover**. This speeds up propagation when
      you flip DNS during the maintenance window.

## 5. Cold-start the new-prod apps
- [ ] Deploy \`backend-prod\` (it will start empty — 1 auto-created admin user only)
- [ ] Watch logs for \`Application startup complete\`
- [ ] Deploy \`frontend-prod\`
- [ ] Verify TLS certs issued by visiting \`${PROD_API_URL}/health/livez\` in browser
      (expect JSON \`{"success":true,"data":{"status":"alive"}}\`)

## 6. Run the MongoDB migration
- [ ] On your laptop, run:
      \`\`\`
      ./scripts/deploy/migrate_mongo.sh backup
      \`\`\`
      (backs up old prod to 3 locations)
- [ ] **Put old prod in read-only mode** (stop old backend container, or just
      announce maintenance window and stop deploys)
- [ ] Run:
      \`\`\`
      DEST_SSH_HOST=root@<new-prod-ip> \\
      DEST_MONGO_CONTAINER=${PROD_MONGO_CONTAINER} \\
      ./scripts/deploy/migrate_mongo.sh restore
      \`\`\`
- [ ] Run:
      \`\`\`
      DEST_SSH_HOST=root@<new-prod-ip> \\
      DEST_MONGO_CONTAINER=${PROD_MONGO_CONTAINER} \\
      ./scripts/deploy/migrate_mongo.sh verify
      \`\`\`
- [ ] Restart \`backend-prod\` to pick up the restored data
- [ ] Test login with the planner's real credentials against \`${PROD_API_URL}\`

## 7. DNS cutover (the real "flip the switch")
- [ ] Confirm new-prod smoke tests pass (login, wedding page, RSVP)
- [ ] In Cloudflare DNS, update:
  - \`${PROD_FRONTEND_URL#https://}\` → new-prod IP
  - \`${PROD_API_URL#https://}\` → new-prod IP
- [ ] Watch for traffic shifting (look at backend logs on both servers)

## 8. Post-cutover
- [ ] Keep old prod running for 72 hours as rollback
- [ ] After 72h, take one final mongodump from old prod, upload to R2, then destroy old server
- [ ] Configure Coolify's scheduled backups on \`wedding-prod\` (daily to R2)
- [ ] Rotate the R2 creds that were leaked during the migration dry run
- [ ] Force-reset the planner's password (was exposed during debugging)
EOF

ok "Wrote ${OUTPUT_DIR}/checklist.md"

# ---- Write secrets-to-rotate.md -------------------------------------------
cat > "${OUTPUT_DIR}/secrets-to-rotate.md" <<EOF
# Secrets that must be rotated or re-synced for new-prod

## Regenerated (values already in backend.env — update external services too)
- [ ] **PLATFORM_METRICS_TOKEN** — update the metrics-snapshot Cloudflare Worker
      secret (\`wrangler secret put PLATFORM_METRICS_TOKEN\`) and the
      \`PLATFORM_METRICS_TOKEN\` GitHub Actions repo secret.
- [ ] **CRON_SECRET** — update the Autopilot Cloudflare Worker secret and the
      corresponding GitHub secret.
- [ ] **BACKUP_SECRET** — update the Backup Cloudflare Worker secret.
- [ ] **SCHEDULER_HMAC_SECRET** — any external scheduler callers need the
      new value.

## External services: verify these point at the new domain/environment
- [ ] **Stripe webhooks** — endpoint should be \`${PROD_API_URL}/webhooks/stripe\`
      (or whatever your route is). Existing webhook secret may or may not
      match; re-verify after cutover.
- [ ] **Resend webhooks** — endpoint should point at the new backend URL.
- [ ] **Google OAuth redirect URIs** — update in Google Cloud Console to
      \`${PROD_FRONTEND_URL}/auth/google/callback\` (or your exact path).
- [ ] **Twilio / Telnyx webhook callback URLs** (SMS delivery status etc.)

## R2 tokens
- [ ] Create a new R2 API token scoped to only the buckets backend-prod needs.
      The one you used during the dry-run migration was exposed in terminal
      output and should be revoked.
EOF

ok "Wrote ${OUTPUT_DIR}/secrets-to-rotate.md"

echo
warn "Files written to ${OUTPUT_DIR}/. These contain secrets — do not commit to git."
warn "Add ${OUTPUT_DIR}/ to .gitignore, or delete after pasting into Coolify."
echo
log "Next steps:"
log "  1. Review ${OUTPUT_DIR}/checklist.md"
log "  2. Provision the new Coolify resources in the order shown"
log "  3. Paste ${OUTPUT_DIR}/backend.env and frontend.env into Coolify"
log "  4. When ready, run ./scripts/deploy/migrate_mongo.sh backup (then restore)"
