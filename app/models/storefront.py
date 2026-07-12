"""Strict request and response contracts for planner storefronts."""

from __future__ import annotations

from datetime import datetime

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
