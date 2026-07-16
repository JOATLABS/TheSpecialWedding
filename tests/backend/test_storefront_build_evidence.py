"""Tests for production frontend source/build binding."""

from __future__ import annotations

from pathlib import Path
import subprocess

from testbed.storefront_build_evidence import (
    frontend_source_evidence,
    storefront_evidence_source_evidence,
)


def _git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=repo, check=True, capture_output=True)


def test_frontend_source_evidence_changes_for_tracked_and_untracked_inputs(tmp_path):
    _git(tmp_path, "init", "--quiet")
    (tmp_path / "app").mkdir()
    source = tmp_path / "app" / "page.tsx"
    source.write_text(
        "export default function Page() { return null }\n", encoding="utf-8"
    )
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", "app/page.tsx", "package.json")

    first = frontend_source_evidence(tmp_path)
    source.write_text(
        "export default function Page() { return <main /> }\n", encoding="utf-8"
    )
    second = frontend_source_evidence(tmp_path)
    untracked = tmp_path / "app" / "new.ts"
    untracked.write_text("export const value = 1\n", encoding="utf-8")
    third = frontend_source_evidence(tmp_path)

    assert first["frontend_source_sha256"] != second["frontend_source_sha256"]
    assert second["frontend_source_sha256"] != third["frontend_source_sha256"]
    assert third["frontend_source_file_count"] == 3


def test_frontend_source_evidence_ignores_generated_tsbuildinfo(tmp_path):
    _git(tmp_path, "init", "--quiet")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "page.tsx").write_text("export default 1\n", encoding="utf-8")
    (tmp_path / "tsconfig.tsbuildinfo").write_text("generated\n", encoding="utf-8")

    evidence = frontend_source_evidence(tmp_path)

    assert "tsconfig.tsbuildinfo" not in evidence["frontend_source_files"]


def test_storefront_evidence_source_hash_binds_untracked_testbed_driver_bytes(tmp_path):
    _git(tmp_path, "init", "--quiet")
    testbed = tmp_path / "testbed"
    testbed.mkdir()
    driver = testbed / "verify_storefront_frontend_lifecycle.py"
    driver.write_text("RUN_ID = 'first'\n", encoding="utf-8")

    first = storefront_evidence_source_evidence(tmp_path)
    driver.write_text("RUN_ID = 'second'\n", encoding="utf-8")
    second = storefront_evidence_source_evidence(tmp_path)

    assert (
        first["storefront_evidence_source_sha256"]
        != second["storefront_evidence_source_sha256"]
    )
    assert second["storefront_evidence_source_file_count"] == 1
    assert (
        "testbed/verify_storefront_frontend_lifecycle.py"
        in second["storefront_evidence_source_files"]
    )
