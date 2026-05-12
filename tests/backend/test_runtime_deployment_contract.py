from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_bootstrap_runtime():
    spec = importlib.util.spec_from_file_location(
        "bootstrap_runtime_under_test",
        PROJECT_ROOT / "scripts" / "bootstrap_runtime.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dockerfile_instructions(source: str) -> list[str]:
    instructions: list[str] = []
    current: list[str] = []

    for raw_line in source.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not current and (not stripped or stripped.startswith("#")):
            continue

        current.append(line)
        if stripped.endswith("\\"):
            continue

        instructions.append("\n".join(current))
        current = []

    if current:
        instructions.append("\n".join(current))

    return instructions


def test_seed_subscription_script_import_contract_without_pythonpath():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["SEED_SUBSCRIPTION_PLANS_IMPORT_CHECK_ONLY"] = "1"

    result = subprocess.run(
        [sys.executable, "scripts/seed_subscription_plans.py"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "[OK] seed subscription import contract satisfied" in result.stdout


def test_runtime_bootstrap_exports_project_root_to_child_pythonpath(monkeypatch):
    bootstrap_runtime = _load_bootstrap_runtime()

    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})

    monkeypatch.setattr(bootstrap_runtime.subprocess, "run", fake_run)
    monkeypatch.setenv("PYTHONPATH", "/existing/pythonpath")

    assert bootstrap_runtime.main() == 0

    assert len(calls) == len(bootstrap_runtime.COMMANDS)
    for call in calls:
        assert call["cwd"] == bootstrap_runtime.ROOT
        assert call["check"] is True
        env = call["env"]
        assert isinstance(env, dict)
        pythonpath = env["PYTHONPATH"].split(os.pathsep)
        assert pythonpath[0] == str(bootstrap_runtime.ROOT)
        assert "/existing/pythonpath" in pythonpath[1:]


def test_frontend_dockerfile_prunes_next_cache_before_runtime_copy():
    source = (PROJECT_ROOT / "Dockerfile.frontend").read_text()
    instructions = _dockerfile_instructions(source)

    build_run_index = next(
        index
        for index, instruction in enumerate(instructions)
        if instruction.lstrip().startswith("RUN ") and "npm run build" in instruction
    )
    runtime_copy_index = next(
        index
        for index, instruction in enumerate(instructions)
        if instruction.strip() == "COPY --from=builder /app/.next ./.next"
    )

    build_run = instructions[build_run_index]
    assert ".next/cache" in build_run
    assert "rm -rf" in build_run
    assert build_run_index < runtime_copy_index
    assert "standalone output" not in source
