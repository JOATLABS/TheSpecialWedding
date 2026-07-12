"""Canonical storefront feature names and validation boundaries."""

STOREFRONT_FEATURE = "planner_storefront"
CUSTOM_DOMAIN_FEATURE = "custom_domain"

SUPPORTED_STOREFRONT_FEATURES = frozenset(
    {
        STOREFRONT_FEATURE,
        CUSTOM_DOMAIN_FEATURE,
    }
)

RESERVED_STOREFRONT_SLUGS = frozenset(
    {
        "admin",
        "api",
        "assets",
        "billing",
        "custom-domain",
        "help",
        "login",
        "preview",
        "settings",
        "storefront",
        "support",
        "system",
        "the-special-wedding",
        "www",
    }
)
