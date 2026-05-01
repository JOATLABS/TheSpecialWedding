"""Tenant-scoped lookup helpers for vendor-domain resources.

Centralizes the planner-ownership boundary at the Mongo query layer for
vendor profiles, weddings, vendor assignments, vendor contracts, vendor
forms, and vendor form submissions. Mutation paths must use these
helpers so a client-supplied ``_id`` cannot leak across tenants.

Contract:
  - ``actor_email=None`` → root-admin bypass (no ownership filter).
  - ``actor_email=str``  → require ownership match.
  - returns ``None`` when not found OR owned by another planner.
    Callers raise 404 with a generic "not found" detail so foreign IDs
    and missing IDs are indistinguishable from the outside (per
    ``AGENTS.md`` §"Authorization And Tenant Boundary Rule").

This module is the canonical home for the pattern. ``VendorService``
private methods delegate here; any other module that needs the same
protection (e.g. ``contract_service``) should call these functions
directly rather than re-implementing the filter shape.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import mongo
from app.utils.planner_ownership import (
    build_wedding_owner_query,
    combine_mongo_filters,
    normalize_planner_email,
)

logger = logging.getLogger(__name__)


async def get_owned_vendor_profile(
    vendor_id: str, actor_email: Optional[str]
) -> Optional[dict]:
    """Fetch a vendor profile, scoped by ``created_by == actor_email``.

    Returns None on bad ID, missing record, or wrong owner.
    """
    if not vendor_id:
        return None
    try:
        obj_id = ObjectId(vendor_id)
    except (InvalidId, TypeError, ValueError):
        return None

    query: Dict[str, Any] = {"_id": obj_id}
    normalized_actor = normalize_planner_email(actor_email)
    if normalized_actor is not None:
        query["created_by"] = normalized_actor

    try:
        return await mongo.db["vendor_profiles"].find_one(query)
    except Exception as e:
        logger.warning(
            f"Failed to look up vendor profile '{vendor_id}' for actor "
            f"'{actor_email}': {e}"
        )
        return None


async def get_owned_wedding(
    wedding_id: str, actor_email: Optional[str]
) -> Optional[dict]:
    """Fetch a wedding, scoped via the canonical planner-ownership query.

    Weddings carry ownership via ``assigned_planner_id`` /
    ``assigned_planner_email`` (NOT ``created_by``), so the filter is
    delegated to ``planner_ownership.build_wedding_owner_query``. Tries
    the string ID first, then ObjectId — matching the legacy
    ``_get_wedding`` shape so wedding IDs stored as ``wedding_<hex>``
    strings still resolve.

    Returns None on missing record or wrong owner.
    """
    if not wedding_id:
        return None

    normalized_actor = normalize_planner_email(actor_email)
    owner_query = (
        build_wedding_owner_query(planner_email=normalized_actor)
        if normalized_actor is not None
        else None
    )

    async def _find(id_value: Any) -> Optional[dict]:
        id_filter = {"_id": id_value}
        query = combine_mongo_filters(id_filter, owner_query)
        try:
            return await mongo.db["weddings"].find_one(query)
        except Exception as e:
            logger.debug(
                f"Wedding lookup failed for id={id_value!r} "
                f"(actor={actor_email!r}): {e}"
            )
            return None

    # First try the string ID form (most weddings use ``wedding_<hex>``).
    wedding = await _find(wedding_id)
    if wedding:
        return wedding

    # Fall back to ObjectId form.
    try:
        obj_id = ObjectId(wedding_id)
    except (InvalidId, TypeError, ValueError):
        return None

    return await _find(obj_id)


async def get_owned_assignment(
    assignment_id: str, actor_email: Optional[str]
) -> Optional[dict]:
    """Fetch a vendor_assignment, scoped by ``created_by == actor_email``.

    Returns None on bad ID, missing record, or wrong owner.
    """
    if not assignment_id:
        return None
    try:
        obj_id = ObjectId(assignment_id)
    except (InvalidId, TypeError, ValueError):
        return None

    query: Dict[str, Any] = {"_id": obj_id, "is_deleted": {"$ne": True}}
    normalized_actor = normalize_planner_email(actor_email)
    if normalized_actor is not None:
        query["created_by"] = normalized_actor

    try:
        return await mongo.db["vendor_assignments"].find_one(query)
    except Exception as e:
        logger.warning(
            f"Failed to look up vendor_assignment '{assignment_id}' for "
            f"actor '{actor_email}': {e}"
        )
        return None


async def get_owned_contract(
    contract_id: str, actor_email: Optional[str]
) -> Optional[dict]:
    """Fetch a vendor_contract, scoped by ``created_by == actor_email``.

    Used by mutation paths that fetch a contract by ID without going
    through the higher-level ``get_contract`` (which already enforces
    the boundary for the contract-detail GET path). Returns None on
    bad ID, missing record, or wrong owner.
    """
    if not contract_id:
        return None
    try:
        obj_id = ObjectId(contract_id)
    except (InvalidId, TypeError, ValueError):
        return None

    query: Dict[str, Any] = {"_id": obj_id, "is_soft_deleted": {"$ne": True}}
    normalized_actor = normalize_planner_email(actor_email)
    if normalized_actor is not None:
        query["created_by"] = normalized_actor

    try:
        return await mongo.db["vendor_contracts"].find_one(query)
    except Exception as e:
        logger.warning(
            f"Failed to look up vendor_contract '{contract_id}' for "
            f"actor '{actor_email}': {e}"
        )
        return None


async def get_owned_form(form_id: str, actor_email: Optional[str]) -> Optional[dict]:
    """Fetch a vendor_form, scoped by ``created_by == actor_email``.

    ``vendor_forms.created_by`` is the planner's email — set when the
    form is created via ``VendorFormService.create_vendor_form``.
    Mutation/read paths that resolve a form by ``_id`` must use this
    helper so a client-supplied ``form_id`` cannot leak across tenants.

    Returns None on bad ID, missing record, or wrong owner.
    """
    if not form_id:
        return None
    try:
        obj_id = ObjectId(form_id)
    except (InvalidId, TypeError, ValueError):
        return None

    query: Dict[str, Any] = {"_id": obj_id}
    normalized_actor = normalize_planner_email(actor_email)
    if normalized_actor is not None:
        query["created_by"] = normalized_actor

    try:
        return await mongo.db["vendor_forms"].find_one(query)
    except Exception as e:
        logger.warning(
            f"Failed to look up vendor_form '{form_id}' for actor '{actor_email}': {e}"
        )
        return None


async def get_owned_form_submission(
    submission_id: str, actor_email: Optional[str]
) -> Optional[dict]:
    """Fetch a vendor form submission, scoped by planner ownership.

    ``vendor_submissions`` documents do NOT carry a direct ``created_by``
    field — they are written by the public vendor-form submission
    endpoint without any planner identity on the record. Ownership is
    established transitively through the parent ``vendor_forms`` row
    referenced by ``form_id``.

    Resolution order:
      1. Fetch the submission by ``_id``.
      2. Resolve its parent ``vendor_form`` via ``get_owned_form``;
         if that returns None (bad/foreign form), the submission is
         treated as not-owned.
      3. Return the submission only when ownership passes.

    Returns None on bad ID, missing record, or wrong owner. Mirrors the
    404-not-403 ambiguity convention used by ``get_contract``.
    """
    if not submission_id:
        return None
    try:
        obj_id = ObjectId(submission_id)
    except (InvalidId, TypeError, ValueError):
        return None

    try:
        submission = await mongo.db["vendor_submissions"].find_one({"_id": obj_id})
    except Exception as e:
        logger.warning(
            f"Failed to look up vendor_submission '{submission_id}' for "
            f"actor '{actor_email}': {e}"
        )
        return None

    if not submission:
        return None

    # Root-admin bypass — actor_email=None skips the ownership check.
    if normalize_planner_email(actor_email) is None:
        return submission

    parent_form_id = submission.get("form_id")
    if not parent_form_id:
        # No parent form linked — cannot establish ownership safely.
        return None

    owned_form = await get_owned_form(str(parent_form_id), actor_email)
    if owned_form is None:
        return None

    return submission
