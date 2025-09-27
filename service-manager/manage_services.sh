#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="project-services"
MENU_WINDOW="menu"
FRONTEND_WINDOW="frontend"
ALL_LOG_WINDOW="all-logs"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_ROOT="$PROJECT_ROOT/.service-manager"
LOG_DIR="$LOG_ROOT/logs"
FRONTEND_LOG_FILE="$LOG_DIR/frontend.log"
REQUIREMENTS_FILE="$PROJECT_ROOT/service-manager/requirements.txt"

mkdir -p "$LOG_DIR"

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
declare -A DEPENDENCY_DESCRIPTIONS=()
declare -A PACKAGE_MAP=()

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

    if [[ -n "${DEPENDENCY_DESCRIPTIONS[$key]+x}" ]]; then
      warn "Duplicate dependency '$key' in $REQUIREMENTS_FILE; skipping."
      continue
    fi

    DEPENDENCY_KEYS+=("$key")
    DEPENDENCY_DESCRIPTIONS["$key"]="$description"

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
      PACKAGE_MAP["$key:$manager"]="$packages"
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
  echo "${PACKAGE_MAP["$dep:$manager"]:-}"
}

install_missing_dependencies() {
  local missing=("$@")
  local manager
  if ! manager=$(detect_package_manager); then
    error "Missing required commands (${missing[*]}), and no supported package manager (apt, dnf, yum, brew) was found to install them."
    exit 1
  fi

  declare -A package_set=()
  local packages=()
  local dep pkg_specs pkg
  for dep in "${missing[@]}"; do
    pkg_specs="$(packages_for_dependency "$dep" "$manager")"
    if [[ -z "$pkg_specs" ]]; then
      warn "No installation recipe available for dependency '$dep' with package manager '$manager'."
      continue
    fi
    local pkg_array=()
    read -r -a pkg_array <<<"$pkg_specs"
    for pkg in "${pkg_array[@]}"; do
      if [[ -n "$pkg" && -z "${package_set[$pkg]:-}" ]]; then
        packages+=("$pkg")
        package_set[$pkg]=1
      fi
    done
  done

  if ((${#packages[@]} == 0)); then
    return
  fi

  case "$manager" in
    apt-get)
      info "Installing missing packages (${packages[*]}) via apt-get."
      run_with_privilege apt-get update
      run_with_privilege apt-get install -y "${packages[@]}"
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
  local key description
  for key in "${DEPENDENCY_KEYS[@]}"; do
    description="${DEPENDENCY_DESCRIPTIONS[$key]}"
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
  if [[ -z "${TMUX:-}" ]]; then
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
      tmux attach-session -t "$SESSION_NAME"
    else
      tmux new-session -d -s "$SESSION_NAME" -n "$MENU_WINDOW" "$0" --menu
      tmux attach-session -t "$SESSION_NAME"
    fi
    exit 0
  fi

  if [[ "${1:-}" != "--menu" ]]; then
    # If we are already inside tmux, restart script in menu mode.
    "$0" --menu
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
  mapfile -t services < <(list_services)
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
  local windows
  mapfile -t windows < <(tmux list-windows -t "$SESSION_NAME" -F '#{window_name}' 2>/dev/null)
  local name
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
  local services
  mapfile -t services < <(list_services)
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

print_menu() {
  clear
  cat <<'MENU'
Project Service Manager
=======================

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
11) Detach from tmux session
12) Quit manager (kills tmux session)
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
    11) tmux detach-client ;;
    12) tmux kill-session -t "$SESSION_NAME" ; exit 0 ;;
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
