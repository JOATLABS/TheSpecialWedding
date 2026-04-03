#!/usr/bin/env bash
set -euo pipefail

# Default configuration
DEFAULT_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="${DEFAULT_PROJECT_ROOT}"
MENU_WINDOW="menu"
FRONTEND_WINDOW="frontend"
ALL_LOG_WINDOW="all-logs"
SCRAPER_WINDOW="vendor-scraper"

if [[ -z "${BASH_VERSINFO:-}" ]]; then
  echo "This script must be run with Bash." >&2
  exit 1
elif (( BASH_VERSINFO[0] < 3 )); then
  echo "Bash version 3 or newer is required." >&2
  exit 1
fi

show_usage() {
  cat <<'USAGE'
Project Service Manager

USAGE:
  manage_services.sh [OPTIONS] [PROJECT_PATH]

OPTIONS:
  -h, --help              Show this help message
  -p, --project PATH      Specify project root directory
  --menu                  Internal flag for tmux menu window

ARGUMENTS:
  PROJECT_PATH            Path to project directory (default: script parent dir)

EXAMPLES:
  # Use default project (script's parent directory)
  ./manage_services.sh

  # Monitor a specific project
  ./manage_services.sh /path/to/my-project
  ./manage_services.sh -p /path/to/my-project

REQUIREMENTS:
  - Project must contain docker-compose.yml
  - Project must contain package.json (for frontend)
  - Project may contain service-manager/requirements.txt (optional)

USAGE
}

parse_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        show_usage
        exit 0
        ;;
      -p|--project)
        if [[ -z "${2:-}" ]]; then
          echo "Error: --project requires a path argument" >&2
          exit 1
        fi
        PROJECT_ROOT="$2"
        shift 2
        ;;
      --menu)
        # Internal flag used by tmux, skip it
        shift
        ;;
      -*)
        echo "Error: Unknown option: $1" >&2
        show_usage
        exit 1
        ;;
      *)
        # Treat as project path
        PROJECT_ROOT="$1"
        shift
        ;;
    esac
  done

  # Resolve to absolute path
  if [[ -n "$PROJECT_ROOT" && "$PROJECT_ROOT" != "$DEFAULT_PROJECT_ROOT" ]]; then
    PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || {
      echo "Error: Cannot access project directory: $PROJECT_ROOT" >&2
      exit 1
    }
  fi
}

validate_project_structure() {
  if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "Error: Project directory does not exist: $PROJECT_ROOT" >&2
    exit 1
  fi

  if [[ ! -f "$PROJECT_ROOT/docker-compose.yml" ]]; then
    echo "Error: No docker-compose.yml found in $PROJECT_ROOT" >&2
    echo "This doesn't appear to be a valid project directory." >&2
    exit 1
  fi

  if [[ ! -f "$PROJECT_ROOT/package.json" ]]; then
    echo "Warning: No package.json found in $PROJECT_ROOT" >&2
    echo "Frontend management will not be available." >&2
  fi
}

initialize_paths() {
  # Generate unique session name based on project path
  local project_basename
  project_basename="$(basename "$PROJECT_ROOT")"
  SESSION_NAME="services-${project_basename}"

  LOG_ROOT="$PROJECT_ROOT/.service-manager"
  LOG_DIR="$LOG_ROOT/logs"
  FRONTEND_LOG_FILE="$LOG_DIR/frontend.log"

  # Check for project-specific requirements, fall back to default
  if [[ -f "$PROJECT_ROOT/service-manager/requirements.txt" ]]; then
    REQUIREMENTS_FILE="$PROJECT_ROOT/service-manager/requirements.txt"
  elif [[ -f "$DEFAULT_PROJECT_ROOT/service-manager/requirements.txt" ]]; then
    REQUIREMENTS_FILE="$DEFAULT_PROJECT_ROOT/service-manager/requirements.txt"
  else
    # Create minimal default requirements
    REQUIREMENTS_FILE="$LOG_ROOT/requirements.txt"
    mkdir -p "$(dirname "$REQUIREMENTS_FILE")"
    cat > "$REQUIREMENTS_FILE" <<'EOF'
# dependency|description|manager=package list
tmux|tmux terminal multiplexer|apt-get=tmux|dnf=tmux|yum=tmux|brew=tmux
npm|Node.js and npm CLI|apt-get=nodejs npm|dnf=nodejs|yum=nodejs|brew=node
docker|Docker Engine|apt-get=docker.io|dnf=docker|yum=docker|brew=docker
docker_compose|Docker Compose plugin|apt-get=docker-compose-plugin|dnf=docker-compose|yum=docker-compose|brew=docker
EOF
  fi

  mkdir -p "$LOG_DIR"
}

# Parse arguments early
parse_arguments "$@"
validate_project_structure
initialize_paths

info() {
  printf '\n[INFO] %s\n' "$1"
}

warn() {
  printf '\n[WARN] %s\n' "$1" >&2
}

error() {
  printf '\n[ERROR] %s\n' "$1" >&2
}

trim() {
  local value
  value="$(printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  echo "$value"
}

declare -a DEPENDENCY_KEYS=()
declare -a DEPENDENCY_DESCRIPTIONS=()
declare -a PACKAGE_KEYS=()
declare -a PACKAGE_VALUES=()

parse_requirements() {
  if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
    error "Missing requirements file: $REQUIREMENTS_FILE"
    exit 1
  fi

  local raw_line line
  while IFS= read -r raw_line; do
    line="$(trim "$raw_line")"
    if [[ -z "$line" || "${line:0:1}" == "#" ]]; then
      continue
    fi

    IFS='|' read -r -a parts <<<"$line"
    if (( ${#parts[@]} < 2 )); then
      warn "Skipping malformed requirements entry: $line"
      continue
    fi

    local key="$(trim "${parts[0]}")"
    local description="$(trim "${parts[1]}")"
    if [[ -z "$key" ]]; then
      warn "Skipping requirements entry with empty key: $line"
      continue
    fi

    local exists="false"
    local existing_key
    for existing_key in "${DEPENDENCY_KEYS[@]}"; do
      if [[ "$existing_key" == "$key" ]]; then
        exists="true"
        break
      fi
    done

    if [[ "$exists" == "true" ]]; then
      warn "Duplicate dependency '$key' in $REQUIREMENTS_FILE; skipping."
      continue
    fi

    DEPENDENCY_KEYS+=("$key")
    DEPENDENCY_DESCRIPTIONS+=("$description")

    local idx field manager packages
    for ((idx=2; idx<${#parts[@]}; idx++)); do
      field="$(trim "${parts[$idx]}")"
      if [[ -z "$field" ]]; then
        continue
      fi
      if [[ "$field" != *=* ]]; then
        warn "Skipping package mapping without '=' for dependency '$key': $field"
        continue
      fi
      manager="$(trim "${field%%=*}")"
      packages="$(trim "${field#*=}")"
      if [[ -z "$manager" || -z "$packages" ]]; then
        warn "Skipping incomplete package mapping for dependency '$key': $field"
        continue
      fi
      PACKAGE_KEYS+=("$key|$manager")
      PACKAGE_VALUES+=("$packages")
    done
  done < "$REQUIREMENTS_FILE"

  if ((${#DEPENDENCY_KEYS[@]} == 0)); then
    error "No dependencies declared in $REQUIREMENTS_FILE"
    exit 1
  fi
}

parse_requirements

run_with_privilege() {
  if (( EUID == 0 )); then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    error "Cannot escalate privileges to install packages. Install missing dependencies manually and re-run the manager."
    exit 1
  fi
}

detect_package_manager() {
  if command -v apt-get >/dev/null 2>&1; then
    echo "apt-get"
  elif command -v dnf >/dev/null 2>&1; then
    echo "dnf"
  elif command -v yum >/dev/null 2>&1; then
    echo "yum"
  elif command -v brew >/dev/null 2>&1; then
    echo "brew"
  else
    return 1
  fi
}

packages_for_dependency() {
  local dep="$1"
  local manager="$2"
  local search_key="$dep|$manager"
  local i
  for ((i = 0; i < ${#PACKAGE_KEYS[@]}; i++)); do
    if [[ "${PACKAGE_KEYS[$i]}" == "$search_key" ]]; then
      echo "${PACKAGE_VALUES[$i]}"
      return
    fi
  done
  echo ""
}

install_missing_dependencies() {
  local missing=("$@")
  local manager
  if ! manager=$(detect_package_manager); then
    error "Missing required commands (${missing[*]}), and no supported package manager (apt, dnf, yum, brew) was found to install them."
    exit 1
  fi

  local packages=()
  local dep pkg_specs pkg existing
  for dep in "${missing[@]}"; do
    pkg_specs="$(packages_for_dependency "$dep" "$manager")"
    if [[ -z "$pkg_specs" ]]; then
      warn "No installation recipe available for dependency '$dep' with package manager '$manager'."
      continue
    fi
    local pkg_array=()
    read -r -a pkg_array <<<"$pkg_specs"
    for pkg in "${pkg_array[@]}"; do
      if [[ -z "$pkg" ]]; then
        continue
      fi
      local already_present="false"
      for existing in "${packages[@]}"; do
        if [[ "$existing" == "$pkg" ]]; then
          already_present="true"
          break
        fi
      done
      if [[ "$already_present" == "false" ]]; then
        packages+=("$pkg")
      fi
    done
  done

  if ((${#packages[@]} == 0)); then
    return
  fi

  case "$manager" in
    apt-get)
      info "Installing missing packages (${packages[*]}) via apt-get."
      # Skip update if it causes issues - packages can still install from cache
      if ! run_with_privilege apt-get update 2>/dev/null; then
        warn "apt-get update failed, attempting install without update..."
      fi
      # Don't exit on install failure - we'll verify dependencies afterward
      if ! run_with_privilege apt-get install -y "${packages[@]}" 2>&1 | tee /tmp/apt-install.log; then
        warn "Package installation encountered errors. Checking if required commands are available..."
      fi
      ;;
    dnf|yum)
      info "Installing missing packages (${packages[*]}) via $manager."
      run_with_privilege "$manager" install -y "${packages[@]}"
      ;;
    brew)
      info "Installing missing packages (${packages[*]}) via Homebrew."
      brew update
      brew install "${packages[@]}"
      ;;
  esac
}

ensure_dependencies() {
  local missing=()
  local i key description
  for ((i = 0; i < ${#DEPENDENCY_KEYS[@]}; i++)); do
    key="${DEPENDENCY_KEYS[$i]}"
    description="${DEPENDENCY_DESCRIPTIONS[$i]}"
    case "$key" in
      tmux)
        if ! command -v tmux >/dev/null 2>&1; then
          missing+=("tmux")
          warn "Missing dependency: $description"
        fi
        ;;
      npm)
        if ! command -v npm >/dev/null 2>&1; then
          missing+=("npm")
          warn "Missing dependency: $description"
        fi
        ;;
      docker)
        if ! command -v docker >/dev/null 2>&1; then
          missing+=("docker")
          warn "Missing dependency: $description"
        fi
        ;;
      docker_compose)
        if ! (command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1) && ! command -v docker-compose >/dev/null 2>&1; then
          missing+=("docker_compose")
          warn "Missing dependency: $description"
        fi
        ;;
      *)
        warn "Unsupported dependency check for '$key'."
        ;;
    esac
  done

  if ((${#missing[@]} > 0)); then
    install_missing_dependencies "${missing[@]}"

    # Re-verify that critical dependencies are now available
    local still_missing=()
    local dep
    for dep in "${missing[@]}"; do
      case "$dep" in
        tmux)
          if ! command -v tmux >/dev/null 2>&1; then
            still_missing+=("tmux")
          fi
          ;;
        npm)
          if ! command -v npm >/dev/null 2>&1; then
            still_missing+=("npm")
          fi
          ;;
        docker)
          if ! command -v docker >/dev/null 2>&1; then
            still_missing+=("docker")
          fi
          ;;
        docker_compose)
          if ! (command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1) && ! command -v docker-compose >/dev/null 2>&1; then
            still_missing+=("docker_compose")
          fi
          ;;
      esac
    done

    if ((${#still_missing[@]} > 0)); then
      error "Failed to install required dependencies: ${still_missing[*]}"
      error "Please install them manually and re-run this script."
      exit 1
    else
      info "All dependencies are now available."
    fi
  fi

  if ! command -v docker-compose >/dev/null 2>&1 && command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return
  fi

  if ! command -v docker-compose >/dev/null 2>&1 && ! (command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1); then
    error "Docker Compose is still unavailable after attempted installation."
    exit 1
  fi
}

init_compose_command() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
  else
    error "Neither 'docker compose' nor 'docker-compose' is available. Install Docker Compose first."
    exit 1
  fi
}

compose() {
  (cd "$PROJECT_ROOT" && "${COMPOSE_CMD[@]}" "$@")
}

list_services() {
  compose config --services
}

window_exists() {
  local window_name="$1"
  tmux list-windows -t "$SESSION_NAME" -F '#{window_name}' 2>/dev/null | grep -Fxq "$window_name"
}

ensure_tmux_session() {
  if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux new-session -d -s "$SESSION_NAME" -n "$MENU_WINDOW" "$0" --menu
  fi

  if [[ -z "${TMUX:-}" ]]; then
    tmux attach-session -t "$SESSION_NAME"
    exit 0
  fi

  if [[ "${1:-}" != "--menu" ]]; then
    if ! window_exists "$MENU_WINDOW"; then
      tmux new-window -d -t "$SESSION_NAME" -n "$MENU_WINDOW" "$0" --menu
    fi
    tmux switch-client -t "$SESSION_NAME:$MENU_WINDOW"
    exit 0
  fi
}

start_frontend() {
  if window_exists "$FRONTEND_WINDOW"; then
    warn "Frontend window already exists."
    return
  fi
  info "Starting frontend (npm run dev)."
  tmux new-window -d -t "$SESSION_NAME" -n "$FRONTEND_WINDOW" \
    "cd '$PROJECT_ROOT' && npm run dev"
  sleep 1
  tmux pipe-pane -t "$SESSION_NAME:$FRONTEND_WINDOW.0" "cat >> '$FRONTEND_LOG_FILE'"
}

stop_frontend() {
  if ! window_exists "$FRONTEND_WINDOW"; then
    warn "Frontend window not running."
    return
  fi
  info "Stopping frontend."
  tmux send-keys -t "$SESSION_NAME:$FRONTEND_WINDOW" C-c
  sleep 1
  if window_exists "$FRONTEND_WINDOW"; then
    tmux kill-window -t "$SESSION_NAME:$FRONTEND_WINDOW"
  fi
}

restart_frontend() {
  stop_frontend
  sleep 1
  start_frontend
}

start_backends() {
  info "Starting Docker services via ${COMPOSE_CMD[*]} up -d."
  compose up -d
}

stop_backends() {
  info "Stopping Docker services via ${COMPOSE_CMD[*]} stop."
  compose stop
}

restart_backends() {
  info "Restarting Docker services via ${COMPOSE_CMD[*]} restart."
  compose restart
}

view_frontend_logs() {
  if ! window_exists "$FRONTEND_WINDOW"; then
    warn "Frontend is not running yet. Start it first to view logs."
    return
  fi
  tmux switch-client -t "$SESSION_NAME:$FRONTEND_WINDOW"
}

view_service_logs() {
  local services=()
  while IFS= read -r service; do
    services+=("$service")
  done < <(list_services)
  if [[ ${#services[@]} -eq 0 ]]; then
    warn "No services defined in docker-compose.yml."
    return
  fi
  printf '\nSelect a Docker service to view logs:\n'
  local i
  for ((i=0; i<${#services[@]}; i++)); do
    printf '  %d) %s\n' $((i+1)) "${services[$i]}"
  done
  printf 'Enter choice (or press Enter to cancel): '
  read -r choice
  if [[ -z "$choice" ]]; then
    return
  fi
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > ${#services[@]} )); then
    warn "Invalid selection."
    return
  fi
  local service="${services[$((choice-1))]}"
  local window_name="logs-$service"
  if ! window_exists "$window_name"; then
    tmux new-window -d -t "$SESSION_NAME" -n "$window_name" \
      "cd '$PROJECT_ROOT' && ${COMPOSE_CMD[*]} logs -f --tail=200 '$service'"
  fi
  tmux switch-client -t "$SESSION_NAME:$window_name"
}

close_service_log_windows() {
  local windows=()
  local name
  while IFS= read -r name; do
    windows+=("$name")
  done < <(tmux list-windows -t "$SESSION_NAME" -F '#{window_name}' 2>/dev/null)
  for name in "${windows[@]}"; do
    if [[ "$name" == logs-* ]]; then
      tmux kill-window -t "$SESSION_NAME:$name"
    fi
  done
  if window_exists "$ALL_LOG_WINDOW"; then
    tmux kill-window -t "$SESSION_NAME:$ALL_LOG_WINDOW"
  fi
  info "Closed log windows."
}

setup_all_logs_window() {
  local services=()
  while IFS= read -r service; do
    services+=("$service")
  done < <(list_services)
  if window_exists "$ALL_LOG_WINDOW"; then
    warn "All logs view already active."
    tmux switch-client -t "$SESSION_NAME:$ALL_LOG_WINDOW"
    return
  fi

  tmux new-window -d -t "$SESSION_NAME" -n "$ALL_LOG_WINDOW" "cd '$PROJECT_ROOT' && bash"
  tmux send-keys -t "$SESSION_NAME:$ALL_LOG_WINDOW" "tail -n 200 -F '$FRONTEND_LOG_FILE'" C-m

  local service
  for service in "${services[@]}"; do
    tmux split-window -t "$SESSION_NAME:$ALL_LOG_WINDOW" -v -p 50 \
      "cd '$PROJECT_ROOT' && ${COMPOSE_CMD[*]} logs -f --tail=200 '$service'"
    tmux select-layout -t "$SESSION_NAME:$ALL_LOG_WINDOW" tiled
  done

  tmux switch-client -t "$SESSION_NAME:$ALL_LOG_WINDOW"
}

# =============================================================================
# VENDOR SCRAPER
# =============================================================================

SCRAPER_LOG_FILE="$LOG_DIR/scraper.log"
SCRAPER_EXPORT_DIR="$LOG_ROOT/exports"

run_vendor_scraper() {
  local dry_run="${1:-false}"

  if window_exists "$SCRAPER_WINDOW"; then
    warn "Scraper is already running. View logs (option 13) or wait for it to finish."
    return
  fi

  # ── State selection (loaded from states.json) ──
  local states_file="$PROJECT_ROOT/app/jobs/vendor_scraper/states.json"
  if [[ ! -f "$states_file" ]]; then
    err "states.json not found at $states_file"
    warn "Create it with: [{\"state\": \"OK\", \"state_full\": \"Oklahoma\", \"country\": \"US\"}]"
    return
  fi

  # Parse state abbreviations and full names from JSON
  local state_abbrevs=()
  local state_fulls=()
  while IFS='|' read -r abbrev full; do
    state_abbrevs+=("$abbrev")
    state_fulls+=("$full")
  done < <(python3 -c "
import json, sys
with open('$states_file') as f:
    for s in json.load(f):
        print(f\"{s['state']}|{s['state_full']}\")
")

  local state_count=${#state_abbrevs[@]}
  if [[ "$state_count" -eq 0 ]]; then
    err "No states found in states.json"
    return
  fi

  printf '\n\033[1;35mVendor Directory Scraper\033[0m\n'
  printf '\033[90m─────────────────────────────────────────\033[0m\n'
  printf '\nAvailable states (from states.json):\n'
  for i in $(seq 0 $((state_count - 1))); do
    printf '  %d) %s (%s)' "$((i + 1))" "${state_fulls[$i]}" "${state_abbrevs[$i]}"
    # 3 states per line
    if (( (i + 1) % 3 == 0 )); then
      printf '\n'
    else
      printf '    '
    fi
  done
  printf '\n  a) All states\n'
  printf '\nSelect states (comma-separated, or "a" for all): '
  read -r state_input

  local state_args=""
  if [[ "$state_input" != "a" && -n "$state_input" ]]; then
    IFS=',' read -r -a selections <<< "$state_input"
    for sel in "${selections[@]}"; do
      sel="$(trim "$sel")"
      if [[ "$sel" =~ ^[0-9]+$ ]] && (( sel >= 1 && sel <= state_count )); then
        local idx=$((sel - 1))
        state_args="$state_args --state \"${state_abbrevs[$idx]}\""
      fi
    done
  fi

  # ── Category selection ──
  printf '\nAvailable categories:\n'
  printf '  photographer, videographer, florist, caterer, venue, dj, mc,\n'
  printf '  band, officiant, planner, decorator, cake, hair_makeup,\n'
  printf '  transportation, stationery, rentals, lighting, photo_booth,\n'
  printf '  jewelry, attire\n'
  printf '\nCategories (comma-separated, or Enter for all): '
  read -r cat_input

  local cat_args=""
  if [[ -n "$cat_input" ]]; then
    # Sanitize: only allow alphanumeric, commas, underscores (valid category chars)
    local sanitized_cats
    sanitized_cats="$(printf '%s' "$cat_input" | tr -cd 'a-zA-Z0-9,_')"
    if [[ -n "$sanitized_cats" ]]; then
      cat_args="--categories $sanitized_cats"
    fi
  fi

  local dry_flag=""
  if [[ "$dry_run" == "true" ]]; then
    dry_flag="--dry-run"
  fi

  local cmd="cd '$PROJECT_ROOT' && python -m app.jobs.vendor_scraper.run $state_args $cat_args $dry_flag 2>&1 | tee '$SCRAPER_LOG_FILE'"

  local mode="LIVE"
  [[ "$dry_run" == "true" ]] && mode="DRY RUN (no DB writes)"

  printf '\n\033[90m─────────────────────────────────────────\033[0m\n'
  printf '\033[33m▶ Starting scraper...\033[0m\n'
  printf "  Mode: %s\n" "$mode"
  [[ -n "$state_args" ]] && printf "  States: %s\n" "$state_args" || printf "  States: All\n"
  [[ -n "$cat_args" ]] && printf "  Categories: %s\n" "$cat_input" || printf "  Categories: All\n"
  printf '\n'

  info "Launching scraper in a new tmux pane..."
  tmux new-window -d -t "$SESSION_NAME" -n "$SCRAPER_WINDOW" \
    "bash -c '$cmd; printf \"\n\033[32m✓ Scraper finished. Press Enter to close.\033[0m\n\"; read -r'"
  sleep 1
  tmux pipe-pane -t "$SESSION_NAME:$SCRAPER_WINDOW.0" "cat >> '$SCRAPER_LOG_FILE'"
  tmux switch-client -t "$SESSION_NAME:$SCRAPER_WINDOW"
}

view_scraper_logs() {
  if window_exists "$SCRAPER_WINDOW"; then
    tmux switch-client -t "$SESSION_NAME:$SCRAPER_WINDOW"
    return
  fi

  if [[ -f "$SCRAPER_LOG_FILE" ]]; then
    info "No active scraper session. Showing last log file..."
    tmux new-window -d -t "$SESSION_NAME" -n "$SCRAPER_WINDOW" \
      "less +G '$SCRAPER_LOG_FILE'"
    tmux switch-client -t "$SESSION_NAME:$SCRAPER_WINDOW"
  else
    warn "No scraper logs found. Run the scraper first."
  fi
}

export_scraper_json() {
  mkdir -p "$SCRAPER_EXPORT_DIR"
  local timestamp
  timestamp="$(date +%Y-%m-%d-%H%M)"
  local outfile="$SCRAPER_EXPORT_DIR/vendors-${timestamp}.json"

  info "Exporting scraped vendors to JSON..."
  cd "$PROJECT_ROOT" && python -m app.jobs.vendor_scraper.export_json "$outfile"
  local exit_code=$?

  if [[ $exit_code -eq 0 && -f "$outfile" ]]; then
    local count
    count="$(python3 -c "import json; print(len(json.load(open('$outfile'))))" 2>/dev/null || echo '?')"
    local size
    size="$(du -h "$outfile" | cut -f1)"

    printf '\n\033[32m✓ Exported %s vendors\033[0m\n' "$count"
    printf '  File: %s\n' "$outfile"
    printf '  Size: %s\n' "$size"
    printf '\n\033[37mYou can now import this file via the admin panel:\033[0m\n'
    printf '  \033[36mAdmin → Vendor Management → Import Vendors\033[0m\n'
  else
    error "Export failed. Make sure the database is running."
  fi
}

print_menu() {
  clear
  cat <<MENU
Project Service Manager
=======================
Managing: $PROJECT_ROOT

1) Start frontend (npm run dev)
2) Stop frontend
3) Restart frontend
4) Start backend services (docker compose up -d)
5) Stop backend services (docker compose stop)
6) Restart backend services (docker compose restart)
7) View frontend logs
8) View Docker service logs
9) View all logs (split panes)
10) Close log windows

── Vendor Scraper ────────────────────────
11) Run vendor scraper (prompts for args)
12) Run vendor scraper (dry run)
13) View scraper logs
14) Export last run → JSON (for admin import)

15) Detach from tmux session
16) Quit manager (kills tmux session)
MENU
}

handle_choice() {
  case "$1" in
    1) start_frontend ;;
    2) stop_frontend ;;
    3) restart_frontend ;;
    4) start_backends ;;
    5) stop_backends ;;
    6) restart_backends ;;
    7) view_frontend_logs ;;
    8) view_service_logs ;;
    9) setup_all_logs_window ;;
    10) close_service_log_windows ;;
    11) run_vendor_scraper "false" ;;
    12) run_vendor_scraper "true" ;;
    13) view_scraper_logs ;;
    14) export_scraper_json ;;
    15) tmux detach-client ;;
    16) tmux kill-session -t "$SESSION_NAME" ; exit 0 ;;
    *) warn "Unknown option: $1" ;;
  esac
  printf '\nPress Enter to continue...'
  read -r _
}

main_menu() {
  while true; do
    print_menu
    printf 'Select an option: '
    read -r choice || break
    handle_choice "$choice"
  done
}

ensure_dependencies
ensure_tmux_session "$@"
init_compose_command
main_menu
