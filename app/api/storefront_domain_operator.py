"""Root-admin-only storefront custom-domain review queue and decisions."""

from fastapi import APIRouter, Depends, Path, Query

from app.dependencies.auth_extended import ExtendedAuthUser, require_root_admin
from app.models.storefront_domain_operator import (
    StorefrontAmbiguousCreateAdoptionRequest,
    StorefrontConflictResolutionRequest,
    StorefrontDomainOperatorResolutionResponse,
    StorefrontDomainOperatorReviewDetail,
    StorefrontDomainOperatorReviewListResponse,
    StorefrontO2OCutoverApprovalRequest,
)
from app.services.storefront_domain_operator_service import (
    storefront_domain_operator_service,
)


router = APIRouter(prefix="/storefront/custom-domain/operator")


@router.get(
    "/reviews",
    response_model=StorefrontDomainOperatorReviewListResponse,
)
async def list_storefront_domain_reviews(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    return await storefront_domain_operator_service.list_reviews(
        current_user,
        limit=limit,
    )


@router.get(
    "/reviews/{review_id}",
    response_model=StorefrontDomainOperatorReviewDetail,
)
async def get_storefront_domain_review(
    review_id: str = Path(
        min_length=16,
        max_length=240,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    return await storefront_domain_operator_service.get_review(
        current_user,
        review_id=review_id,
    )


@router.post(
    "/o2o/approve",
    response_model=StorefrontDomainOperatorResolutionResponse,
)
async def approve_storefront_o2o_cutover(
    payload: StorefrontO2OCutoverApprovalRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    return await storefront_domain_operator_service.approve_o2o_cutover(
        current_user,
        **payload.model_dump(),
    )


@router.post(
    "/conflict/resolve",
    response_model=StorefrontDomainOperatorResolutionResponse,
)
async def resolve_storefront_conflict_claim(
    payload: StorefrontConflictResolutionRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    return await storefront_domain_operator_service.resolve_conflict_claim(
        current_user,
        **payload.model_dump(),
    )


@router.post(
    "/ambiguous-create/adopt",
    response_model=StorefrontDomainOperatorResolutionResponse,
)
async def adopt_storefront_ambiguous_create(
    payload: StorefrontAmbiguousCreateAdoptionRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    return await storefront_domain_operator_service.adopt_ambiguous_create(
        current_user,
        **payload.model_dump(),
    )
