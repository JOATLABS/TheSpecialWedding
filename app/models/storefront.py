"""Strict request and response contracts for planner storefronts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class StorefrontSettingsUpdate(BaseModel):
    """Allowlisted planner-authored settings.

    Provider state and direct image URLs intentionally do not belong to this
    model. Media and custom domains have dedicated lifecycle endpoints.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str | None = Field(default=None, max_length=128)
    title: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    hero_asset_id: str | None = Field(default=None, max_length=120)
    about_asset_id: str | None = Field(default=None, max_length=120)
    theme_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    packages_enabled: bool | None = None
    reviews_enabled: bool | None = None
    is_published: bool | None = None


class StorefrontAccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str | None
    storefront_enabled: bool
    custom_domain_enabled: bool
    can_manage_existing_domain: bool


class StorefrontProviderReadinessResponse(BaseModel):
    """Non-secret attestation used before any provider-mutating verification."""

    model_config = ConfigDict(extra="forbid")

    image_uploads_configured: bool
    custom_domains_configured: bool
    runtime_revision: str | None = None


class StorefrontSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str | None
    description: str | None
    contact_email: EmailStr | None
    contact_phone: str | None
    hero_asset_id: str | None
    about_asset_id: str | None
    theme_color: str
    packages_enabled: bool
    reviews_enabled: bool
    is_published: bool
    published_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    revision: int = Field(ge=0)
    slug_editable: bool
    slug_persisted: bool


class StorefrontSettingsEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: StorefrontSettingsResponse | None


class StorefrontSettingsUpdateEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    settings: StorefrontSettingsResponse


class StorefrontDomainConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    domain: str = Field(min_length=1, max_length=253)


class StorefrontDomainPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    domain: str = Field(min_length=1, max_length=253)
    intent: Literal["new", "migration"] = "new"


class StorefrontDomainClaimRequest(StorefrontDomainPreflightRequest):
    pass


class StorefrontDomainVerifyRequest(BaseModel):
    """Verification has no caller-supplied proof; DNS is observed independently."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    attempt_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class StorefrontDomainAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    attempt_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")


class StorefrontDomainConnectAuthorizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_url: str
    attempt_id: str


class StorefrontDomainInstructionRequest(StorefrontDomainAttemptRequest):
    email: EmailStr
    note: str | None = Field(default=None, max_length=1000)


class StorefrontDomainInstructionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["sent"]
    link_id: str
    state: Literal["active", "delivery_pending", "delivery_failed"]
    created_at: datetime
    expires_at: datetime
    recipient_hint: str


class StorefrontDomainInstructionLinkSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: str
    state: Literal["active", "delivery_pending", "delivery_failed"]
    created_at: datetime
    expires_at: datetime
    recipient_hint: str


class StorefrontDomainInstructionLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    links: list[StorefrontDomainInstructionLinkSummary]


class StorefrontDomainInstructionRevokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["revoked"]


class StorefrontDomainInstructionProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    zone: str
    control_panel_url: HttpUrl | None = None


class StorefrontDomainInstructionPublicResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    records: list[StorefrontDnsRecord]
    provider: StorefrontDomainInstructionProvider | None = None
    note: str | None = None
    expires_at: datetime


class StorefrontDnsRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["NS", "A", "AAAA", "CNAME", "CAA", "TXT"]
    name: str
    value: str | None = None
    values: list[str] | None = None
    ttl: int | None = None
    purpose: str | None = None
    relative_host: str | None = None
    proxy: Literal["dns_only", "proxied", "provider_default"] | None = None


class StorefrontDnsConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    record_type: str
    values: list[str]
    message: str | None = None


class StorefrontAuthoritativeDnsEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone: str
    provider: str
    provider_name: str | None = None
    control_panel_url: str | None = None
    nameservers: list[str]


class StorefrontDomainPreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    host_type: Literal["apex", "subdomain"]
    intent: Literal["new", "migration"]
    authoritative_dns: StorefrontAuthoritativeDnsEvidence
    observed_records: list[StorefrontDnsRecord]
    conflicts: list[StorefrontDnsConflict]
    expected_records: list[StorefrontDnsRecord]
    domain_connect_supported: bool = False
    domain_connect_provider: str | None = None
    registrar: str | None = None
    platform_provider: str | None = None
    recommended_flow: Literal["automatic", "manual", "assisted_migration"]
    self_service_allowed: bool = True
    customer_action: str | None = None


class StorefrontDomainErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    customer_action: str
    retryable: bool
    support_id: str
    field: str | None = None
    provider: dict[str, Any] | None = None


class StorefrontOwnershipVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str | None = None
    name: str | None = None
    value: str | None = None


class StorefrontOwnershipVerificationHttp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    http_url: str | None = None
    http_body: str | None = None


class StorefrontSslValidationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    txt_name: str | None = None
    txt_value: str | None = None
    cname_name: str | None = None
    cname_target: str | None = None


class StorefrontDomainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    status: str
    provider_status: str
    ssl_status: str
    application_status: Literal[
        "claim_pending",
        "authorization_pending",
        "authorization_cancelled",
        "dns_setup_pending",
        "migration_prevalidation",
        "cutover_ready",
        "provider_provisioning",
        "hostname_validation",
        "certificate_validation",
        "deploying",
        "active",
        "action_required",
        "operator_review",
        "disconnecting",
        "disconnect_failed",
        "disconnected",
        "expired",
    ] = "claim_pending"
    ownership_status: str = "pending"
    provider_hostname_status: str = "pending"
    routing_dns_status: str = "pending"
    https_status: str = "pending"
    action: str = "action_required"
    provider_hostname_id: str | None = None
    attempt_id: str | None = None
    revision: int = Field(default=0, ge=0)
    claim_expires_at: datetime | None = None
    intent: Literal["new", "migration"] = "new"
    authoritative_dns: StorefrontAuthoritativeDnsEvidence | None = None
    observed_records: list[StorefrontDnsRecord] = Field(default_factory=list)
    conflicts: list[StorefrontDnsConflict] = Field(default_factory=list)
    cleanup_records: list[StorefrontDnsRecord] = Field(default_factory=list)
    domain_connect_supported: bool = False
    domain_connect_provider: str | None = None
    registrar: str | None = None
    platform_provider: str | None = None
    conflict_code: str | None = None
    last_checked_at: datetime | None = None
    next_check_at: datetime | None = None
    expected_records: list[StorefrontDnsRecord] = Field(default_factory=list)
    ownership_verification: StorefrontOwnershipVerification | None = None
    ownership_verification_http: StorefrontOwnershipVerificationHttp | None = None
    ssl_validation_records: list[StorefrontSslValidationRecord] = Field(
        default_factory=list
    )
    provider_verification_errors: list[str] = Field(default_factory=list)
    ssl_validation_errors: list[str] = Field(default_factory=list)
    cname_target: str | None = None
    deletion_status: str | None = None
    last_error: StorefrontDomainErrorDetail | str | None = None


class StorefrontDomainDisconnectResponse(BaseModel):
    """Body-bearing confirmation that avoids ambiguous 204 proxy aborts."""

    model_config = ConfigDict(extra="forbid")

    application_status: Literal["disconnected"] = "disconnected"
    attempt_id: str | None = None


class StorefrontDomainHttpsProbeResponse(BaseModel):
    """Opaque proof that one exact domain lifecycle row reached our origin."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1"]
    hostname: str
    revision: int = Field(ge=0)
    nonce: str
    domain_binding: str
    proof: str


class StorefrontUploadCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: str = Field(min_length=1, max_length=120)


class StorefrontUploadReservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    upload_url: str
    cdn_url: str
    key: str
    max_size_bytes: int = Field(gt=0)


class StorefrontAssetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    slot: str
    state: str
    key: str
    cdn_url: str
    content_type: str
    size_bytes: int = Field(gt=0)


class StorefrontAssetDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    asset_id: str


class PublicStorefrontSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None
    description: str | None
    contact_email: EmailStr | None
    contact_phone: str | None
    hero_image_url: str | None
    about_image_url: str | None
    theme_color: str
    packages_enabled: bool
    reviews_enabled: bool


class PublicPlanner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None
    first_name: str | None
    profile_image_url: str | None


class PublicPackageService(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None


class PublicPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(alias="_id", serialization_alias="_id")
    name: str
    description: str | None
    total_amount: float
    currency: str
    services: list[PublicPackageService]


class PublicReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(alias="_id", serialization_alias="_id")
    author_name: str | None
    rating: float | None
    text: str | None
    source: str | None
    date: str | datetime | None


class PublicStorefrontResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    storefront: PublicStorefrontSettings
    planner: PublicPlanner
    packages: list[PublicPackage]
    reviews: list[PublicReview]


class StorefrontInquiryRequest(BaseModel):
    """Allowlisted public lead fields; owner identity is always server-derived."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    wedding_date: date | None = None
    message: str = Field(min_length=1, max_length=4000)
    idempotency_key: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class StorefrontInquiryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    inquiry_id: str
    message: str
