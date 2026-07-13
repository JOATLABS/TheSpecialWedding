"""Canonical storefront feature names and validation boundaries."""

STOREFRONT_FEATURE = "planner_storefront"
CUSTOM_DOMAIN_FEATURE = "custom_domain"
PENDING_ASSET_GROUP_FIELD = "pending_asset_group"
PENDING_ASSET_RECOVERY_STATUS_FIELD = "pending_asset_recovery_status"
PENDING_ASSET_RECOVERY_TOKEN_FIELD = "pending_asset_recovery_token"
PENDING_ASSET_RECOVERY_LEASE_FIELD = "pending_asset_recovery_lease_expires_at"
PENDING_ASSET_RECOVERY_DUE_FIELD = "pending_asset_recovery_due_at"
PENDING_ASSET_RECOVERY_ERROR_FIELD = "pending_asset_recovery_error"
PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD = "pending_asset_recovery_attempts"
PENDING_ASSET_RECOVERY_FIELDS = frozenset(
    {
        PENDING_ASSET_RECOVERY_STATUS_FIELD,
        PENDING_ASSET_RECOVERY_TOKEN_FIELD,
        PENDING_ASSET_RECOVERY_LEASE_FIELD,
        PENDING_ASSET_RECOVERY_DUE_FIELD,
        PENDING_ASSET_RECOVERY_ERROR_FIELD,
        PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD,
    }
)

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
