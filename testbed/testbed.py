#!/usr/bin/env python3
"""
testbed/testbed.py — live-service orchestrator for subscription-lifecycle drivers.

Patterned after `service-manager/manage_services.sh`: long-running processes live
in a named tmux session, one window per concern, with every window piped to a log
file under `testbed/.testbed/logs/`. Subcommands are scriptable (good for CI-ish
loops) and the same session can be attached interactively with `attach`.

Services managed:

    backend   → uvicorn app.main:app --reload --port $TESTBED_BACKEND_PORT
    stripe    → stripe listen --forward-to localhost:$TESTBED_BACKEND_PORT\\
                              $TESTBED_STRIPE_WEBHOOK_PATH
    frontend  → npm run dev   (optional; enabled with --with-frontend or env)

Seed helpers (run via the `seed` subcommand):

    scripts/seed_subscription_plans.py
    scripts/setup_admin_user.py
    scripts/create_indexes_p0.py

Config overlay:

    Repo-root `.env` is loaded first (same as the running app).
    `testbed/.env` overrides values, so testbed-only tunables don't bleed
    into the app config. See `testbed/.env.example` for the knobs.

Subcommand summary (run `testbed.py -h` for details):

    up         Start the tmux session and every enabled window. Idempotent.
    down       Kill the tmux session. Safe to run against an already-down session.
    restart    Restart one window (or all). Useful after editing requirements.txt.
    status     Print which windows are currently up.
    logs       Tail a service log file (non-interactive; use `attach` for tmux).
    attach     Attach to the tmux session for live interaction.
    seed       Run the seed scripts against the running backend / Mongo.
    preflight  Run Harness.preflight() to validate env + connectivity.
    doctor     Print env, tmux, docker, stripe CLI diagnostics.

House rule reminder from testbed/README.md: this CLI touches *real* Mongo and the
*real* Stripe test-mode account configured in your `.env`. Don't point it at a
live customer database.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover — surfaced by `doctor`
    load_dotenv = None  # type: ignore[assignment]

# ── Paths ────────────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
LOG_DIR = HERE / ".testbed" / "logs"
PID_DIR = HERE / ".testbed" / "pids"

BACKEND_WINDOW = "backend"
STRIPE_WINDOW = "stripe"
FRONTEND_WINDOW = "frontend"

WINDOW_ORDER = [BACKEND_WINDOW, STRIPE_WINDOW, FRONTEND_WINDOW]


# ── Output helpers ───────────────────────────────────────────────────────────


def _say(kind: str, msg: str, *, stream=sys.stdout) -> None:
    print(f"[{kind}] {msg}", file=stream, flush=True)


def info(msg: str) -> None:
    _say("INFO", msg)


def warn(msg: str) -> None:
    _say("WARN", msg, stream=sys.stderr)


def err(msg: str) -> None:
    _say("ERROR", msg, stream=sys.stderr)


# ── Config ───────────────────────────────────────────────────────────────────


class Config:
    """
    Merged config from repo-root `.env` + `testbed/.env`.

    The testbed overlay wins. We read env vars *after* both files have been
    loaded, so explicit shell exports still beat both files — same order as the
    Harness class, which is deliberate: a driver and this CLI must agree on
    which backend/Mongo they're talking to.
    """

    def __init__(self) -> None:
        self._load_dotenvs()
        self.session_name = os.getenv("TESTBED_SESSION_NAME", "testbed")
        self.backend_port = int(os.getenv("TESTBED_BACKEND_PORT", "8000"))
        self.frontend_port = int(os.getenv("TESTBED_FRONTEND_PORT", "3000"))
        self.frontend_origin = os.getenv(
            "TESTBED_FRONTEND_ORIGIN",
            f"http://127.0.0.1:{self.frontend_port}",
        ).rstrip("/")
        self.uvicorn_app = os.getenv("TESTBED_UVICORN_APP", "app.main:app")
        self.uvicorn_args = os.getenv("TESTBED_UVICORN_ARGS", "--reload")
        self.stripe_webhook_path = os.getenv(
            "TESTBED_STRIPE_WEBHOOK_PATH", "/stripe/webhook"
        )
        self.stripe_listen_extra = os.getenv("TESTBED_STRIPE_LISTEN_EXTRA", "")
        self.with_frontend = _truthy(os.getenv("TESTBED_WITH_FRONTEND"))
        self.frontend_cmd = os.getenv("TESTBED_FRONTEND_CMD", "npm run dev")
        frontend_node_env = os.getenv("TESTBED_FRONTEND_NODE_ENV")
        self.frontend_node_env = (
            frontend_node_env.strip()
            if frontend_node_env and frontend_node_env.strip()
            else None
        )
        self.google_maps_api_key = os.getenv("TESTBED_GOOGLE_MAPS_API_KEY")
        self.python_bin = os.getenv("TESTBED_PYTHON", sys.executable)

    # -- dotenv loading --------------------------------------------------------

    def _load_dotenvs(self) -> None:
        if load_dotenv is None:
            warn(
                "python-dotenv not installed; relying on the shell env only. "
                "Install with `pip install python-dotenv` or run `doctor`."
            )
            return
        # Repo-root first (source of truth for app secrets).
        root_env = REPO_ROOT / ".env"
        if root_env.exists():
            load_dotenv(root_env, override=False)
        # Testbed overlay — only touches keys set in this file.
        overlay = HERE / ".env"
        if overlay.exists():
            load_dotenv(overlay, override=True)

    # -- enabled windows ------------------------------------------------------

    def enabled_windows(self, *, include_frontend: Optional[bool] = None) -> list[str]:
        include = self.with_frontend if include_frontend is None else include_frontend
        wins = [BACKEND_WINDOW, STRIPE_WINDOW]
        if include:
            wins.append(FRONTEND_WINDOW)
        return wins


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


# ── Command building ─────────────────────────────────────────────────────────


def build_backend_cmd(cfg: Config) -> str:
    return (
        f"cd {shell_quote(str(REPO_ROOT))} && "
        f"FRONTEND_URL={shell_quote(cfg.frontend_origin)} "
        f"{shell_quote(cfg.python_bin)} -m uvicorn {cfg.uvicorn_app} "
        f"--host 0.0.0.0 --port {cfg.backend_port} {cfg.uvicorn_args}"
    )


def build_stripe_cmd(cfg: Config) -> str:
    extra = f" {cfg.stripe_listen_extra}" if cfg.stripe_listen_extra else ""
    return (
        f"stripe listen "
        f"--forward-to localhost:{cfg.backend_port}{cfg.stripe_webhook_path}"
        f"{extra}"
    )


def build_frontend_cmd(cfg: Config) -> str:
    environment = []
    frontend_node_env = getattr(cfg, "frontend_node_env", None)
    google_maps_api_key = getattr(cfg, "google_maps_api_key", None)
    backend_origin = f"http://127.0.0.1:{cfg.backend_port}"
    if frontend_node_env:
        environment.append(f"NODE_ENV={shell_quote(frontend_node_env)}")
    environment.append(f"FRONTEND_URL={shell_quote(cfg.frontend_origin)}")
    environment.append(f"BACKEND_SERVICE_URL={shell_quote(backend_origin)}")
    environment.append(f"INTERNAL_API_BASE_URL={shell_quote(backend_origin)}")
    if google_maps_api_key is not None:
        environment.append(f"GOOGLE_MAPS_API_KEY={shell_quote(google_maps_api_key)}")
    environment.append(f"PORT={cfg.frontend_port}")

    return (
        f"cd {shell_quote(str(REPO_ROOT))} && "
        f"{' '.join(environment)} {cfg.frontend_cmd}"
    )


def window_cmd(cfg: Config, window: str) -> str:
    if window == BACKEND_WINDOW:
        return build_backend_cmd(cfg)
    if window == STRIPE_WINDOW:
        return build_stripe_cmd(cfg)
    if window == FRONTEND_WINDOW:
        return build_frontend_cmd(cfg)
    raise ValueError(f"Unknown window: {window}")


def log_file(window: str) -> Path:
    return LOG_DIR / f"{window}.log"


def shell_quote(value: str) -> str:
    # Minimal quoting — enough for paths with spaces, not a full shell escape.
    if not value:
        return "''"
    if all(c.isalnum() or c in "-_./:@+=~" for c in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


# ── tmux driver ──────────────────────────────────────────────────────────────


def _tmux(
    *args: str, check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["tmux", *args],
        check=check,
        text=True,
        capture_output=capture,
    )


def tmux_available() -> bool:
    return shutil.which("tmux") is not None


def session_exists(session: str) -> bool:
    r = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True,
    )
    return r.returncode == 0


def list_windows(session: str) -> list[str]:
    if not session_exists(session):
        return []
    r = _tmux("list-windows", "-t", session, "-F", "#{window_name}", capture=True)
    return [line for line in r.stdout.splitlines() if line]


def window_exists(session: str, window: str) -> bool:
    return window in list_windows(session)


def pane_process_name(session: str, window: str) -> str:
    if not window_exists(session, window):
        return ""
    result = _tmux(
        "list-panes",
        "-t",
        f"{session}:{window}",
        "-F",
        "#{pane_current_command}",
        capture=True,
        check=False,
    )
    return next(
        (line.strip().lower() for line in result.stdout.splitlines() if line), ""
    )


def pane_process_names(session: str, window: str) -> set[str]:
    """Return the tmux pane command and every descendant process name."""

    if not window_exists(session, window):
        return set()
    pane = _tmux(
        "display-message",
        "-p",
        "-t",
        f"{session}:{window}.0",
        "#{pane_pid}",
        capture=True,
        check=False,
    )
    try:
        root_pid = int(pane.stdout.strip())
    except (TypeError, ValueError):
        return set()

    process_table = subprocess.run(
        ["ps", "-Ao", "pid=,ppid=,comm="],
        check=False,
        text=True,
        capture_output=True,
    )
    children: dict[int, list[tuple[int, str]]] = {}
    for line in process_table.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        try:
            pid, parent_pid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        children.setdefault(parent_pid, []).append((pid, Path(parts[2]).name.lower()))

    names: set[str] = set()
    pending = [root_pid]
    visited: set[int] = set()
    while pending:
        parent_pid = pending.pop()
        if parent_pid in visited:
            continue
        visited.add(parent_pid)
        for child_pid, name in children.get(parent_pid, []):
            names.add(name)
            pending.append(child_pid)
    current = pane_process_name(session, window)
    if current:
        names.add(current)
    return names


def _service_process_is_live(session: str, window: str) -> bool:
    processes = pane_process_names(session, window)
    if window == BACKEND_WINDOW:
        return any(
            process.startswith("python") or process == "uvicorn"
            for process in processes
        )
    if window == FRONTEND_WINDOW:
        return any(
            process in {"node", "npm"} or process.startswith("next")
            for process in processes
        )
    if window == STRIPE_WINDOW:
        return "stripe" in processes
    return False


def _http_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return 200 <= response.status < 400
    except (OSError, urllib.error.URLError):
        return False


def service_is_ready(cfg: Config, window: str) -> bool:
    if not _service_process_is_live(cfg.session_name, window):
        return False
    if window == BACKEND_WINDOW:
        return _http_ready(f"http://127.0.0.1:{cfg.backend_port}/health/readyz")
    if window == FRONTEND_WINDOW:
        return _http_ready(f"{cfg.frontend_origin}/")
    return True


def wait_for_service(cfg: Config, window: str, timeout_seconds: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if service_is_ready(cfg, window):
            return True
        time.sleep(0.5)
    return False


def kill_window(session: str, window: str) -> None:
    if window_exists(session, window):
        _tmux("kill-window", "-t", f"{session}:{window}", check=False)


def start_window(session: str, window: str, command: str) -> None:
    """
    Create the window if missing, pipe its pane to a log file, and run the
    command. Already-running windows are left alone — idempotent by design.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = log_file(window)
    # Wrap the command so the window survives a crash (shows the error instead
    # of disappearing). Matches the service-manager's "press Enter to close"
    # pattern for the scraper window.
    exit_notice = (
        f'; echo; echo "[testbed] {window} exited ($?). Press Enter to close."; read -r'
    )
    wrapped = f"bash -c {shell_quote(command + exit_notice)}"

    if not session_exists(session):
        _tmux("new-session", "-d", "-s", session, "-n", window, wrapped)
    elif window_exists(session, window):
        info(f"{window} window already running — leaving it alone")
        return
    else:
        _tmux("new-window", "-d", "-t", session, "-n", window, wrapped)

    # Small settle, then tee pane output to a log file.
    time.sleep(0.3)
    _tmux(
        "pipe-pane",
        "-t",
        f"{session}:{window}.0",
        f"cat >> {shell_quote(str(log))}",
        check=False,
    )


# ── Subcommands ──────────────────────────────────────────────────────────────


def cmd_up(cfg: Config, args: argparse.Namespace) -> int:
    if not tmux_available():
        err("tmux is required. Install via `brew install tmux` or apt equivalent.")
        return 2

    windows = cfg.enabled_windows(include_frontend=args.with_frontend)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_DIR.mkdir(parents=True, exist_ok=True)

    for window in windows:
        try:
            start_window(cfg.session_name, window, window_cmd(cfg, window))
            info(f"started {window} (log: {log_file(window)})")
        except subprocess.CalledProcessError as exc:
            err(f"failed to start {window}: {exc}")
            return 1

    for window in windows:
        if not wait_for_service(cfg, window):
            process = pane_process_name(cfg.session_name, window) or "missing"
            err(
                f"{window} failed readiness (pane process: {process}); "
                f"inspect {log_file(window)}"
            )
            return 1
        info(f"ready: {window}")

    info(
        f"session `{cfg.session_name}` ready. "
        f"Attach: tmux attach -t {cfg.session_name}   "
        f"Tear down: {Path(__file__).name} down"
    )
    return 0


def cmd_down(cfg: Config, args: argparse.Namespace) -> int:
    if not session_exists(cfg.session_name):
        info(f"no tmux session `{cfg.session_name}` running")
        return 0
    _tmux("kill-session", "-t", cfg.session_name, check=False)
    info(f"killed tmux session `{cfg.session_name}`")
    return 0


def cmd_restart(cfg: Config, args: argparse.Namespace) -> int:
    target = args.service
    windows = (
        [target] if target else cfg.enabled_windows(include_frontend=args.with_frontend)
    )

    for window in windows:
        if window not in WINDOW_ORDER:
            err(f"unknown service `{window}`. Known: {', '.join(WINDOW_ORDER)}")
            return 2
        kill_window(cfg.session_name, window)

    # tiny pause so kill settles before recreate
    time.sleep(0.3)

    for window in windows:
        start_window(cfg.session_name, window, window_cmd(cfg, window))
        info(f"restarted {window}")
        if not wait_for_service(cfg, window):
            err(f"{window} failed readiness after restart; inspect {log_file(window)}")
            return 1
    return 0


def cmd_status(cfg: Config, args: argparse.Namespace) -> int:
    if not session_exists(cfg.session_name):
        info(f"session `{cfg.session_name}` is down")
        return 1
    wins = list_windows(cfg.session_name)
    required_windows = set(cfg.enabled_windows())
    print(f"session `{cfg.session_name}` is up")
    unhealthy = False
    for window in WINDOW_ORDER:
        present = window in wins
        healthy = present and service_is_ready(cfg, window)
        mark = "✓" if healthy else "!" if present else "·"
        log = log_file(window)
        log_note = f" ({log})" if log.exists() else ""
        process_note = (
            f" process={pane_process_name(cfg.session_name, window) or 'missing'}"
            if present
            else ""
        )
        print(f"  {mark} {window}{process_note}{log_note}")
        unhealthy = unhealthy or (window in required_windows and not healthy)
        unhealthy = unhealthy or (present and not healthy)
    return 1 if unhealthy else 0


def cmd_logs(cfg: Config, args: argparse.Namespace) -> int:
    log = log_file(args.service)
    if not log.exists():
        err(f"no log at {log}. Has `{args.service}` been started?")
        return 1
    # Tail using the system `tail -f` so Ctrl-C behaves the way users expect.
    tail = shutil.which("tail")
    if tail is None:
        err("`tail` not found on PATH")
        return 2
    cmd = (
        [tail, "-n", str(args.tail), "-F", str(log)]
        if args.follow
        else [tail, "-n", str(args.tail), str(log)]
    )
    return subprocess.call(cmd)


def cmd_attach(cfg: Config, args: argparse.Namespace) -> int:
    if not session_exists(cfg.session_name):
        err(
            f"session `{cfg.session_name}` is down. "
            f"Run `{Path(__file__).name} up` first."
        )
        return 1
    os.execvp("tmux", ["tmux", "attach", "-t", cfg.session_name])
    return 0  # unreachable


# -- seed ---------------------------------------------------------------------

SEED_STEPS: list[tuple[str, list[str]]] = [
    # (label, argv) — relative paths resolved against REPO_ROOT.
    ("subscription plans", ["scripts/seed_subscription_plans.py"]),
    ("admin user", ["scripts/setup_admin_user.py"]),
    ("Mongo P0 indexes", ["scripts/create_indexes_p0.py"]),
]


def cmd_seed(cfg: Config, args: argparse.Namespace) -> int:
    skip = set(args.skip or [])
    for label, argv in SEED_STEPS:
        if label in skip:
            info(f"skip seed step: {label}")
            continue
        script = REPO_ROOT / argv[0]
        if not script.exists():
            warn(f"seed script missing — skipping {label} ({script})")
            continue
        info(f"seed: {label} → {script}")
        rc = subprocess.call(
            [cfg.python_bin, str(script), *argv[1:]],
            cwd=str(REPO_ROOT),
        )
        if rc != 0 and not args.keep_going:
            err(f"seed step `{label}` failed ({rc}); use --keep-going to continue")
            return rc
    info("seed complete")
    return 0


# -- preflight ----------------------------------------------------------------


def cmd_preflight(cfg: Config, args: argparse.Namespace) -> int:
    # Import lazily so doctor/up don't fail just because harness has a typo.
    sys.path.insert(0, str(HERE))
    try:
        from harness import Harness  # type: ignore
    except Exception as exc:  # pragma: no cover
        err(f"failed to import Harness: {exc}")
        return 1
    h = Harness(driver_name="testbed.preflight")
    try:
        h.preflight()
    except Exception as exc:
        err(f"preflight failed: {exc}")
        return 1
    info("preflight ok")
    return 0


# -- doctor -------------------------------------------------------------------


def cmd_doctor(cfg: Config, args: argparse.Namespace) -> int:
    print("testbed doctor")
    print("─" * 40)
    print(f"python            : {sys.executable} ({sys.version.split()[0]})")
    print(f"repo root         : {REPO_ROOT}")
    print(f"testbed dir       : {HERE}")
    print(f"log dir           : {LOG_DIR} (exists={LOG_DIR.exists()})")

    deps = {
        "tmux": shutil.which("tmux"),
        "stripe": shutil.which("stripe"),
        "docker": shutil.which("docker"),
        "npm": shutil.which("npm"),
        "tail": shutil.which("tail"),
    }
    print("deps:")
    for name, path in deps.items():
        mark = "✓" if path else "✗"
        print(f"  {mark} {name:8s} {path or '(missing)'}")

    print(f"dotenv loaded     : {load_dotenv is not None}")
    print(f"session name      : {cfg.session_name}")
    print(f"backend port      : {cfg.backend_port}")
    print(f"frontend port     : {cfg.frontend_port}")
    print(f"with frontend     : {cfg.with_frontend}")
    print(f"stripe webhook    : localhost:{cfg.backend_port}{cfg.stripe_webhook_path}")
    for key in ("STRIPE_SECRET_KEY", "MONGO_URI", "MONGODB_URI", "ROOT_ADMIN_PASSWORD"):
        present = "set" if os.getenv(key) else "missing"
        print(f"  env {key:22s} {present}")

    if session_exists(cfg.session_name):
        print(f"tmux session      : up ({', '.join(list_windows(cfg.session_name))})")
    else:
        print("tmux session      : down")
    return 0


# ── argparse wiring ──────────────────────────────────────────────────────────


def _add_with_frontend_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--with-frontend",
        dest="with_frontend",
        action="store_true",
        default=None,
        help="Also manage the Next.js frontend (overrides TESTBED_WITH_FRONTEND).",
    )
    p.add_argument(
        "--no-frontend",
        dest="with_frontend",
        action="store_false",
        help="Skip the Next.js frontend even if TESTBED_WITH_FRONTEND=1.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testbed.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(__doc__ or "").strip(),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_up = sub.add_parser(
        "up", help="Start backend + stripe listen (and optionally frontend)."
    )
    _add_with_frontend_flag(p_up)
    p_up.set_defaults(func=cmd_up)

    p_down = sub.add_parser("down", help="Kill the testbed tmux session.")
    p_down.set_defaults(func=cmd_down)

    p_restart = sub.add_parser("restart", help="Restart one service or all.")
    p_restart.add_argument("service", nargs="?", choices=WINDOW_ORDER, default=None)
    _add_with_frontend_flag(p_restart)
    p_restart.set_defaults(func=cmd_restart)

    p_status = sub.add_parser("status", help="Show tmux window status.")
    p_status.set_defaults(func=cmd_status)

    p_logs = sub.add_parser("logs", help="Tail a service log file.")
    p_logs.add_argument("service", choices=WINDOW_ORDER)
    p_logs.add_argument("-n", "--tail", type=int, default=200, help="Lines to show.")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Follow the log.")
    p_logs.set_defaults(func=cmd_logs)

    p_attach = sub.add_parser("attach", help="Attach to the testbed tmux session.")
    p_attach.set_defaults(func=cmd_attach)

    p_seed = sub.add_parser(
        "seed",
        help="Run shared seed scripts (subscription plans, admin user, Mongo indexes).",
    )
    p_seed.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Seed step label to skip (repeatable). Labels: "
        + ", ".join(label for label, _ in SEED_STEPS),
    )
    p_seed.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue past failing seed steps.",
    )
    p_seed.set_defaults(func=cmd_seed)

    p_pre = sub.add_parser(
        "preflight",
        help="Run Harness.preflight() — checks backend, Mongo, Stripe, admin auth.",
    )
    p_pre.set_defaults(func=cmd_preflight)

    p_doc = sub.add_parser("doctor", help="Print env + dep diagnostics.")
    p_doc.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    cfg = Config()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(cfg, args)
    except KeyboardInterrupt:
        warn("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
