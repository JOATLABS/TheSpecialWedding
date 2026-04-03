#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Sync the Coolify rollout GitHub Actions repository secrets from a local env file.

Usage:
  scripts/deploy/sync_github_secrets.sh [options]

Options:
  --env-file PATH   Shell env file to source before syncing secrets.
                    Default: scripts/deploy/github-secrets.local.env
  --repo OWNER/REPO GitHub repository to update.
                    Default: \$GITHUB_REPOSITORY or gh repo view
  --scope NAME      Which secret group to sync:
                    shared | staging | production | all
                    Default: all
  --dry-run         Print the secret names that would be updated without
                    writing anything to GitHub.
  --help            Show this help message.

Notes:
  - This script writes repository-level Actions secrets because the current
    deploy workflows read repo secrets such as COOLIFY_STAGING_BACKEND_UUID.
  - Secret values are write-only in GitHub. Keep your real source of truth in
    the local env file, a password manager, or another secure store.
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

ENV_FILE="scripts/deploy/github-secrets.local.env"
REPO="${GITHUB_REPOSITORY:-}"
SCOPE="all"
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      [[ $# -ge 2 ]] || die "--env-file requires a value"
      ENV_FILE="$2"
      shift 2
      ;;
    --repo)
      [[ $# -ge 2 ]] || die "--repo requires a value"
      REPO="$2"
      shift 2
      ;;
    --scope)
      [[ $# -ge 2 ]] || die "--scope requires a value"
      SCOPE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

case "$SCOPE" in
  shared|staging|production|all)
    ;;
  *)
    die "Unsupported --scope value: $SCOPE"
    ;;
esac

require_command gh

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
elif [[ "$ENV_FILE" != "scripts/deploy/github-secrets.local.env" ]]; then
  die "Env file not found: $ENV_FILE"
fi

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
fi
[[ -n "$REPO" ]] || die "Unable to determine repository. Pass --repo OWNER/REPO."

gh auth status >/dev/null 2>&1 || die "gh is not authenticated. Run: gh auth login"

declare -a SHARED_REQUIRED=(
  "COOLIFY_BASE_URL"
  "COOLIFY_API_TOKEN"
  "COOLIFY_STAGING_FRONTEND_UUID"
  "COOLIFY_STAGING_BACKEND_UUID"
  "COOLIFY_PRODUCTION_FRONTEND_UUID"
  "COOLIFY_PRODUCTION_BACKEND_UUID"
)

declare -a STAGING_REQUIRED=(
  "STAGING_SMOKE_ADMIN_EMAIL"
  "STAGING_SMOKE_ADMIN_PASSWORD"
  "STAGING_SMOKE_COUPLE_EMAIL"
  "STAGING_SMOKE_COUPLE_PASSWORD"
)

declare -a STAGING_OPTIONAL=(
  "STAGING_SMOKE_PUBLIC_WEDDING_SLUG"
)

declare -a PRODUCTION_REQUIRED=(
  "PRODUCTION_SMOKE_ADMIN_EMAIL"
  "PRODUCTION_SMOKE_ADMIN_PASSWORD"
)

declare -a PRODUCTION_OPTIONAL=(
  "PRODUCTION_SMOKE_PUBLIC_WEDDING_SLUG"
)

declare -a RESOLVED_SECRETS=()
declare -a MISSING_REQUIRED=()

append_required_and_check() {
  local name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      MISSING_REQUIRED+=("$name")
    else
      RESOLVED_SECRETS+=("$name")
    fi
  done
}

append_optional_if_present() {
  local name
  for name in "$@"; do
    if [[ -n "${!name:-}" ]]; then
      RESOLVED_SECRETS+=("$name")
    fi
  done
}

case "$SCOPE" in
  shared)
    append_required_and_check "${SHARED_REQUIRED[@]}"
    ;;
  staging)
    append_required_and_check "${STAGING_REQUIRED[@]}"
    append_optional_if_present "${STAGING_OPTIONAL[@]}"
    ;;
  production)
    append_required_and_check "${PRODUCTION_REQUIRED[@]}"
    append_optional_if_present "${PRODUCTION_OPTIONAL[@]}"
    ;;
  all)
    append_required_and_check "${SHARED_REQUIRED[@]}"
    append_required_and_check "${STAGING_REQUIRED[@]}"
    append_optional_if_present "${STAGING_OPTIONAL[@]}"
    append_required_and_check "${PRODUCTION_REQUIRED[@]}"
    append_optional_if_present "${PRODUCTION_OPTIONAL[@]}"
    ;;
esac

if [[ "${#MISSING_REQUIRED[@]}" -gt 0 ]]; then
  printf 'Missing required values for scope "%s":\n' "$SCOPE" >&2
  printf '  - %s\n' "${MISSING_REQUIRED[@]}" >&2
  exit 1
fi

if [[ "${#RESOLVED_SECRETS[@]}" -eq 0 ]]; then
  die "No secrets resolved for scope \"$SCOPE\"."
fi

printf 'Repository: %s\n' "$REPO"
printf 'Scope: %s\n' "$SCOPE"
printf 'Secrets to sync (%d):\n' "${#RESOLVED_SECRETS[@]}"
printf '  - %s\n' "${RESOLVED_SECRETS[@]}"

if [[ "$DRY_RUN" == "true" ]]; then
  printf '\nDry run only. No GitHub secrets were updated.\n'
  exit 0
fi

for secret_name in "${RESOLVED_SECRETS[@]}"; do
  printf 'Updating %s...\n' "$secret_name"
  printf '%s' "${!secret_name}" | gh secret set "$secret_name" --repo "$REPO" --app actions
done

printf '\nGitHub Actions secrets synced successfully.\n'
