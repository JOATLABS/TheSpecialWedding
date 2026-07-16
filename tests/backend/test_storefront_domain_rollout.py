from __future__ import annotations

from app.services.storefront_domain_rollout import StorefrontDomainRolloutPolicy


def test_rollout_defaults_to_fail_closed_exact_allowlist():
    policy = StorefrontDomainRolloutPolicy.build()

    assert policy.mode == "allowlist"
    assert policy.allows("planner-1", "www.customer.example") is False


def test_rollout_allows_exact_normalized_hostname_or_owner_only():
    policy = StorefrontDomainRolloutPolicy.build(
        mode="allowlist",
        hostnames=["BÜCHER.Example"],
        owner_ids=[" 507F1F77BCF86CD799439011 "],
    )

    assert policy.allows("other", "xn--bcher-kva.example") is True
    assert policy.allows("507f1f77bcf86cd799439011", "other.example") is True
    assert policy.allows("other", "shop.xn--bcher-kva.example") is False


def test_rollout_ignores_wildcards_and_invalid_values():
    policy = StorefrontDomainRolloutPolicy.build(
        mode="allowlist",
        hostnames=["*.example", "https://customer.example/path"],
        owner_ids=[""],
    )

    assert policy.hostnames == frozenset()
    assert policy.owner_ids == frozenset()
    assert policy.allows("planner-1", "www.example") is False


def test_rollout_requires_explicit_general_mode():
    invalid = StorefrontDomainRolloutPolicy.build(mode="unexpected")
    general = StorefrontDomainRolloutPolicy.build(mode="general")

    assert invalid.mode == "allowlist"
    assert invalid.allows("planner-1", "www.example") is False
    assert general.allows("planner-1", "www.example") is True
