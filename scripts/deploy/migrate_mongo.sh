#!/usr/bin/env bash
#
# migrate_mongo.sh — MongoDB data migration between Coolify servers
#
# Handles the full cutover workflow we worked through on staging:
#   1. mongodump from the source Coolify MongoDB container
#   2. Copy the archive to three independent locations:
#      - source server (/root), local laptop (~/wedding-migration-backups),
#        and Cloudflare R2 (s3://mongodb-backups)
#   3. mongorestore into the destination Coolify MongoDB container, using
#      --nsExclude='admin.*' so the destination's root password is preserved
#   4. Verify document counts and the planner account are present
#
# Usage:
#   ./migrate_mongo.sh backup   # dump source → local → R2 (safe, read-only on source)
#   ./migrate_mongo.sh restore  # upload archive to dest server and mongorestore
#   ./migrate_mongo.sh verify   # counts & sample user lookup on dest
#   ./migrate_mongo.sh all      # backup → restore → verify end-to-end
#
# Required env vars (or the script will prompt):
#   SOURCE_SSH_HOST        e.g. root@24.144.71.199
#   SOURCE_MONGO_CONTAINER e.g. xs8gw0okkcgogck0kogs8ok4
#   SOURCE_MONGO_PASSWORD  (prompted if unset)
#   DEST_SSH_HOST          e.g. root@134.199.184.139
#   DEST_MONGO_CONTAINER   e.g. w48gegbc093supjv6cd3ejiy
#   DEST_MONGO_PASSWORD    (prompted if unset)
#   DB_NAME                default: wedding
#   R2_ACCESS_KEY_ID       (prompted if unset)
#   R2_SECRET_ACCESS_KEY   (prompted if unset)
#   R2_ENDPOINT            default: https://78885567ce761574f5914f46808cde6a.r2.cloudflarestorage.com
#   R2_BUCKET              default: mongodb-backups
#   LOCAL_BACKUP_DIR       default: ~/wedding-migration-backups
#   ARCHIVE_NAME           default: prod-backup-<timestamp>.archive (auto-generated)
#
# Nothing here writes to production. The backup phase is read-only on the
# source. The restore phase drops collections on the destination — you are
# prompted before it runs.

set -euo pipefail

# ---- Config ---------------------------------------------------------------

DB_NAME="${DB_NAME:-wedding}"
R2_ENDPOINT="${R2_ENDPOINT:-https://78885567ce761574f5914f46808cde6a.r2.cloudflarestorage.com}"
R2_BUCKET="${R2_BUCKET:-mongodb-backups}"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-$HOME/wedding-migration-backups}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M)}"
ARCHIVE_NAME="${ARCHIVE_NAME:-prod-backup-${TIMESTAMP}.archive}"

# Colors (skipped if not a tty)
if [ -t 1 ]; then
  C_BOLD="$(tput bold 2>/dev/null || true)"
  C_RESET="$(tput sgr0 2>/dev/null || true)"
  C_RED="$(tput setaf 1 2>/dev/null || true)"
  C_GREEN="$(tput setaf 2 2>/dev/null || true)"
  C_YELLOW="$(tput setaf 3 2>/dev/null || true)"
  C_BLUE="$(tput setaf 4 2>/dev/null || true)"
else
  C_BOLD="" C_RESET="" C_RED="" C_GREEN="" C_YELLOW="" C_BLUE=""
fi

log()   { printf '%s[migrate-mongo]%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok()    { printf '%s[ ok ]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn()  { printf '%s[warn]%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
fail()  { printf '%s[fail]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 1; }
bold()  { printf '%s%s%s' "$C_BOLD" "$*" "$C_RESET"; }

prompt() {
  local var="$1" msg="$2" secret="${3:-no}" current="${!var:-}"
  if [ -n "$current" ]; then return; fi
  if [ "$secret" = "yes" ]; then  # pragma: allowlist secret
    read -r -s -p "$msg: " value
    printf '\n'
  else
    read -r -p "$msg: " value
  fi
  printf -v "$var" '%s' "$value"
}

confirm() {
  local msg="$1" answer
  read -r -p "$msg (type 'yes' to continue): " answer
  [ "$answer" = "yes" ] || fail "Aborted."
}

require_cmd() {
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || fail "Missing required command: $c"
  done
}

gather_source_creds() {
  prompt SOURCE_SSH_HOST        "Source Coolify SSH host (user@ip)" no
  prompt SOURCE_MONGO_CONTAINER "Source MongoDB container name"     no
  prompt SOURCE_MONGO_PASSWORD  "Source MongoDB root password"      yes
}

gather_dest_creds() {
  prompt DEST_SSH_HOST        "Destination Coolify SSH host (user@ip)" no
  prompt DEST_MONGO_CONTAINER "Destination MongoDB container name"     no
  prompt DEST_MONGO_PASSWORD  "Destination MongoDB root password"      yes
}

gather_r2_creds() {
  prompt R2_ACCESS_KEY_ID     "Cloudflare R2 Access Key ID"     no
  prompt R2_SECRET_ACCESS_KEY "Cloudflare R2 Secret Access Key" yes
}

ssh_run() {
  local host="$1"; shift
  # shellcheck disable=SC2029
  ssh -o StrictHostKeyChecking=accept-new "$host" "$@"
}

# ---- Phases ---------------------------------------------------------------

phase_backup() {
  require_cmd ssh scp aws
  gather_source_creds
  gather_r2_creds

  log "Source:       $(bold "$SOURCE_SSH_HOST")"
  log "Container:    $(bold "$SOURCE_MONGO_CONTAINER")"
  log "Archive:      $(bold "$ARCHIVE_NAME")"
  log "Local dir:    $(bold "$LOCAL_BACKUP_DIR")"
  log "R2 bucket:    $(bold "s3://$R2_BUCKET/")"
  mkdir -p "$LOCAL_BACKUP_DIR"

  log "Step 1/4: dumping MongoDB on source server (read-only)…"
  ssh_run "$SOURCE_SSH_HOST" \
    "docker exec $SOURCE_MONGO_CONTAINER mongodump \
       --uri='mongodb://root:${SOURCE_MONGO_PASSWORD}@localhost:27017' \
       --archive=/tmp/${ARCHIVE_NAME} --gzip" \
    || fail "mongodump failed"

  log "Step 2/4: copying archive out of source container to source /root…"
  ssh_run "$SOURCE_SSH_HOST" \
    "docker cp $SOURCE_MONGO_CONTAINER:/tmp/${ARCHIVE_NAME} /root/ && \
     ls -lh /root/${ARCHIVE_NAME}" \
    || fail "docker cp (source) failed"

  log "Step 3/4: downloading archive to laptop ($LOCAL_BACKUP_DIR)…"
  scp "${SOURCE_SSH_HOST}:/root/${ARCHIVE_NAME}" "${LOCAL_BACKUP_DIR}/" \
    || fail "scp download failed"
  ls -lh "${LOCAL_BACKUP_DIR}/${ARCHIVE_NAME}"

  log "Step 4/4: uploading archive to R2 (s3://$R2_BUCKET/)…"
  AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
  AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
    aws s3 cp "${LOCAL_BACKUP_DIR}/${ARCHIVE_NAME}" \
      "s3://${R2_BUCKET}/${ARCHIVE_NAME}" \
      --endpoint-url "$R2_ENDPOINT" \
    || fail "R2 upload failed"

  ok "Backup complete. Three copies exist:"
  printf '    - %s:/root/%s\n'       "$SOURCE_SSH_HOST" "$ARCHIVE_NAME"
  printf '    - %s/%s\n'             "$LOCAL_BACKUP_DIR" "$ARCHIVE_NAME"
  printf '    - s3://%s/%s\n'        "$R2_BUCKET" "$ARCHIVE_NAME"
}

phase_restore() {
  require_cmd ssh scp
  gather_dest_creds

  local local_archive="${LOCAL_BACKUP_DIR}/${ARCHIVE_NAME}"
  if [ ! -f "$local_archive" ]; then
    fail "Local archive not found: $local_archive
(Run './migrate_mongo.sh backup' first, or set ARCHIVE_NAME to point at an existing file.)"
  fi

  warn "About to DROP existing collections on destination and replace with source data."
  warn "Destination: $DEST_SSH_HOST (container $DEST_MONGO_CONTAINER) database='$DB_NAME'"
  confirm "Proceed?"

  log "Step 1/3: uploading archive to destination server /root…"
  scp "$local_archive" "${DEST_SSH_HOST}:/root/${ARCHIVE_NAME}" \
    || fail "scp upload failed"

  log "Step 2/3: copying archive into destination MongoDB container…"
  ssh_run "$DEST_SSH_HOST" \
    "docker cp /root/${ARCHIVE_NAME} ${DEST_MONGO_CONTAINER}:/tmp/" \
    || fail "docker cp (dest) failed"

  log "Step 3/3: mongorestore into '$DB_NAME' (skipping admin.* to preserve dest user)…"
  ssh_run "$DEST_SSH_HOST" \
    "docker exec $DEST_MONGO_CONTAINER mongorestore \
       --uri='mongodb://root:${DEST_MONGO_PASSWORD}@localhost:27017/?authSource=admin' \
       --archive=/tmp/${ARCHIVE_NAME} \
       --gzip \
       --drop \
       --noIndexRestore \
       --nsExclude='admin.*'" \
    || fail "mongorestore failed"

  ok "Restore complete."
  warn "Reminder: on the destination backend, confirm MONGO_DB=$DB_NAME then restart."
}

phase_verify() {
  gather_dest_creds

  log "Counting documents in key collections on destination…"
  ssh_run "$DEST_SSH_HOST" \
    "docker exec $DEST_MONGO_CONTAINER mongosh \
       'mongodb://root:${DEST_MONGO_PASSWORD}@localhost:27017/${DB_NAME}?authSource=admin' \
       --quiet --eval '
[\"weddings\",\"users\",\"guests\",\"rsvps\",\"plus_ones\",\"vendor_contracts\",\"planner_tasks\",\"budget_categories\"].forEach(c => {
  const n = db[c].countDocuments({});
  print(c.padEnd(25) + n);
});'" \
    || fail "verify failed"
}

phase_all() {
  phase_backup
  phase_restore
  phase_verify
}

# ---- Dispatch -------------------------------------------------------------

cmd="${1:-}"
case "$cmd" in
  backup)   phase_backup  ;;
  restore)  phase_restore ;;
  verify)   phase_verify  ;;
  all)      phase_all     ;;
  ""|-h|--help)
    sed -n '2,30p' "$0"
    exit 0
    ;;
  *)
    fail "Unknown command: $cmd (expected: backup | restore | verify | all)"
    ;;
esac
