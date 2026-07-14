"""Focused contracts for the production-like marketing-capture runtime.

These tests intentionally exercise the testbed orchestrator itself. The larger
marketing-workspace contract owns seeded product data and scene preflight; this
module owns only shell precedence, local service wiring, and runtime identity.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testbed import testbed as testbed_cli  # noqa: E402


def test_explicit_capture_shell_values_win_over_both_dotenv_files(
    monkeypatch, tmp_path
):
    repo_root = tmp_path / "repo"
    testbed_dir = repo_root / "testbed"
    testbed_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        "TESTBED_BACKEND_PORT=7000\n"
        "TESTBED_FRONTEND_PORT=7001\n"
        "TESTBED_FRONTEND_CMD=npm run dev\n"
        "TESTBED_FRONTEND_NODE_ENV=development\n"
        "TESTBED_GOOGLE_MAPS_API_KEY=root-key\n",
        encoding="utf-8",
    )
    (testbed_dir / ".env").write_text(
        "TESTBED_BACKEND_PORT=9000\n"
        "TESTBED_FRONTEND_PORT=9001\n"
        "TESTBED_FRONTEND_ORIGIN=http://127.0.0.1:9001\n"
        "TESTBED_FRONTEND_CMD=npm run dev\n"
        "TESTBED_FRONTEND_NODE_ENV=development\n"
        "TESTBED_GOOGLE_MAPS_API_KEY=overlay-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(testbed_cli, "REPO_ROOT", repo_root)
    monkeypatch.setattr(testbed_cli, "HERE", testbed_dir)

    shell_values = {
        "TESTBED_BACKEND_PORT": "8000",
        "TESTBED_FRONTEND_PORT": "3100",
        "TESTBED_FRONTEND_ORIGIN": "http://127.0.0.1:3100",
        "TESTBED_FRONTEND_CMD": "npm run start -- --hostname 127.0.0.1",
        "TESTBED_FRONTEND_NODE_ENV": "production",
        "TESTBED_GOOGLE_MAPS_API_KEY": "",
    }
    for key, value in shell_values.items():
        monkeypatch.setenv(key, value)

    cfg = testbed_cli.Config()

    assert cfg.backend_port == 8000
    assert cfg.frontend_port == 3100
    assert cfg.frontend_origin == "http://127.0.0.1:3100"
    assert cfg.frontend_cmd == "npm run start -- --hostname 127.0.0.1"
    assert cfg.frontend_node_env == "production"
    assert cfg.google_maps_api_key == ""


def test_capture_session_defaults_later_status_checks_to_the_canonical_origin(
    monkeypatch,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    testbed_dir = repo_root / "testbed"
    testbed_dir.mkdir(parents=True)
    monkeypatch.setattr(testbed_cli, "REPO_ROOT", repo_root)
    monkeypatch.setattr(testbed_cli, "HERE", testbed_dir)
    monkeypatch.setenv("TESTBED_SESSION_NAME", "marketing-capture")
    monkeypatch.delenv("TESTBED_FRONTEND_PORT", raising=False)
    monkeypatch.delenv("TESTBED_FRONTEND_ORIGIN", raising=False)
    monkeypatch.delenv("TESTBED_FRONTEND_NODE_ENV", raising=False)

    cfg = testbed_cli.Config()

    assert cfg.frontend_port == 3100
    assert cfg.frontend_origin == "http://127.0.0.1:3100"
    assert cfg.frontend_node_env is None


def test_capture_frontend_is_pinned_to_the_selected_local_backend(monkeypatch):
    monkeypatch.setenv("BACKEND_SERVICE_URL", "https://wrong.example.test")
    monkeypatch.setenv("INTERNAL_API_BASE_URL", "https://also-wrong.example.test")
    cfg = SimpleNamespace(
        backend_port=8123,
        frontend_port=3100,
        frontend_origin="http://127.0.0.1:3100",
        frontend_cmd="npm run start -- --hostname 127.0.0.1",
        frontend_node_env="production",
        google_maps_api_key="",
    )

    command = testbed_cli.build_frontend_cmd(cfg)

    assert "BACKEND_SERVICE_URL=http://127.0.0.1:8123" in command
    assert "INTERNAL_API_BASE_URL=http://127.0.0.1:8123" in command
    assert "wrong.example.test" not in command


def test_process_inspection_preserves_full_npm_command_lines(monkeypatch):
    monkeypatch.setattr(testbed_cli, "window_exists", lambda *_: True)
    monkeypatch.setattr(
        testbed_cli,
        "_tmux",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="123\n"
        ),
    )
    process_table = "\n".join(
        (
            "123 1 bash -c run-the-frontend",
            "124 123 npm run start -- --hostname 127.0.0.1",
            "125 124 next-server (v16.2.7)",
            "900 1 npm run dev",
        )
    )
    monkeypatch.setattr(
        testbed_cli.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout=process_table
        ),
    )

    assert testbed_cli.pane_process_commands(
        "marketing-capture", testbed_cli.FRONTEND_WINDOW
    ) == {
        "npm run start -- --hostname 127.0.0.1",
        "next-server (v16.2.7)",
    }


@pytest.mark.parametrize(
    "commands",
    [
        {"npm run start --hostname 127.0.0.1"},
        {"node node_modules/next/dist/bin/next start --hostname 127.0.0.1"},
    ],
)
def test_production_frontend_readiness_accepts_next_start(monkeypatch, commands):
    cfg = SimpleNamespace(
        session_name="ordinary-production-testbed",
        frontend_node_env="production",
        frontend_origin="http://127.0.0.1:3000",
    )
    monkeypatch.setattr(testbed_cli, "_service_process_is_live", lambda *_: True)
    monkeypatch.setattr(
        testbed_cli, "pane_process_commands", lambda *_: commands, raising=False
    )
    monkeypatch.setattr(testbed_cli, "_http_ready", lambda _url: True)

    assert testbed_cli.service_is_ready(cfg, testbed_cli.FRONTEND_WINDOW)


def test_canonical_capture_requires_next_start_without_transient_node_env(monkeypatch):
    cfg = SimpleNamespace(
        session_name="marketing-capture",
        frontend_node_env=None,
        frontend_origin="http://127.0.0.1:3100",
    )
    monkeypatch.setattr(testbed_cli, "_service_process_is_live", lambda *_: True)
    monkeypatch.setattr(
        testbed_cli,
        "pane_process_commands",
        lambda *_: {"npm run dev -- --hostname 127.0.0.1"},
        raising=False,
    )
    monkeypatch.setattr(testbed_cli, "_http_ready", lambda _url: True)

    assert not testbed_cli.service_is_ready(cfg, testbed_cli.FRONTEND_WINDOW)


def test_canonical_capture_requires_node_22_without_transient_node_env(monkeypatch):
    cfg = SimpleNamespace(
        session_name="marketing-capture",
        frontend_node_env=None,
        frontend_origin="http://127.0.0.1:3100",
    )
    monkeypatch.setattr(testbed_cli, "_service_process_is_live", lambda *_: True)
    monkeypatch.setattr(
        testbed_cli,
        "pane_process_commands",
        lambda *_: {"npm run start -- --hostname 127.0.0.1"},
        raising=False,
    )
    monkeypatch.setattr(
        testbed_cli,
        "_frontend_process_uses_node_22",
        lambda *_: False,
        raising=False,
    )
    monkeypatch.setattr(testbed_cli, "_http_ready", lambda _url: True)

    assert not testbed_cli.service_is_ready(cfg, testbed_cli.FRONTEND_WINDOW)


def test_capture_node_check_uses_every_running_next_process(monkeypatch):
    runtime_check = getattr(testbed_cli, "_frontend_process_uses_node_22", None)
    assert callable(runtime_check), (
        "capture readiness needs a running-process Node check"
    )
    monkeypatch.setattr(
        testbed_cli,
        "_pane_descendant_processes",
        lambda *_: [
            (124, "npm", "npm run start -- --hostname 127.0.0.1"),
            (125, "next-server", "next-server (v16.2.7)"),
            (126, "bash", "bash -c echo npm run start"),
        ],
    )
    versions = {124: 22, 125: 22}
    monkeypatch.setattr(
        testbed_cli,
        "_node_major_version_for_process",
        lambda pid: versions.get(pid),
        raising=False,
    )

    assert runtime_check("marketing-capture") is True
    versions[125] = 24
    assert runtime_check("marketing-capture") is False


def test_production_frontend_readiness_rejects_next_dev_even_when_http_is_ready(
    monkeypatch,
):
    cfg = SimpleNamespace(
        session_name="marketing-capture",
        frontend_node_env="production",
        frontend_origin="http://127.0.0.1:3100",
    )
    monkeypatch.setattr(testbed_cli, "_service_process_is_live", lambda *_: True)
    monkeypatch.setattr(
        testbed_cli,
        "pane_process_commands",
        lambda *_: {"node node_modules/next/dist/bin/next dev --webpack"},
        raising=False,
    )
    monkeypatch.setattr(testbed_cli, "_http_ready", lambda _url: True)

    assert not testbed_cli.service_is_ready(cfg, testbed_cli.FRONTEND_WINDOW)


def test_development_frontend_readiness_does_not_require_next_start(monkeypatch):
    cfg = SimpleNamespace(
        session_name="ordinary-testbed",
        frontend_node_env=None,
        frontend_origin="http://127.0.0.1:3000",
    )
    monkeypatch.setattr(testbed_cli, "_service_process_is_live", lambda *_: True)
    monkeypatch.setattr(testbed_cli, "_http_ready", lambda _url: True)

    assert testbed_cli.service_is_ready(cfg, testbed_cli.FRONTEND_WINDOW)


def test_status_names_a_non_production_frontend_runtime(monkeypatch, capsys):
    cfg = SimpleNamespace(
        session_name="marketing-capture",
        with_frontend=True,
        frontend_node_env=None,
        frontend_origin="http://127.0.0.1:3100",
        enabled_windows=lambda: [testbed_cli.FRONTEND_WINDOW],
    )
    monkeypatch.setattr(testbed_cli, "session_exists", lambda _session: True)
    monkeypatch.setattr(
        testbed_cli, "list_windows", lambda _session: [testbed_cli.FRONTEND_WINDOW]
    )
    monkeypatch.setattr(testbed_cli, "_service_process_is_live", lambda *_: True)
    monkeypatch.setattr(
        testbed_cli,
        "pane_process_commands",
        lambda *_: {"npm run dev -- --hostname 127.0.0.1"},
        raising=False,
    )
    monkeypatch.setattr(testbed_cli, "_http_ready", lambda _url: True)
    monkeypatch.setattr(testbed_cli, "pane_process_name", lambda *_: "node")

    assert testbed_cli.cmd_status(cfg, SimpleNamespace()) == 1
    assert "runtime=not-next-start" in capsys.readouterr().out


def test_status_rejects_non_node_22_capture_runtime_without_transient_env(
    monkeypatch,
    capsys,
):
    cfg = SimpleNamespace(
        session_name="marketing-capture",
        with_frontend=True,
        frontend_node_env=None,
        frontend_origin="http://127.0.0.1:3100",
        enabled_windows=lambda: [testbed_cli.FRONTEND_WINDOW],
    )
    monkeypatch.setattr(testbed_cli, "session_exists", lambda _session: True)
    monkeypatch.setattr(
        testbed_cli, "list_windows", lambda _session: [testbed_cli.FRONTEND_WINDOW]
    )
    monkeypatch.setattr(testbed_cli, "_service_process_is_live", lambda *_: True)
    monkeypatch.setattr(
        testbed_cli,
        "pane_process_commands",
        lambda *_: {"npm run start -- --hostname 127.0.0.1"},
        raising=False,
    )
    monkeypatch.setattr(
        testbed_cli,
        "_frontend_process_uses_node_22",
        lambda *_: False,
        raising=False,
    )
    monkeypatch.setattr(testbed_cli, "_http_ready", lambda _url: True)
    monkeypatch.setattr(testbed_cli, "pane_process_name", lambda *_: "node")

    assert testbed_cli.cmd_status(cfg, SimpleNamespace()) == 1
    output = capsys.readouterr().out
    assert "runtime=next-start" in output
    assert "node=not-node-22" in output
