"""Deterministic source identity for the storefront production frontend build."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
from typing import Any


FRONTEND_BUILD_INPUTS = (
    "app",
    "public",
    "scripts",
    "package.json",
    "package-lock.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "proxy.ts",
    "tsconfig.json",
)

STOREFRONT_EVIDENCE_INPUTS = (
    "testbed/build_storefront_frontend.py",
    "testbed/cleanup_storefront_frontend_lifecycle_state.py",
    "testbed/playwright.storefront.config.ts",
    "testbed/storefront_build_evidence.py",
    "testbed/storefront_configuration_doctor.py",
    "testbed/storefront_frontend_lifecycle.spec.ts",
    "testbed/storefront_https_proxy.mjs",
    "testbed/storefront_provider_harness.py",
    "testbed/storefront_provider_harness_core.py",
    "testbed/serve_storefront_visible_playback.py",
    "testbed/storefront_browser_facade.mjs",
    "testbed/storefront_testbed_safety.py",
    "testbed/validate_storefront_domain_connect_template.py",
    "testbed/verify_storefront_frontend_lifecycle.py",
)


def _source_evidence(
    repo_root: Path,
    *,
    inputs: tuple[str, ...],
    result_prefix: str,
) -> dict[str, Any]:
    command = [
        "git",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        *inputs,
    ]
    listed = subprocess.check_output(command, cwd=repo_root, text=True).splitlines()
    paths = sorted(
        {
            path
            for path in listed
            if path
            and not path.endswith("tsconfig.tsbuildinfo")
            and (repo_root / path).is_file()
        }
    )
    digest = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for relative in paths:
        content = (repo_root / relative).read_bytes()
        file_hash = hashlib.sha256(content).hexdigest()
        file_hashes[relative] = file_hash
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_hash))
    return {
        f"{result_prefix}_sha256": digest.hexdigest(),
        f"{result_prefix}_file_count": len(paths),
        f"{result_prefix}_files": file_hashes,
    }


def frontend_source_evidence(repo_root: Path) -> dict[str, Any]:
    """Hash every tracked or untracked, non-ignored frontend build input.

    The hash includes relative paths as well as bytes, so a stale `.next` build
    cannot be accepted after a source edit, rename, addition, or deletion.
    """

    return _source_evidence(
        repo_root,
        inputs=FRONTEND_BUILD_INPUTS,
        result_prefix="frontend_source",
    )


def storefront_evidence_source_evidence(repo_root: Path) -> dict[str, Any]:
    """Hash the exact storefront testbed and evidence implementation.

    These files are deliberately included even while untracked. A run cannot
    inherit a backend runtime revision from one verifier implementation while
    its receipts were produced or parsed by another.
    """

    return _source_evidence(
        repo_root,
        inputs=STOREFRONT_EVIDENCE_INPUTS,
        result_prefix="storefront_evidence_source",
    )
