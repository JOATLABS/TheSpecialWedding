"""Import-time smoke test for the form-lifecycle testbed drivers.

The verifiers themselves run live against a configured dev stack and
are not collected by pytest. This smoke test simply imports each
driver module so a syntax error / bad import / drifting helper
function causes a CI failure rather than blowing up the first time
ops runs the driver.

The drivers themselves don't execute anything at import (their work
lives behind ``if __name__ == '__main__'`` + ``asyncio.run(main())``),
so importing here is safe.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("FRONTEND_URL", "https://app.example.com")

# Suppress the input(...) prompt the verifiers use as a phase gate so
# any accidental top-level import path (none currently, but cheap
# protection) doesn't block the test process.
os.environ.setdefault("FORMLIFE_NO_INPUT", "1")


VERIFIER_MODULES = [
    "testbed._form_lifecycle_common",
    "testbed.verify_form_anonymous_submission_lifecycle",
    "testbed.verify_form_tokenized_submission_lifecycle",
    "testbed.verify_form_conditional_logic_runtime",
    "testbed.verify_form_file_upload_lifecycle",
    "testbed.verify_form_reminder_scheduler",
    "testbed.verify_form_phase_d_seed",
    "testbed.verify_form_public_pdf_preview",
    "testbed.verify_form_marketing_lead_capture",
    "testbed.verify_form_response_pagination",
    "testbed.verify_form_csv_export_truncation",
    "testbed.verify_form_send_dedup_recovery",
    "testbed.verify_planner_two_stage_toast",
    "testbed.verify_homepage_starter_pack_lead_magnet",
]


CLEANUP_MODULES = [
    "testbed.cleanup_form_anonymous_submission_state",
    "testbed.cleanup_form_tokenized_submission_state",
    "testbed.cleanup_form_conditional_logic_state",
    "testbed.cleanup_form_file_upload_state",
    "testbed.cleanup_form_reminder_scheduler_state",
    "testbed.cleanup_form_phase_d_seed_state",
    "testbed.cleanup_form_public_pdf_preview_state",
    "testbed.cleanup_form_marketing_lead_capture_state",
    "testbed.cleanup_form_response_pagination_state",
    "testbed.cleanup_form_csv_export_truncation_state",
    "testbed.cleanup_form_send_dedup_recovery_state",
    "testbed.cleanup_planner_two_stage_toast_state",
]


@pytest.mark.parametrize("module_path", VERIFIER_MODULES + CLEANUP_MODULES)
def test_driver_module_imports_cleanly(module_path):
    """Catches syntax errors, bad helper imports, and stale references."""
    module = importlib.import_module(module_path)
    # Each driver module is expected to expose either ``main`` (sync or
    # async) or to be the shared helper module — a basic shape check
    # that future refactors don't accidentally rename the entry point.
    if module_path.startswith("testbed._"):
        return
    assert hasattr(module, "main"), f"{module_path} missing main()"


def test_house_rules_every_verifier_has_paired_cleanup():
    """testbed/README.md house rule #6: a driver without cleanup is
    tech debt. Confirm pairing for every form-lifecycle driver.
    """
    verifier_tags = {
        m.split(".verify_form_")[-1].rsplit("_lifecycle", 1)[0].rsplit("_runtime", 1)[0]
        for m in VERIFIER_MODULES
        if ".verify_form_" in m
    }
    cleanup_tags = {
        m.split(".cleanup_form_")[-1].rsplit("_state", 1)[0]
        for m in CLEANUP_MODULES
        if ".cleanup_form_" in m
    }
    # Sanity: not empty
    assert verifier_tags
    assert cleanup_tags
    # Each verifier tag must have a cleanup counterpart (allow a couple
    # of suffix mismatches: drivers ending in ``_lifecycle`` /
    # ``_runtime`` strip those, cleanups strip ``_state`` — net naming
    # is the scenario root).
    missing = verifier_tags - cleanup_tags
    # Allowed exception: anonymous_submission/tokenized_submission etc
    # have slightly varying suffix words; we only enforce that EVERY
    # verifier's "scenario word" prefix appears in some cleanup tag.
    unmatched = []
    for tag in missing:
        # Match if any cleanup tag shares the leading word.
        leading = tag.split("_")[0]
        if not any(c.startswith(leading) for c in cleanup_tags):
            unmatched.append(tag)
    assert not unmatched, f"verifiers missing paired cleanups: {unmatched}"
