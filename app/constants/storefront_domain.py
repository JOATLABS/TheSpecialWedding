"""Canonical application phases for the storefront custom-domain lifecycle."""

from __future__ import annotations

from typing import Final


# Cloudflare requests use a ten-second HTTP timeout. The wider, immutable
# two-minute evidence window allows for provider-side completion after a lost
# response while ensuring an unrelated hostname created later cannot be
# adopted into the original attempt.
PROVIDER_CREATE_REQUEST_WINDOW_SECONDS: Final = 120
STOREFRONT_DOMAIN_INSTRUCTIONS_EMAIL_TYPE: Final = "storefront_domain_instructions"

SETUP_CANCELLED: Final = "setup_cancelled"
DOMAIN_DISCONNECTED: Final = "domain_disconnected"
OWNERSHIP_REVIEW_CANCELLED: Final = "ownership_review_cancelled"
STOREFRONT_DOMAIN_REMOVAL_KINDS: Final[frozenset[str]] = frozenset(
    {SETUP_CANCELLED, DOMAIN_DISCONNECTED, OWNERSHIP_REVIEW_CANCELLED}
)

CLAIM_PENDING: Final = "claim_pending"
AUTHORIZATION_PENDING: Final = "authorization_pending"
AUTHORIZATION_CANCELLED: Final = "authorization_cancelled"
DNS_SETUP_PENDING: Final = "dns_setup_pending"
MIGRATION_PREVALIDATION: Final = "migration_prevalidation"
CUTOVER_READY: Final = "cutover_ready"
PROVIDER_PROVISIONING: Final = "provider_provisioning"
HOSTNAME_VALIDATION: Final = "hostname_validation"
CERTIFICATE_VALIDATION: Final = "certificate_validation"
DEPLOYING: Final = "deploying"
ACTIVE: Final = "active"
ACTION_REQUIRED: Final = "action_required"
OPERATOR_REVIEW: Final = "operator_review"
DISCONNECTING: Final = "disconnecting"
DISCONNECT_FAILED: Final = "disconnect_failed"
DISCONNECTED: Final = "disconnected"
EXPIRED: Final = "expired"

STOREFRONT_DOMAIN_APPLICATION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        CLAIM_PENDING,
        AUTHORIZATION_PENDING,
        AUTHORIZATION_CANCELLED,
        DNS_SETUP_PENDING,
        MIGRATION_PREVALIDATION,
        CUTOVER_READY,
        PROVIDER_PROVISIONING,
        HOSTNAME_VALIDATION,
        CERTIFICATE_VALIDATION,
        DEPLOYING,
        ACTIVE,
        ACTION_REQUIRED,
        OPERATOR_REVIEW,
        DISCONNECTING,
        DISCONNECT_FAILED,
        DISCONNECTED,
        EXPIRED,
    }
)


def require_storefront_domain_application_status(value: str) -> str:
    """Fail at the write boundary when a developer invents a new phase."""

    if value not in STOREFRONT_DOMAIN_APPLICATION_STATUSES:
        raise ValueError(f"Unsupported storefront domain application status: {value}")
    return value
