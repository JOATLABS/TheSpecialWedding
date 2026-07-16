"""Root-admin request and receipt contracts for bounded domain resolutions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StorefrontDomainOperatorTarget(BaseModel):
    """Exact lifecycle row an operator reviewed before making a decision."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    planner_id: str = Field(min_length=1, max_length=120)
    hostname: str = Field(min_length=1, max_length=253)
    attempt_id: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    revision: int = Field(ge=0)
    reason: str = Field(min_length=10, max_length=1000)


class StorefrontO2OCutoverApprovalRequest(StorefrontDomainOperatorTarget):
    """Approve one ownership-verified Cloudflare O2O provider attempt."""


class StorefrontConflictResolutionRequest(StorefrontDomainOperatorTarget):
    """Close a verified conflict proof without transferring the hostname."""

    decision: Literal["denied", "cancelled"]


class StorefrontAmbiguousCreateAdoptionRequest(StorefrontDomainOperatorTarget):
    """Bind one independently observed Cloudflare ID to an ambiguous create."""

    provider_hostname_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class StorefrontDomainOperatorResolutionResponse(BaseModel):
    """Non-secret receipt returned after one bounded operator decision."""

    model_config = ConfigDict(extra="forbid")

    operation_id: str
    decision: Literal[
        "approved",
        "denied",
        "cancelled",
        "adopted",
    ]
    planner_id: str
    hostname: str
    attempt_id: str
    before_revision: int = Field(ge=0)
    after_revision: int = Field(ge=0)
    application_status: str
    provider_hostname_id: str | None = None
    completed_at: datetime


StorefrontDomainReviewType = Literal[
    "o2o_cutover",
    "ambiguous_create",
    "hostname_conflict",
    "investigation",
]
StorefrontDomainReviewAction = Literal[
    "approve_o2o_cutover",
    "adopt_ambiguous_create",
    "deny_hostname_conflict",
    "cancel_hostname_conflict",
]


class StorefrontDomainOperatorReviewSummary(BaseModel):
    """Bounded root-only queue row; review_id is the only lookup authority."""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    review_type: StorefrontDomainReviewType
    hostname: str
    application_status: str
    action: str
    revision: int = Field(ge=0)
    updated_at: datetime | None = None
    support_id: str | None = None
    allowed_actions: list[StorefrontDomainReviewAction]


class StorefrontDomainOperatorReviewListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[StorefrontDomainOperatorReviewSummary]
    has_more: bool


class StorefrontDomainOperatorReviewDetail(StorefrontDomainOperatorReviewSummary):
    """Exact owner/attempt/revision target loaded through an opaque review ID."""

    planner_id: str
    attempt_id: str
    intent: str | None = None
    ownership_status: str | None = None
    routing_dns_status: str | None = None
    provider_hostname_status: str | None = None
    ssl_status: str | None = None
    https_status: str | None = None
    authoritative_dns_provider: str | None = None
    authoritative_nameservers: list[str] = Field(default_factory=list)
    provider_candidate_ids: list[str] = Field(default_factory=list)
    provider_lookup_status: Literal[
        "not_required", "available", "unavailable", "invalid"
    ] = "not_required"
    provider_lookup_message: str | None = None
    provider_lookup_support_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    customer_action: str | None = None
