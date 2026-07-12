"""Strict request and response contracts for planner storefronts."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    ownership_verification: StorefrontOwnershipVerification | None
    ownership_verification_http: StorefrontOwnershipVerificationHttp | None
    ssl_validation_records: list[StorefrontSslValidationRecord]
    cname_target: str | None
    deletion_status: str | None
    last_error: str | None


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
    idempotency_key: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class StorefrontInquiryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    inquiry_id: str
    message: str
