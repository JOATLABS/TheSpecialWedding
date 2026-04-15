from datetime import datetime, timezone

from scripts.setup_smoke_accounts import build_smoke_seed_config, normalize_public_slug


def test_build_smoke_seed_config_uses_scoped_values_when_generic_absent():
    config = build_smoke_seed_config(
        {
            "ENVIRONMENT": "staging",
            "STAGING_SMOKE_ADMIN_EMAIL": "staging-admin@example.com",
            "STAGING_SMOKE_ADMIN_PASSWORD": "PlannerPass123!",  # pragma: allowlist secret
            "STAGING_SMOKE_COUPLE_EMAIL": "staging-couple@example.com",
            "STAGING_SMOKE_COUPLE_PASSWORD": "CouplePass123!",  # pragma: allowlist secret
            "STAGING_SMOKE_PUBLIC_WEDDING_SLUG": "Staging-Smoke-Wedding",
        },
        now=datetime(2026, 4, 14, tzinfo=timezone.utc),
    )

    assert config is not None
    assert config.scope == "staging"
    assert config.planner.email == "staging-admin@example.com"
    assert config.couple is not None
    assert config.couple.email == "staging-couple@example.com"
    assert config.wedding.slug == "Staging-Smoke-Wedding"


def test_build_smoke_seed_config_prefers_generic_over_scoped_values():
    config = build_smoke_seed_config(
        {
            "ENVIRONMENT": "staging",
            "SMOKE_ADMIN_EMAIL": "generic-admin@example.com",
            "SMOKE_ADMIN_PASSWORD": "GenericPass123!",  # pragma: allowlist secret
            "STAGING_SMOKE_ADMIN_EMAIL": "staging-admin@example.com",
            "STAGING_SMOKE_ADMIN_PASSWORD": "ScopedPass123!",  # pragma: allowlist secret
        },
        now=datetime(2026, 4, 14, tzinfo=timezone.utc),
    )

    assert config is not None
    assert config.planner.email == "generic-admin@example.com"
    assert config.planner.password == "GenericPass123!"  # pragma: allowlist secret


def test_build_smoke_seed_config_returns_none_without_planner_credentials():
    assert build_smoke_seed_config({"ENVIRONMENT": "staging"}) is None


def test_normalize_public_slug_accepts_full_url():
    assert (
        normalize_public_slug("https://staging.thespecialwedding.io/Emmanuel-Peace")
        == "Emmanuel-Peace"
    )
    assert normalize_public_slug("/Emmanuel-Peace") == "Emmanuel-Peace"
