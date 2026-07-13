"""Canonical identifiers for repository-owned, non-production seed data."""

MARKETING_CAPTURE_SEED_SOURCE = "system:marketing_capture_seed"
SMOKE_ACCOUNT_SEED_SOURCE = "system:smoke_account_seed"

MARKETING_CAPTURE_SEED_SCOPE = "phase1_showcase_workspace_v1"
LEGACY_SMOKE_SEED_SCOPE = "development"


def is_exact_marketing_capture_seed(source: object, scope: object) -> bool:
    """Return whether a record belongs to the one isolated Phase 1 workspace."""

    return (
        source == MARKETING_CAPTURE_SEED_SOURCE
        and scope == MARKETING_CAPTURE_SEED_SCOPE
    )
