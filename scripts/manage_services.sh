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

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    error "Required command '$1' is not available in PATH."
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
  require_command tmux

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

ensure_tmux_session "$@"
init_compose_command
main_menu
