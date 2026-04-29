"""
Vendor Management Service

Comprehensive service for managing vendors, contracts, and payments.
Handles all business logic for the vendor management feature.
"""

import hashlib
import hmac
import logging
import os
import re
import secrets
import string
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional

import stripe
from botocore.exceptions import ClientError
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile

from app.core.database import mongo
from app.core.settings import settings
from app.utils.planner_ownership import (
    build_wedding_owner_query,
    combine_mongo_filters,
    normalize_planner_email,
    wedding_belongs_to_owner,
)
from app.models.vendor import (
    ContractKind,
    ContractStatus,
    ContractType,
    PaymentLinkStatus,
    PaymentMilestoneStatus,
    QuoteStatus,
)
from app.models.vendor_contracts import VendorContractActivityType
from app.services.email_service_resend import ResendEmailService
from app.services.media_storage import MediaStorage, StorageTarget

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================
SYSTEM_CREATED_BY = "system@thespecialwedding.com"
TOKEN_EXPIRY_DAYS = int(os.getenv("CONTRACT_TOKEN_EXPIRY_DAYS", "30"))
DEPOSIT_DUE_DAYS = int(os.getenv("DEPOSIT_DUE_DAYS", "7"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_CONTRACT_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
# Allowed MIME types for contract uploads
ALLOWED_CONTRACT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def validate_object_id(id_str: str, field_name: str = "ID") -> ObjectId:
    """
    Validate and convert a string to ObjectId.
    Raises HTTPException with clear error message if invalid.
    """
    if not id_str:
        raise HTTPException(status_code=400, detail=f"Missing {field_name}")
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")


class VendorService:
    """
    Service for managing all vendor-related operations.
    """

    def __init__(self):
        # Collections
        self.vendor_profiles = mongo.db["vendor_profiles"]
        self.contract_templates = mongo.db["contract_templates"]
        self.vendor_contracts = mongo.db["vendor_contracts"]
        self.vendor_contract_activities = mongo.db["vendor_contract_activities"]
        self.payment_milestones = mongo.db["vendor_payment_milestones"]
        self.vendor_assignments = mongo.db["vendor_assignments"]
        self.vendor_communications = mongo.db["vendor_communications"]
        self.vendor_quotes = mongo.db["vendor_quotes"]
        self.budget_categories = mongo.db["budget_categories"]
        self.weddings = mongo.db["weddings"]
        self.couple_users = mongo.db["couple_users"]
        self.users = mongo.get_users_collection()
        self.payment_links = mongo.db["payment_links"]
        self.vendor_forms = mongo.db["vendor_forms"]
        self.form_responses = mongo.db["form_responses"]

        # Services
        self.email_service = ResendEmailService()

        self.storage = MediaStorage()
        self.s3: S3Client = self.storage.client
        primary_target = self.storage.target(StorageTarget.PRIMARY)
        if not primary_target.bucket_name:
            raise RuntimeError("S3_BUCKET_NAME environment variable is required")
        self.bucket_name = primary_target.bucket_name
        self.media_domain = primary_target.public_domain or ""

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _generate_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        return "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(length)
        )

    def _generate_contract_number(self) -> str:
        """Generate a unique contract number"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_suffix = "".join(secrets.choice(string.digits) for _ in range(4))
        return f"CON-{timestamp}-{random_suffix}"

    @staticmethod
    def _build_public_vendor_contract_link(
        base_url: str, contract_id: str, access_token: str
    ) -> str:
        normalized_base = base_url.rstrip("/")
        return f"{normalized_base}/vendor-contract/{contract_id}/{access_token}"

    @staticmethod
    def _build_inactive_contract_token_fields() -> Dict[str, Any]:
        # Deliberately OMITS `access_token_hash` rather than setting it to
        # None, because the unique-sparse index on access_token_hash treats
        # an explicit null as a value (sparse only excludes documents
        # MISSING the field). Two contracts inserted with
        # access_token_hash=None would therefore collide on the index.
        # send_contract sets the field to a real hash at issuance time;
        # until then the field is genuinely absent.
        return {
            "token_expires_at": None,
            "token_revoked_at": None,
            "token_last_sent_at": None,
            "token_last_viewed_at": None,
        }

    def _hash_contract_access_token(self, raw_token: str) -> str:
        secret_key = settings.secret_key
        if not secret_key:
            raise RuntimeError("SECRET_KEY is required for contract token hashing")

        return hmac.new(
            secret_key.encode("utf-8"),
            raw_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _verify_contract_access_token(self, raw_token: str, stored_hash: str) -> bool:
        expected_hash = self._hash_contract_access_token(raw_token)
        return hmac.compare_digest(expected_hash, stored_hash)

    def _issue_contract_access_token(
        self, contract_id: str, planner_settings: dict
    ) -> tuple[str, dict]:
        now = datetime.now(timezone.utc)
        raw_token = self._generate_token()
        return raw_token, {
            "access_token_hash": self._hash_contract_access_token(raw_token),
            "token_expires_at": now
            + timedelta(days=planner_settings["token_expiry_days"]),
            "token_revoked_at": None,
            "token_last_sent_at": now,
            "token_last_viewed_at": None,
            "updated_at": now,
        }

    async def _revoke_contract_access_token(
        self, contract_id: str, session: Any = None
    ) -> None:
        revoked_at = datetime.now(timezone.utc)
        await self.vendor_contracts.update_one(
            {"_id": validate_object_id(contract_id, "contract ID")},
            {
                "$set": {
                    "token_revoked_at": revoked_at,
                    "updated_at": revoked_at,
                }
            },
            session=session,
        )

    def _sanitize_public_contract_response(
        self, contract: Dict[str, Any]
    ) -> Dict[str, Any]:
        contract.pop("access_token", None)
        contract.pop("access_token_hash", None)
        contract.pop("internal_notes", None)
        contract.pop("token_revoked_at", None)
        contract.pop("token_last_sent_at", None)
        contract.pop("token_last_viewed_at", None)
        return contract

    async def _run_required_transaction(
        self,
        operation_name: str,
        operation: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        try:
            async with await mongo.client.start_session() as session:
                async with session.start_transaction():
                    return await operation(session)
        except HTTPException:
            raise
        except Exception as exc:
            message = str(exc).lower()
            if (
                "transaction" in message
                or "replica" in message
                or "topology" in message
                or "session" in message
            ):
                logger.error(
                    "MongoDB transaction support is required for %s: %s",
                    operation_name,
                    exc,
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"{operation_name} requires MongoDB transaction support",
                )
            raise

    @staticmethod
    def _serialize_doc(doc: Dict) -> Dict:
        """Normalize a MongoDB document for API response: ensure both 'id' and '_id' are string."""
        if "_id" in doc:
            doc["id"] = str(doc["_id"])
            doc["_id"] = str(doc["_id"])
        return doc

    @staticmethod
    def _stringify_id(value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def _attach_contract_version_metadata(
        self, contract: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Backfill default lineage metadata for legacy contracts in API responses."""
        contract_id = self._stringify_id(contract.get("_id") or contract.get("id"))
        contract["version_number"] = int(contract.get("version_number") or 1)
        contract["root_contract_id"] = (
            self._stringify_id(contract.get("root_contract_id")) or contract_id
        )
        contract["parent_contract_id"] = self._stringify_id(
            contract.get("parent_contract_id")
        )
        contract["supersedes_contract_id"] = self._stringify_id(
            contract.get("supersedes_contract_id")
        )
        contract["superseded_by_contract_id"] = self._stringify_id(
            contract.get("superseded_by_contract_id")
        )
        contract["is_current_version"] = contract.get("is_current_version", True)

        raw_contract_kind = contract.get("contract_kind", ContractKind.ORIGINAL.value)
        if isinstance(raw_contract_kind, ContractKind):
            raw_contract_kind = raw_contract_kind.value
        contract["contract_kind"] = raw_contract_kind

        contract.setdefault("amendment_reason", None)
        contract.setdefault("superseded_at", None)
        contract.setdefault("access_token_hash", None)
        contract.setdefault("token_revoked_at", None)
        contract.setdefault("token_last_sent_at", None)
        contract.setdefault("token_last_viewed_at", None)
        return contract

    def _get_root_contract_id(self, contract: Dict[str, Any]) -> str:
        """Resolve the root/original contract id for a lineage-aware contract document."""
        root_contract_id = contract.get("root_contract_id")
        if root_contract_id:
            return str(root_contract_id)

        contract_id = contract.get("_id") or contract.get("id")
        if not contract_id:
            raise HTTPException(status_code=500, detail="Contract is missing an id")
        return str(contract_id)

    @staticmethod
    def _is_contract_current(contract: Dict[str, Any]) -> bool:
        return contract.get("is_current_version", True)

    def _ensure_contract_current_for_payments(
        self, contract: Dict[str, Any], *, action: str
    ) -> None:
        """Fail closed when money mutations target a historical contract version."""
        if not self._is_contract_current(contract):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot {action} on a historical contract version",
            )

    @staticmethod
    def _can_create_revision_from_status(status: str) -> bool:
        return status in {
            ContractStatus.SENT.value,
            ContractStatus.VIEWED.value,
            ContractStatus.SIGNED.value,
        }

    async def _ensure_contract_editable(self, contract: Dict[str, Any]) -> None:
        """Allow edits only for active drafts or draft revisions based on the live version."""
        if contract["status"] not in [
            ContractStatus.DRAFT.value,
            ContractStatus.PENDING_REVIEW.value,
        ]:
            raise HTTPException(
                status_code=400,
                detail="Contract cannot be modified after it has been sent",
            )

        if self._is_contract_current(contract):
            return

        supersedes_contract_id = contract.get("supersedes_contract_id")
        if not supersedes_contract_id:
            raise HTTPException(
                status_code=400,
                detail="Historical contract versions cannot be edited",
            )

        superseded_contract = await self.get_contract(
            supersedes_contract_id,
            created_by=contract["created_by"],
        )
        if not self._is_contract_current(superseded_contract):
            raise HTTPException(
                status_code=400,
                detail="This draft is stale because a newer contract version is already live",
            )

    def _build_contract_lineage_query(
        self, root_contract_id: str, created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        root_object_id = validate_object_id(root_contract_id, "root contract ID")
        lineage_query: Dict[str, Any] = {
            "$or": [
                {"root_contract_id": root_contract_id},
                {"_id": root_object_id},
            ]
        }

        if created_by:
            lineage_query["created_by"] = created_by

        return lineage_query

    async def _get_contract_lineage(
        self, root_contract_id: str, created_by: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch and normalize every contract in a lineage."""
        query = self._build_contract_lineage_query(
            root_contract_id=root_contract_id, created_by=created_by
        )
        contracts = await self.vendor_contracts.find(query).to_list(length=200)

        for contract in contracts:
            self._serialize_doc(contract)
            self._attach_contract_version_metadata(contract)

        contracts.sort(
            key=lambda item: (
                item.get("version_number", 1),
                item.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
            )
        )
        return contracts

    async def _get_next_contract_version_number(
        self, root_contract_id: str, created_by: Optional[str] = None
    ) -> int:
        lineage = await self._get_contract_lineage(
            root_contract_id=root_contract_id, created_by=created_by
        )
        if not lineage:
            return 1

        return max(int(contract.get("version_number", 1)) for contract in lineage) + 1

    def _build_contract_revision_copy(
        self,
        source_contract: Dict[str, Any],
        revision_kind: str,
        next_version_number: int,
        reason: Optional[str] = None,
        copy_sections: bool = True,
        copy_terms_and_conditions: bool = True,
        copy_cancellation_policy: bool = True,
        copy_custom_clauses: bool = True,
    ) -> Dict[str, Any]:
        """Clone a live contract into a new editable child version."""
        new_contract_id = ObjectId()
        source_contract_id = self._stringify_id(
            source_contract.get("_id") or source_contract.get("id")
        )
        root_contract_id = self._get_root_contract_id(source_contract)
        now = datetime.now(timezone.utc)

        revision_contract = {
            "_id": new_contract_id,
            "wedding_id": source_contract["wedding_id"],
            "vendor_profile_id": source_contract.get("vendor_profile_id"),
            "vendor_quote_id": source_contract.get("vendor_quote_id"),
            "budget_category_id": source_contract.get("budget_category_id"),
            "template_id": source_contract.get("template_id"),
            "vendor_name": source_contract["vendor_name"],
            "vendor_email": source_contract["vendor_email"],
            "vendor_phone": source_contract.get("vendor_phone"),
            "vendor_address": source_contract.get("vendor_address"),
            "service_category": source_contract["service_category"],
            "custom_service_category": source_contract.get("custom_service_category"),
            "contract_title": source_contract["contract_title"],
            "contract_number": source_contract.get("contract_number"),
            "contract_type": source_contract.get(
                "contract_type", ContractType.TEMPLATE.value
            ),
            "uploaded_pdf_url": source_contract.get("uploaded_pdf_url"),
            "uploaded_pdf_name": source_contract.get("uploaded_pdf_name"),
            "form_submission_id": source_contract.get("form_submission_id"),
            "form_submission_ids": deepcopy(
                source_contract.get("form_submission_ids") or []
            ),
            "form_data_applied": source_contract.get("form_data_applied", False),
            "form_data_mappings": deepcopy(
                source_contract.get("form_data_mappings") or {}
            ),
            "sections": (
                deepcopy(source_contract.get("sections") or []) if copy_sections else []
            ),
            "terms_and_conditions": (
                deepcopy(source_contract.get("terms_and_conditions"))
                if copy_terms_and_conditions
                else None
            ),
            "cancellation_policy": (
                deepcopy(source_contract.get("cancellation_policy"))
                if copy_cancellation_policy
                else None
            ),
            "custom_clauses": (
                deepcopy(source_contract.get("custom_clauses"))
                if copy_custom_clauses
                else None
            ),
            "total_amount": source_contract["total_amount"],
            "currency": source_contract.get("currency", "USD"),
            "deposit_amount": source_contract.get("deposit_amount"),
            "deposit_due_date": source_contract.get("deposit_due_date"),
            "status": ContractStatus.DRAFT.value,
            "service_date": source_contract.get("service_date"),
            "service_start_time": source_contract.get("service_start_time"),
            "service_end_time": source_contract.get("service_end_time"),
            "service_location": source_contract.get("service_location"),
            "created_by": source_contract["created_by"],
            "internal_notes": source_contract.get("internal_notes"),
            "vendor_notes": source_contract.get("vendor_notes"),
            "draft_document_url": source_contract.get("draft_document_url"),
            "signed_document_url": None,
            "attachments": deepcopy(source_contract.get("attachments") or []),
            "sent_at": None,
            "viewed_at": None,
            "signed_at": None,
            "signed_by_name": None,
            "signed_by_email": None,
            "signature_ip": None,
            "completed_at": None,
            "cancelled_at": None,
            "cancellation_reason": None,
            "version_number": next_version_number,
            "root_contract_id": root_contract_id,
            "parent_contract_id": source_contract_id,
            "supersedes_contract_id": source_contract_id,
            "superseded_by_contract_id": None,
            "is_current_version": False,
            "contract_kind": revision_kind,
            "amendment_reason": reason,
            "superseded_at": None,
            "created_at": now,
            "updated_at": now,
            **self._build_inactive_contract_token_fields(),
        }

        return revision_contract

    async def _mark_contract_as_superseded(
        self, contract_id: str, superseded_by_contract_id: str
    ) -> None:
        """Mark a once-live contract as historical without changing its status."""
        await self.vendor_contracts.update_one(
            {"_id": validate_object_id(contract_id, "contract ID")},
            {
                "$set": {
                    "is_current_version": False,
                    "superseded_at": datetime.now(timezone.utc),
                    "superseded_by_contract_id": superseded_by_contract_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    @staticmethod
    def _get_vendor_service_label(
        service_category: str,
        custom_service_category: Optional[str] = None,
    ) -> str:
        if service_category == "other" and custom_service_category:
            return custom_service_category.strip()

        labels = {
            "dj": "DJ",
            "mc": "MC / Host",
            "hair_makeup": "Hair & Makeup",
            "photo_booth": "Photo Booth",
        }
        return labels.get(service_category, service_category.replace("_", " ").title())

    @staticmethod
    def _normalize_vendor_category_data(
        data: Dict[str, Any], existing: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        normalized = dict(data)

        service_category = normalized.get("service_category")
        if service_category is None and existing:
            service_category = existing.get("service_category")

        custom_category = normalized.get("custom_service_category")
        if custom_category is None and existing:
            custom_category = existing.get("custom_service_category")

        if isinstance(custom_category, str):
            custom_category = custom_category.strip() or None

        if service_category == "other":
            if not custom_category:
                raise HTTPException(
                    status_code=400,
                    detail="Please enter a custom vendor category when selecting Other.",
                )
            normalized["custom_service_category"] = custom_category
        elif "custom_service_category" in normalized or existing:
            normalized["custom_service_category"] = None

        return normalized

    @staticmethod
    def _omit_empty_google_place_id(data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(data)
        google_place_id = normalized.get("google_place_id")

        if isinstance(google_place_id, str):
            google_place_id = google_place_id.strip() or None

        if google_place_id:
            normalized["google_place_id"] = google_place_id
        else:
            normalized.pop("google_place_id", None)

        return normalized

    async def _get_planner_contract_settings(
        self, planner_email: str
    ) -> Dict[str, Any]:
        """
        Get contract settings for a planner, with graceful fallback to system defaults.

        Implements layered configuration:
        1. Planner's stored preferences (if set)
        2. System defaults from environment variables

        Returns:
            Dict with token_expiry_days, deposit_due_days, etc.
        """
        defaults = {
            "token_expiry_days": TOKEN_EXPIRY_DAYS,
            "deposit_due_days": DEPOSIT_DUE_DAYS,
            "payment_reminder_days": [7, 3, 1],
            "auto_followup_days": 3,
            "default_currency": "USD",
        }

        try:
            planner = await self.users.find_one({"email": planner_email})
            if planner and planner.get("contract_settings"):
                # Merge planner settings with defaults (planner overrides defaults)
                settings = planner["contract_settings"]
                return {
                    "token_expiry_days": settings.get(
                        "token_expiry_days", defaults["token_expiry_days"]
                    ),
                    "deposit_due_days": settings.get(
                        "deposit_due_days", defaults["deposit_due_days"]
                    ),
                    "payment_reminder_days": settings.get(
                        "payment_reminder_days", defaults["payment_reminder_days"]
                    ),
                    "auto_followup_days": settings.get(
                        "auto_followup_days", defaults["auto_followup_days"]
                    ),
                    "default_currency": settings.get(
                        "default_currency", defaults["default_currency"]
                    ),
                }
        except Exception as e:
            logger.warning(f"Failed to fetch planner settings for {planner_email}: {e}")

        return defaults

    async def _get_wedding(self, wedding_id: str) -> Optional[dict]:
        """Get wedding by ID, trying both string and ObjectId formats.

        Backwards-compatible shim. Existing callers that pre-date the
        cross-tenant boundary fix should be migrated to
        ``_get_owned_wedding`` so the planner-ownership check runs at the
        Mongo query layer. This shim delegates to the owned helper with
        ``actor_email=None`` (root-admin bypass) so legacy callers retain
        their previous semantics until they are migrated.
        """
        return await self._get_owned_wedding(wedding_id, actor_email=None)

    # ------------------------------------------------------------------
    # Tenant-scoped lookup helpers
    #
    # These centralize the planner-ownership boundary at the Mongo query
    # layer so vendor mutation paths cannot trust an `_id` from the
    # client. They follow the established pattern documented in
    # AGENTS.md "Authorization And Tenant Boundary Rule" and the
    # 404-not-403 ambiguity convention used by ``get_contract`` (see
    # vendor_service.py ~line 1928).
    #
    # Contract:
    #   - actor_email=None → root-admin bypass (no ownership filter).
    #   - actor_email=str  → require ownership match.
    #   - returns None when not found OR owned by another planner.
    #     The caller raises 404 with a generic "not found" detail so
    #     foreign IDs and missing IDs are indistinguishable from the
    #     outside.
    # ------------------------------------------------------------------

    async def _get_owned_vendor_profile(
        self, vendor_id: str, actor_email: Optional[str]
    ) -> Optional[dict]:
        """Fetch a vendor profile, scoped by planner ownership.

        ``vendor_profiles.created_by`` is the planner's email — the same
        scope the existing ``get_vendor_profile`` (vendor_service.py
        ~line 1199) enforces. Mutation paths must use this helper so the
        client-supplied ``vendor_profile_id`` cannot leak across
        tenants.

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
            return await self.vendor_profiles.find_one(query)
        except Exception as e:
            logger.warning(
                f"Failed to look up vendor profile '{vendor_id}' for actor "
                f"'{actor_email}': {e}"
            )
            return None

    async def _get_owned_wedding(
        self, wedding_id: str, actor_email: Optional[str]
    ) -> Optional[dict]:
        """Fetch a wedding, scoped via the canonical planner-ownership query.

        Weddings carry ownership via ``assigned_planner_id`` /
        ``assigned_planner_email`` (NOT ``created_by``). We delegate to
        ``planner_ownership.build_wedding_owner_query`` so the rule lives
        in one place. Tries the string ID first, then ObjectId — matching
        the legacy ``_get_wedding`` shape so wedding IDs stored as
        ``wedding_<hex>`` strings still resolve.

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
                return await self.weddings.find_one(query)
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

    async def _get_owned_assignment(
        self, assignment_id: str, actor_email: Optional[str]
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

        query: Dict[str, Any] = {"_id": obj_id}
        normalized_actor = normalize_planner_email(actor_email)
        if normalized_actor is not None:
            query["created_by"] = normalized_actor

        try:
            return await self.vendor_assignments.find_one(query)
        except Exception as e:
            logger.warning(
                f"Failed to look up vendor_assignment '{assignment_id}' for "
                f"actor '{actor_email}': {e}"
            )
            return None

    async def _get_owned_contract(
        self, contract_id: str, actor_email: Optional[str]
    ) -> Optional[dict]:
        """Fetch a vendor_contract, scoped by ``created_by == actor_email``.

        ``get_contract`` already enforces this boundary for the
        contract-detail GET path; this helper is for mutation paths
        (currently ``upload_contract_document``) that fetch by ID
        without the ownership filter. Returns None on bad ID, missing
        record, or wrong owner.
        """
        if not contract_id:
            return None
        try:
            obj_id = ObjectId(contract_id)
        except (InvalidId, TypeError, ValueError):
            return None

        query: Dict[str, Any] = {"_id": obj_id}
        normalized_actor = normalize_planner_email(actor_email)
        if normalized_actor is not None:
            query["created_by"] = normalized_actor

        try:
            return await self.vendor_contracts.find_one(query)
        except Exception as e:
            logger.warning(
                f"Failed to look up vendor_contract '{contract_id}' for "
                f"actor '{actor_email}': {e}"
            )
            return None

    async def _resolve_couple_contact(
        self,
        wedding_id: Optional[str],
        actor_email: Optional[str],
    ) -> Dict[str, Optional[str]]:
        """
        Resolve the couple's email + display name for a given wedding_id.

        Tries the authoritative `couple_users` collection first; falls back to
        the embedded fields on the `weddings` doc. Both reads are scoped to
        the actor planner's ownership (per AGENTS.md "Authorization And Tenant
        Boundary Rule") to defend against ownership drift surfaced by
        `app/scripts/report_planner_ownership_drift.py`. When `actor_email` is
        None we treat the call as root-admin and skip scoping. Always returns a
        dict with `couple_email` and `couple_names` keys — both may be None.
        Never raises.
        """
        result: Dict[str, Optional[str]] = {
            "couple_email": None,
            "couple_names": None,
        }

        if not wedding_id:
            return result

        normalized_actor_email = normalize_planner_email(actor_email)

        # Defense-in-depth: confirm the wedding belongs to the actor planner
        # before trusting any couple lookups keyed by wedding_id. Skip the
        # check entirely for the root-admin case (actor_email is None).
        wedding: Optional[dict] = None
        if normalized_actor_email is not None:
            try:
                wedding = await self._get_wedding(wedding_id)
            except Exception as e:
                logger.warning(
                    f"Failed to look up wedding for couple contact '{wedding_id}': {e}"
                )
                wedding = None

            if not wedding_belongs_to_owner(
                wedding, planner_email=normalized_actor_email
            ):
                # Wedding is missing or owned by a different planner — refuse
                # to leak couple contact info. Return the empty result.
                return result

        # Authoritative source: couple_users collection (keyed by wedding_id).
        # Scope by planner_email when we have an actor identity.
        couple_query: Dict[str, Any] = {"wedding_id": wedding_id}
        if normalized_actor_email is not None:
            couple_query["planner_email"] = normalized_actor_email

        try:
            couple_doc = await self.couple_users.find_one(
                couple_query,
                {"email": 1, "partner1_name": 1, "partner2_name": 1},
            )
        except Exception as e:
            logger.warning(
                f"Failed to look up couple_users for wedding_id '{wedding_id}': {e}"
            )
            couple_doc = None

        if couple_doc:
            email = (couple_doc.get("email") or "").strip() or None
            result["couple_email"] = email
            partner1 = (couple_doc.get("partner1_name") or "").strip()
            partner2 = (couple_doc.get("partner2_name") or "").strip()
            if partner1 and partner2:
                result["couple_names"] = f"{partner1} & {partner2}"
            elif partner1:
                result["couple_names"] = partner1
            elif partner2:
                result["couple_names"] = partner2

        # Fallback to wedding doc for any field still missing. The wedding doc
        # was already loaded + ownership-checked above when actor_email is set;
        # for the root-admin case we load it now without scoping.
        if not result["couple_email"] or not result["couple_names"]:
            if wedding is None and normalized_actor_email is None:
                try:
                    wedding = await self._get_wedding(wedding_id)
                except Exception as e:
                    logger.warning(
                        f"Failed to look up wedding for couple contact '{wedding_id}': {e}"
                    )
                    wedding = None

            if wedding:
                if not result["couple_email"]:
                    embedded_couple = wedding.get("couple") or {}
                    if isinstance(embedded_couple, dict):
                        embedded_email = (
                            embedded_couple.get("email") or ""
                        ).strip() or None
                        result["couple_email"] = embedded_email
                if not result["couple_names"]:
                    fallback_names = (wedding.get("couple_names") or "").strip() or None
                    result["couple_names"] = fallback_names

        return result

    async def _log_communication(
        self,
        vendor_profile_id: str,
        comm_type: str,
        content: str,
        created_by: str,
        wedding_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        subject: Optional[str] = None,
        direction: str = "outgoing",
        sent_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
    ):
        """Log a communication with a vendor"""
        comm = {
            "vendor_profile_id": vendor_profile_id,
            "wedding_id": wedding_id,
            "contract_id": contract_id,
            "type": comm_type,
            "subject": subject,
            "content": content,
            "direction": direction,
            "sent_to": sent_to,
            "attachments": attachments or [],
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        await self.vendor_communications.insert_one(comm)

    async def _log_contract_activity(
        self,
        contract_id: str,
        root_contract_id: str,
        activity_type: VendorContractActivityType | str,
        title: str,
        description: Optional[str],
        actor_type: str,
        actor_identifier: Optional[str],
        actor_display_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        """Persist one contract activity row for the detail page timeline."""
        try:
            normalized_type = (
                activity_type.value
                if isinstance(activity_type, VendorContractActivityType)
                else activity_type
            )
            activity = {
                "contract_id": contract_id,
                "root_contract_id": root_contract_id,
                "activity_type": normalized_type,
                "title": title,
                "description": description,
                "actor": {
                    "type": actor_type,
                    "identifier": actor_identifier,
                    "display_name": actor_display_name,
                },
                "metadata": metadata or {},
                "created_at": created_at or datetime.now(timezone.utc),
            }
            await self.vendor_contract_activities.insert_one(activity)
        except Exception as exc:
            logger.warning(
                "Failed to persist vendor contract activity %s for contract %s: %s",
                activity_type,
                contract_id,
                exc,
            )

    def _serialize_contract_activity_item(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw activity document into the API response shape."""
        return {
            "id": str(doc.get("_id") or doc.get("id") or ""),
            "contract_id": self._stringify_id(doc.get("contract_id")) or "",
            "root_contract_id": self._stringify_id(doc.get("root_contract_id")) or "",
            "activity_type": doc.get("activity_type"),
            "title": doc.get("title", "Activity"),
            "description": doc.get("description"),
            "actor": doc.get("actor")
            or {"type": "system", "identifier": None, "display_name": None},
            "metadata": doc.get("metadata") or {},
            "created_at": doc.get("created_at"),
        }

    def _build_synthesized_contract_activity(
        self, contract: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build fallback activity entries for legacy contracts with no explicit log rows."""
        contract_id = (
            self._stringify_id(contract.get("_id") or contract.get("id")) or ""
        )
        root_contract_id = self._get_root_contract_id(contract)
        planner_identifier = contract.get("created_by")
        vendor_identifier = contract.get("vendor_email")
        vendor_display_name = (
            contract.get("signed_by_name")
            or contract.get("vendor_name")
            or contract.get("vendor_email")
        )

        items: List[Dict[str, Any]] = [
            {
                "id": f"synth:{contract_id}:created",
                "contract_id": contract_id,
                "root_contract_id": root_contract_id,
                "activity_type": VendorContractActivityType.CONTRACT_CREATED.value,
                "title": "Contract created",
                "description": None,
                "actor": {
                    "type": "planner",
                    "identifier": planner_identifier,
                    "display_name": planner_identifier,
                },
                "metadata": {},
                "created_at": contract.get("created_at"),
            }
        ]

        if contract.get("updated_at") and contract.get("updated_at") != contract.get(
            "created_at"
        ):
            items.append(
                {
                    "id": f"synth:{contract_id}:updated",
                    "contract_id": contract_id,
                    "root_contract_id": root_contract_id,
                    "activity_type": VendorContractActivityType.CONTRACT_UPDATED.value,
                    "title": "Contract updated",
                    "description": None,
                    "actor": {
                        "type": "planner",
                        "identifier": planner_identifier,
                        "display_name": planner_identifier,
                    },
                    "metadata": {},
                    "created_at": contract.get("updated_at"),
                }
            )

        if contract.get("sent_at"):
            items.append(
                {
                    "id": f"synth:{contract_id}:sent",
                    "contract_id": contract_id,
                    "root_contract_id": root_contract_id,
                    "activity_type": VendorContractActivityType.CONTRACT_SENT.value,
                    "title": "Contract sent",
                    "description": None,
                    "actor": {
                        "type": "planner",
                        "identifier": planner_identifier,
                        "display_name": planner_identifier,
                    },
                    "metadata": {},
                    "created_at": contract.get("sent_at"),
                }
            )

        if contract.get("viewed_at"):
            items.append(
                {
                    "id": f"synth:{contract_id}:viewed",
                    "contract_id": contract_id,
                    "root_contract_id": root_contract_id,
                    "activity_type": VendorContractActivityType.CONTRACT_VIEWED.value,
                    "title": "Contract viewed",
                    "description": None,
                    "actor": {
                        "type": "vendor",
                        "identifier": vendor_identifier,
                        "display_name": contract.get("vendor_name"),
                    },
                    "metadata": {},
                    "created_at": contract.get("viewed_at"),
                }
            )

        if contract.get("signed_at"):
            items.append(
                {
                    "id": f"synth:{contract_id}:signed",
                    "contract_id": contract_id,
                    "root_contract_id": root_contract_id,
                    "activity_type": VendorContractActivityType.CONTRACT_SIGNED.value,
                    "title": "Contract signed",
                    "description": None,
                    "actor": {
                        "type": "vendor",
                        "identifier": contract.get("signed_by_email")
                        or vendor_identifier,
                        "display_name": vendor_display_name,
                    },
                    "metadata": {},
                    "created_at": contract.get("signed_at"),
                }
            )

        return [item for item in items if item.get("created_at")]

    # =========================================================================
    # VENDOR DIRECTORY (Master List)
    # =========================================================================

    async def create_vendor_profile(self, data: dict, created_by: str) -> dict:
        """Create a new vendor in the directory"""
        try:
            data = self._omit_empty_google_place_id(
                self._normalize_vendor_category_data(data)
            )
            vendor = {
                **data,
                "created_by": created_by,
                "weddings_count": 0,
                "total_revenue": 0.0,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            result = await self.vendor_profiles.insert_one(vendor)
            vendor["_id"] = str(result.inserted_id)

            # Serialize datetime objects for JSON response
            if isinstance(vendor.get("created_at"), datetime):
                vendor["created_at"] = vendor["created_at"].isoformat()
            if isinstance(vendor.get("updated_at"), datetime):
                vendor["updated_at"] = vendor["updated_at"].isoformat()

            logger.info(
                f"Created vendor profile: {vendor['business_name']} by {created_by}"
            )
            return vendor

        except HTTPException:
            raise
        except ValueError as e:
            logger.warning(f"Invalid input creating vendor profile: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to create vendor profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create vendor")

    async def upsert_scraped_vendor(self, data: dict) -> dict:
        """
        Insert or update a vendor discovered by the scraper job.

        Dedup logic:
        1. Match by google_place_id (most reliable)
        2. Match by normalized business_name + city + service_category
        Never overwrites a planner-added (source=manual) vendor.

        Returns the vendor doc (inserted or existing).
        """
        try:
            now = datetime.now(timezone.utc)
            google_place_id = data.get("google_place_id")
            business_name = data.get("business_name", "").strip()
            city = (data.get("city") or "").strip()
            service_category = data.get("service_category")

            # -- Dedup: check if vendor already exists --
            existing = None
            if google_place_id:
                existing = await self.vendor_profiles.find_one(
                    {"google_place_id": google_place_id}
                )

            if not existing and business_name and city:
                # Escape regex metacharacters to prevent injection via business_name/city
                safe_name = re.escape(business_name)
                safe_city = re.escape(city)
                existing = await self.vendor_profiles.find_one(
                    {
                        "business_name": {"$regex": f"^{safe_name}$", "$options": "i"},
                        "city": {"$regex": f"^{safe_city}$", "$options": "i"},
                        "service_category": service_category,
                    }
                )

            # Third dedup tier: business_name + state + category (when city is empty)
            state = (data.get("state") or "").strip()
            if not existing and business_name and not city and state:
                safe_name = re.escape(business_name)
                safe_state = re.escape(state)
                existing = await self.vendor_profiles.find_one(
                    {
                        "business_name": {"$regex": f"^{safe_name}$", "$options": "i"},
                        "state": {"$regex": f"^{safe_state}$", "$options": "i"},
                        "service_category": service_category,
                    }
                )

            # If it exists and was manually added by a planner, don't touch it
            if existing and existing.get("source", "manual") == "manual":
                logger.debug(
                    f"Skipping scraped vendor '{business_name}' — already exists as manual entry"
                )
                existing["_id"] = str(existing["_id"])
                return existing

            # If it exists as a previously scraped entry, refresh it
            if existing:
                update_fields: Dict[str, Any] = {
                    "scraped_at": now,
                    "updated_at": now,
                }
                # Only update fields that have new non-empty values
                for field in [
                    "phone",
                    "website",
                    "address",
                    "state",
                    "country",
                    "postal_code",
                    "service_description",
                    "logo_url",
                    "typical_price_min",
                    "typical_price_max",
                ]:
                    new_val = data.get(field)
                    if new_val is not None and new_val != "":
                        update_fields[field] = new_val

                # Set portfolio_urls to the logo image URL (replace any old website URLs)
                new_logo = data.get("logo_url")
                if new_logo:
                    update_fields["portfolio_urls"] = [new_logo]

                await self.vendor_profiles.update_one(
                    {"_id": existing["_id"]}, {"$set": update_fields}
                )
                existing["_id"] = str(existing["_id"])
                existing.update(update_fields)
                logger.info(f"Refreshed scraped vendor: {business_name} in {city}")
                return existing

            # -- Insert new scraped vendor --
            vendor = self._omit_empty_google_place_id(
                {
                    "business_name": business_name,
                    "email": data.get("email", ""),
                    "phone": data.get("phone"),
                    "website": data.get("website"),
                    "address": data.get("address"),
                    "city": city,
                    "state": data.get("state"),
                    "country": data.get("country", "US"),
                    "postal_code": data.get("postal_code"),
                    "service_category": service_category,
                    "custom_service_category": data.get("custom_service_category"),
                    "service_subcategories": data.get("service_subcategories", []),
                    "service_description": data.get("service_description"),
                    "logo_url": data.get("logo_url"),
                    "portfolio_urls": (
                        [data["logo_url"]] if data.get("logo_url") else []
                    ),
                    "typical_price_min": data.get("typical_price_min"),
                    "typical_price_max": data.get("typical_price_max"),
                    "currency": data.get("currency", "USD"),
                    "tags": data.get("tags", []),
                    "source": "scraped",
                    "google_place_id": google_place_id,
                    "scraped_at": now,
                    "scraped_from_state": data.get("scraped_from_state"),
                    "created_by": SYSTEM_CREATED_BY,
                    "weddings_count": 0,
                    "total_revenue": 0.0,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )

            result = await self.vendor_profiles.insert_one(vendor)
            vendor["_id"] = str(result.inserted_id)
            logger.info(
                f"Inserted scraped vendor: {business_name} in {city} [{service_category}]"
            )
            return vendor

        except Exception as e:
            logger.error(
                f"Failed to upsert scraped vendor '{data.get('business_name')}': {str(e)}"
            )
            raise

    async def get_vendor_profiles(
        self,
        created_by: Optional[str] = None,
        category: Optional[str] = None,
        is_preferred: Optional[bool] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[dict]:
        """Get vendor profiles with filtering. If created_by is None, returns all active vendors."""
        try:
            query: dict = {"is_active": True}
            if created_by is not None:
                query["created_by"] = created_by

            if category:
                query["service_category"] = category
            if is_preferred is not None:
                query["is_preferred"] = is_preferred
            if tags:
                query["tags"] = {"$all": tags}
            if search:
                query["$or"] = [
                    {"business_name": {"$regex": search, "$options": "i"}},
                    {"contact_name": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                    {"service_description": {"$regex": search, "$options": "i"}},
                ]

            cursor = (
                self.vendor_profiles.find(query)
                .skip(skip)
                .limit(limit)
                .sort("business_name", 1)
            )
            vendors = await cursor.to_list(length=limit)

            for v in vendors:
                v["_id"] = str(v["_id"])
                # Serialize datetime objects for JSON response
                if isinstance(v.get("created_at"), datetime):
                    v["created_at"] = v["created_at"].isoformat()
                if isinstance(v.get("updated_at"), datetime):
                    v["updated_at"] = v["updated_at"].isoformat()

            return vendors

        except HTTPException:
            raise
        except ValueError as e:
            logger.warning(f"Invalid filter parameters: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to fetch vendor profiles: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch vendors")

    async def get_vendor_profile(self, vendor_id: str, created_by: str) -> dict:
        """Get a single vendor profile"""
        try:
            vendor = await self.vendor_profiles.find_one(
                {"_id": ObjectId(vendor_id), "created_by": created_by}
            )

            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")

            vendor["_id"] = str(vendor["_id"])
            # Serialize datetime objects for JSON response
            if isinstance(vendor.get("created_at"), datetime):
                vendor["created_at"] = vendor["created_at"].isoformat()
            if isinstance(vendor.get("updated_at"), datetime):
                vendor["updated_at"] = vendor["updated_at"].isoformat()
            return vendor

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching vendor profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch vendor")

    async def update_vendor_profile(
        self, vendor_id: str, data: dict, created_by: Optional[str] = None
    ) -> dict:
        """Update a vendor profile. If created_by is None, updates any vendor (root admin)."""
        try:
            query: dict = {"_id": ObjectId(vendor_id)}
            if created_by is not None:
                query["created_by"] = created_by
            existing = await self.vendor_profiles.find_one(query)
            if not existing:
                raise HTTPException(status_code=404, detail="Vendor not found")

            # Remove None values
            update_data = {k: v for k, v in data.items() if v is not None}
            update_data = self._normalize_vendor_category_data(
                update_data, existing=existing
            )
            update_data["updated_at"] = datetime.now(timezone.utc)

            result = await self.vendor_profiles.find_one_and_update(
                query, {"$set": update_data}, return_document=True
            )

            if not result:
                raise HTTPException(status_code=404, detail="Vendor not found")

            result["_id"] = str(result["_id"])
            # Serialize datetime objects for JSON response
            if isinstance(result.get("created_at"), datetime):
                result["created_at"] = result["created_at"].isoformat()
            if isinstance(result.get("updated_at"), datetime):
                result["updated_at"] = result["updated_at"].isoformat()
            return result

        except HTTPException:
            raise
        except ValueError as e:
            logger.warning(f"Invalid update data: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to update vendor profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update vendor")

    async def delete_vendor_profile(
        self, vendor_id: str, created_by: Optional[str] = None
    ) -> dict:
        """Soft delete a vendor profile. If created_by is None, deletes any vendor (root admin)."""
        try:
            query: dict = {"_id": ObjectId(vendor_id)}
            if created_by is not None:
                query["created_by"] = created_by
            result = await self.vendor_profiles.find_one_and_update(
                query,
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                return_document=True,
            )

            if not result:
                raise HTTPException(status_code=404, detail="Vendor not found")

            return {"message": "Vendor deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting vendor profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete vendor")

    async def get_vendor_categories_used(self, created_by: str) -> List[str]:
        """Get list of categories used by planner's vendors"""
        try:
            pipeline = [
                {"$match": {"created_by": created_by, "is_active": True}},
                {"$group": {"_id": "$service_category"}},
                {"$sort": {"_id": 1}},
            ]
            result = await self.vendor_profiles.aggregate(pipeline).to_list(length=100)
            return [r["_id"] for r in result if r["_id"]]

        except Exception as e:
            logger.error(f"Error getting vendor categories: {str(e)}")
            return []

    async def get_dashboard_counts(
        self, created_by: str, wedding_id: Optional[str] = None
    ) -> dict:
        """
        Get dashboard counts efficiently using MongoDB aggregation.
        Much faster than loading all documents just to count them.
        """
        try:
            # Vendor counts
            vendor_total = await self.vendor_profiles.count_documents(
                {"created_by": created_by, "is_active": True}
            )
            vendor_preferred = await self.vendor_profiles.count_documents(
                {"created_by": created_by, "is_active": True, "is_preferred": True}
            )

            # Contract counts
            contract_query = {"created_by": created_by}
            if wedding_id:
                contract_query["wedding_id"] = wedding_id

            contract_total = await self.vendor_contracts.count_documents(contract_query)
            contract_pending = await self.vendor_contracts.count_documents(
                {**contract_query, "status": {"$in": ["draft", "sent", "viewed"]}}
            )
            contract_signed = await self.vendor_contracts.count_documents(
                {**contract_query, "status": "signed"}
            )

            # Payment milestone counts and aggregation
            milestone_query = {}
            if wedding_id:
                milestone_query["wedding_id"] = wedding_id

            milestone_pending = await self.payment_milestones.count_documents(
                {**milestone_query, "status": {"$in": ["pending", "due"]}}
            )
            milestone_overdue = await self.payment_milestones.count_documents(
                {**milestone_query, "status": "overdue"}
            )

            # Get totals using aggregation
            payment_pipeline = [
                {"$match": milestone_query} if milestone_query else {"$match": {}},
                {
                    "$group": {
                        "_id": None,
                        "total_paid": {"$sum": "$paid_amount"},
                        "total_due": {
                            "$sum": {
                                "$cond": [
                                    {"$in": ["$status", ["pending", "due", "overdue"]]},
                                    "$amount",
                                    0,
                                ]
                            }
                        },
                    }
                },
            ]
            payment_totals = await self.payment_milestones.aggregate(
                payment_pipeline
            ).to_list(1)
            totals = (
                payment_totals[0]
                if payment_totals
                else {"total_paid": 0, "total_due": 0}
            )

            return {
                "vendors": {"total": vendor_total, "preferred": vendor_preferred},
                "contracts": {
                    "total": contract_total,
                    "pending": contract_pending,
                    "signed": contract_signed,
                },
                "payments": {
                    "pending_count": milestone_pending,
                    "overdue_count": milestone_overdue,
                    "total_paid": totals.get("total_paid", 0),
                    "total_due": totals.get("total_due", 0),
                },
            }

        except Exception as e:
            logger.error(f"Error getting dashboard counts: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to get dashboard counts"
            )

    # =========================================================================
    # VENDOR ASSIGNMENT (Link to Wedding)
    # =========================================================================

    async def assign_vendor_to_wedding(
        self,
        vendor_profile_id: str,
        wedding_id: str,
        created_by: Optional[str] = None,
        budget_category_id: Optional[str] = None,
        service_notes: Optional[str] = None,
    ) -> dict:
        """Assign a vendor from directory to a wedding"""
        try:
            # Get vendor profile (scoped by planner ownership — prevents
            # cross-tenant assignment via a client-supplied vendor_profile_id).
            vendor = await self._get_owned_vendor_profile(vendor_profile_id, created_by)
            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")

            # Verify the wedding belongs to the actor planner (was previously
            # not fetched at all, so any wedding_id was trusted).
            wedding = await self._get_owned_wedding(wedding_id, created_by)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Check if already assigned
            existing = await self.vendor_assignments.find_one(
                {"vendor_profile_id": vendor_profile_id, "wedding_id": wedding_id}
            )
            if existing:
                raise HTTPException(
                    status_code=409, detail="Vendor already assigned to this wedding"
                )

            assignment = {
                "wedding_id": wedding_id,
                "vendor_profile_id": vendor_profile_id,
                "budget_category_id": budget_category_id,
                "status": "inquiry",
                "vendor_name": vendor["business_name"],
                "vendor_email": vendor["email"],
                "service_category": vendor["service_category"],
                "custom_service_category": vendor.get("custom_service_category"),
                "quote_ids": [],
                "contract_id": None,
                "service_notes": service_notes,
                "quoted_amount": None,
                "contracted_amount": None,
                "paid_amount": 0.0,
                "created_by": created_by,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            result = await self.vendor_assignments.insert_one(assignment)
            assignment["_id"] = str(result.inserted_id)

            # Update vendor's wedding count
            await self.vendor_profiles.update_one(
                {"_id": ObjectId(vendor_profile_id)},
                {
                    "$inc": {"weddings_count": 1},
                    "$set": {"last_used_at": datetime.now(timezone.utc)},
                },
            )

            return assignment

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error assigning vendor: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to assign vendor")

    async def get_wedding_vendors(self, wedding_id: str, created_by: str) -> List[dict]:
        """Get all vendors assigned to a wedding"""
        try:
            cursor = self.vendor_assignments.find({"wedding_id": wedding_id})
            assignments = await cursor.to_list(length=100)

            for a in assignments:
                a["_id"] = str(a["_id"])

            return assignments

        except Exception as e:
            logger.error(f"Error fetching wedding vendors: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to fetch wedding vendors"
            )

    async def update_assignment_status(
        self,
        assignment_id: str,
        status: str,
        created_by: Optional[str] = None,
    ) -> dict:
        """Update vendor assignment status"""
        from app.models.vendor import VendorAssignmentStatus

        try:
            VendorAssignmentStatus(status)
        except ValueError:
            valid = [s.value for s in VendorAssignmentStatus]
            raise HTTPException(
                status_code=400, detail=f"Invalid status. Must be one of: {valid}"
            )

        try:
            # Pre-flight ownership check — keeps the planner-scoped query
            # in the helper module and raises 404 if the assignment is
            # missing or owned by another planner. The subsequent
            # find_one_and_update is then re-scoped on _id + created_by
            # so a TOCTOU swap between check and update cannot succeed.
            owned = await self._get_owned_assignment(assignment_id, created_by)
            if not owned:
                raise HTTPException(status_code=404, detail="Assignment not found")

            update_query: Dict[str, Any] = {"_id": ObjectId(assignment_id)}
            normalized_actor = normalize_planner_email(created_by)
            if normalized_actor is not None:
                update_query["created_by"] = normalized_actor

            result = await self.vendor_assignments.find_one_and_update(
                update_query,
                {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
                return_document=True,
            )

            if not result:
                raise HTTPException(status_code=404, detail="Assignment not found")

            result["_id"] = str(result["_id"])
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating assignment: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update assignment")

    # =========================================================================
    # CONTRACT TEMPLATES
    # =========================================================================

    async def create_contract_template(self, data: dict, created_by: str) -> dict:
        """Create a contract template"""
        try:
            template = {
                "name": data["name"],
                "description": data.get("description"),
                "service_category": data["service_category"],
                "sections": data.get("sections", []),
                "terms_and_conditions": data.get("terms_and_conditions"),
                "cancellation_policy": data.get("cancellation_policy"),
                "default_deposit_percentage": data.get("default_deposit_percentage"),
                "default_payment_schedule": data.get("default_payment_schedule", []),
                "created_by": created_by,
                "is_system_template": False,
                "is_public": data.get("is_public", False),
                "is_active": True,
                "usage_count": 0,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            result = await self.contract_templates.insert_one(template)
            template["_id"] = str(result.inserted_id)

            return template

        except Exception as e:
            logger.error(f"Error creating contract template: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create template")

    async def get_contract_templates(
        self,
        created_by: str,
        category: Optional[str] = None,
        include_system: bool = True,
    ) -> List[dict]:
        """Get contract templates available to planner"""
        try:
            or_conditions: List[Dict[str, Any]] = [{"created_by": created_by}]
            if include_system:
                or_conditions.append({"is_system_template": True})

            query = {"$or": or_conditions, "is_active": True}

            if category:
                query["service_category"] = category

            cursor = self.contract_templates.find(query).sort("name", 1)
            templates = await cursor.to_list(length=100)

            for t in templates:
                t["_id"] = str(t["_id"])

            return templates

        except Exception as e:
            logger.error(f"Error fetching templates: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch templates")

    async def get_contract_template(self, template_id: str) -> dict:
        """Get a specific contract template"""
        try:
            template = await self.contract_templates.find_one(
                {"_id": ObjectId(template_id)}
            )
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            template["_id"] = str(template["_id"])
            return template

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching template: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch template")

    # =========================================================================
    # CONTRACTS
    # =========================================================================

    def _populate_placeholders(self, content: str, data: dict) -> str:
        """Replace placeholders in content with actual data"""
        if not content:
            return content

        placeholders = {
            "{{vendor_name}}": data.get("vendor_name", ""),
            "{{vendor_email}}": data.get("vendor_email", ""),
            "{{vendor_phone}}": data.get("vendor_phone", ""),
            "{{vendor_address}}": data.get("vendor_address", ""),
            "{{couple_names}}": data.get("couple_names", ""),
            "{{wedding_date}}": data.get("wedding_date", ""),
            "{{wedding_venue}}": data.get("wedding_venue", ""),
            "{{service_category}}": data.get("service_category", ""),
            "{{total_amount}}": str(data.get("total_amount", "")),
            "{{deposit_amount}}": str(data.get("deposit_amount", "")),
            "{{planner_name}}": data.get("planner_name", ""),
            "{{planner_email}}": data.get("planner_email", ""),
            "{{planner_company}}": data.get("planner_company", ""),
            "{{contract_date}}": datetime.now(timezone.utc).strftime("%B %d, %Y"),
            "{{contract_number}}": data.get("contract_number", ""),
        }

        for placeholder, value in placeholders.items():
            content = content.replace(placeholder, str(value) if value else "")

        return content

    async def create_contract(
        self,
        wedding_id: str,
        vendor_profile_id: str,
        created_by: Optional[str] = None,
        template_id: Optional[str] = None,
        quote_id: Optional[str] = None,
        total_amount: float = 0,
        custom_sections: Optional[List[Dict]] = None,
        deposit_percentage: Optional[float] = None,
        service_date: Optional[datetime] = None,
        service_location: Optional[str] = None,
    ) -> dict:
        """Create a new vendor contract"""
        try:
            contract_id = ObjectId()
            # Get planner's contract settings (with fallback to system defaults)
            planner_settings = await self._get_planner_contract_settings(created_by)

            # Get vendor profile (scoped by planner ownership — prevents
            # cross-tenant write via a client-supplied vendor_profile_id).
            vendor = await self._get_owned_vendor_profile(vendor_profile_id, created_by)
            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")

            # Get wedding (scoped by planner ownership — prevents
            # cross-tenant write via a client-supplied wedding_id).
            wedding = await self._get_owned_wedding(wedding_id, created_by)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Get planner info
            planner = await self.users.find_one({"email": created_by})

            # Prepare placeholder data
            placeholder_data = {
                "vendor_name": vendor["business_name"],
                "vendor_email": vendor["email"],
                "vendor_phone": vendor.get("phone", ""),
                "vendor_address": vendor.get("address", ""),
                "couple_names": wedding.get("couple_names", ""),
                "wedding_date": wedding.get("date", ""),
                "wedding_venue": wedding.get("venue", ""),
                "service_category": self._get_vendor_service_label(
                    vendor["service_category"],
                    vendor.get("custom_service_category"),
                ),
                "total_amount": total_amount,
                "deposit_amount": (
                    (total_amount * deposit_percentage / 100)
                    if deposit_percentage
                    else 0
                ),
                "planner_name": (
                    f"{planner.get('first_name', '')} {planner.get('last_name', '')}".strip()
                    if planner
                    else ""
                ),
                "planner_email": created_by,
                "planner_company": planner.get("company_name", "") if planner else "",
                "contract_number": self._generate_contract_number(),
            }

            # Build contract sections
            sections = []
            terms_and_conditions = None
            cancellation_policy = None

            if template_id:
                template = await self.get_contract_template(template_id)
                for section in template.get("sections", []):
                    sections.append(
                        {
                            "id": section.get("id", str(ObjectId())),
                            "title": section["title"],
                            "content": self._populate_placeholders(
                                section["content"], placeholder_data
                            ),
                            "order": section.get("order", 0),
                        }
                    )
                terms_and_conditions = self._populate_placeholders(
                    template.get("terms_and_conditions", ""), placeholder_data
                )
                cancellation_policy = self._populate_placeholders(
                    template.get("cancellation_policy", ""), placeholder_data
                )

                # Increment template usage
                await self.contract_templates.update_one(
                    {"_id": ObjectId(template_id)}, {"$inc": {"usage_count": 1}}
                )

            # Add custom sections
            if custom_sections:
                for cs in custom_sections:
                    sections.append(
                        {
                            "id": str(ObjectId()),
                            "title": cs.get("title", "Additional Terms"),
                            "content": self._populate_placeholders(
                                cs.get("content", ""), placeholder_data
                            ),
                            "order": cs.get("order", len(sections)),
                        }
                    )

            # Calculate deposit using planner's configured settings
            deposit_amount = None
            deposit_due_date = None
            if deposit_percentage and total_amount:
                deposit_amount = total_amount * deposit_percentage / 100
                deposit_due_date = datetime.now(timezone.utc) + timedelta(
                    days=planner_settings["deposit_due_days"]
                )

            # Inherit budget_category_id from the vendor's assignment for this
            # wedding so milestone payments can roll up into the budget
            # tracker. Without this lookup the field stayed None forever and
            # the $inc against budget_categories.actual_spent in record_payment
            # was unreachable in practice.
            existing_assignment = await self.vendor_assignments.find_one(
                {
                    "vendor_profile_id": vendor_profile_id,
                    "wedding_id": wedding_id,
                },
                {"budget_category_id": 1, "contract_id": 1},
            )
            assigned_category_id = (existing_assignment or {}).get("budget_category_id")
            if assigned_category_id is None:
                logger.warning(
                    "Creating contract with no budget_category_id: "
                    "no assignment-with-category found for vendor %s on wedding %s. "
                    "Milestone payments will not roll up into budget tracking until "
                    "the contract is linked to a category.",
                    vendor_profile_id,
                    wedding_id,
                )

            contract = {
                "_id": contract_id,
                "wedding_id": wedding_id,
                "vendor_profile_id": vendor_profile_id,
                "vendor_quote_id": quote_id,
                "budget_category_id": assigned_category_id,
                "template_id": template_id,
                "vendor_name": vendor["business_name"],
                "vendor_email": vendor["email"],
                "vendor_phone": vendor.get("phone"),
                "vendor_address": vendor.get("address"),
                "service_category": vendor["service_category"],
                "custom_service_category": vendor.get("custom_service_category"),
                "contract_title": f"{self._get_vendor_service_label(vendor['service_category'], vendor.get('custom_service_category'))} Services Contract",
                "contract_number": placeholder_data["contract_number"],
                "sections": sections,
                "terms_and_conditions": terms_and_conditions,
                "cancellation_policy": cancellation_policy,
                "total_amount": total_amount,
                "currency": "USD",
                "deposit_amount": deposit_amount,
                "deposit_due_date": deposit_due_date,
                "status": ContractStatus.DRAFT.value,
                "service_date": service_date,
                "service_location": service_location,
                "created_by": created_by,
                "version_number": 1,
                "root_contract_id": str(contract_id),
                "parent_contract_id": None,
                "supersedes_contract_id": None,
                "superseded_by_contract_id": None,
                "is_current_version": True,
                "contract_kind": ContractKind.ORIGINAL.value,
                "amendment_reason": None,
                "superseded_at": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                **self._build_inactive_contract_token_fields(),
            }

            await self.vendor_contracts.insert_one(contract)
            self._serialize_doc(contract)
            self._attach_contract_version_metadata(contract)

            # Link the new contract back to the assignment so the wedding-detail
            # Vendors tab (and any other surface that reads from the assignment)
            # can show the contract immediately, not only after sign. We only
            # set contract_id when it's currently null — first-contract-wins
            # semantics, matching the prior behavior that sign_contract did at
            # sign time. Status is intentionally NOT changed: the documented
            # state machine reserves "contracted" for SIGNED, and a draft
            # contract isn't signed.
            if existing_assignment and not existing_assignment.get("contract_id"):
                await self.vendor_assignments.update_one(
                    {"_id": existing_assignment["_id"]},
                    {
                        "$set": {
                            "contract_id": str(contract_id),
                            "contracted_amount": total_amount,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )

            # Update quote if converting from quote
            if quote_id:
                await self.vendor_quotes.update_one(
                    {"_id": ObjectId(quote_id)},
                    {
                        "$set": {
                            "status": QuoteStatus.CONVERTED.value,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )

            await self._log_contract_activity(
                contract_id=str(contract_id),
                root_contract_id=str(contract_id),
                activity_type=VendorContractActivityType.CONTRACT_CREATED,
                title="Contract created",
                description=f"Created draft contract for {vendor['business_name']}.",
                actor_type="planner",
                actor_identifier=created_by,
                actor_display_name=created_by,
                metadata={
                    "contract_number": contract["contract_number"],
                    "contract_kind": ContractKind.ORIGINAL.value,
                    "version_number": 1,
                },
                created_at=contract["created_at"],
            )

            logger.info(
                f"Created contract {contract['contract_number']} for vendor {vendor['business_name']}"
            )
            return contract

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating contract: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create contract: {str(e)}"
            )

    async def get_contracts(
        self,
        created_by: str,
        wedding_id: Optional[str] = None,
        vendor_profile_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[dict]:
        """Get contracts for a planner"""
        try:
            query: Dict[str, Any] = {
                "created_by": created_by,
                "$or": [
                    {"is_current_version": {"$exists": False}},
                    {"is_current_version": True},
                ],
            }

            if wedding_id:
                query["wedding_id"] = wedding_id
            if vendor_profile_id:
                query["vendor_profile_id"] = vendor_profile_id
            if status:
                query["status"] = status

            cursor = (
                self.vendor_contracts.find(query)
                .skip(skip)
                .limit(limit)
                .sort("created_at", -1)
            )
            contracts = await cursor.to_list(length=limit)

            for c in contracts:
                self._serialize_doc(c)
                self._attach_contract_version_metadata(c)

            return contracts

        except HTTPException:
            raise
        except ValueError as e:
            logger.warning(f"Invalid filter parameters: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to fetch contracts: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch contracts")

    async def get_contract(
        self,
        contract_id: str,
        created_by: Optional[str] = None,
        include_couple_contact: bool = False,
    ) -> dict:
        """
        Get a specific contract.

        Args:
            contract_id: The contract ID to fetch
            created_by: If provided, verifies the contract belongs to this planner (authorization check)
            include_couple_contact: If True, enrich the response with the
                couple's email and display name (1-2 extra Mongo reads). Only
                the admin contract-detail endpoint needs this; internal
                callers (revisions, signing, payment recording, lineage, etc.)
                leave it False to avoid the per-call lookup cost.
        """
        try:
            obj_id = validate_object_id(contract_id, "contract ID")

            query: Dict[str, Any] = {"_id": obj_id}
            if created_by:
                query["created_by"] = created_by

            contract = await self.vendor_contracts.find_one(query)
            if not contract:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Contract not found"
                        if not created_by
                        else "Contract not found or access denied"
                    ),
                )

            self._serialize_doc(contract)
            self._attach_contract_version_metadata(contract)

            if include_couple_contact:
                # Defensive enrichment: surface couple contact info for the
                # detail view (used by the "Send Payment Link to Couple" UI).
                # Never let a missing/failed lookup 500 the contract response.
                try:
                    couple_contact = await self._resolve_couple_contact(
                        contract.get("wedding_id"),
                        contract.get("created_by"),
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to resolve couple contact for contract {contract_id}: {e}"
                    )
                    couple_contact = {"couple_email": None, "couple_names": None}

                contract["couple_email"] = couple_contact.get("couple_email")
                contract["couple_names"] = couple_contact.get("couple_names")

            return contract

        except HTTPException:
            raise
        except ValueError as e:
            logger.warning(f"Invalid contract ID format: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to fetch contract: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch contract")

    async def _validate_contract_public_token(
        self, contract_id: str, raw_token: str
    ) -> dict:
        """Validate a public vendor contract token against the persisted hash and lifecycle rules."""
        contract = await self.get_contract(contract_id)

        if not self._is_contract_current(contract):
            raise HTTPException(
                status_code=410,
                detail="This contract version has been replaced",
            )

        if contract.get("token_revoked_at"):
            raise HTTPException(
                status_code=403, detail="Contract link is no longer active"
            )

        token_expires_at = contract.get("token_expires_at")
        if token_expires_at and token_expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="Contract link has expired")

        stored_hash = contract.get("access_token_hash")
        if not stored_hash:
            raise HTTPException(status_code=403, detail="Contract link is not active")

        if not self._verify_contract_access_token(raw_token, stored_hash):
            raise HTTPException(
                status_code=404, detail="Contract not found or invalid token"
            )

        return contract

    async def get_contract_by_token(self, contract_id: str, token: str) -> dict:
        """Get contract for vendor access (public endpoint)"""
        try:
            contract = await self._validate_contract_public_token(contract_id, token)
            viewed_at = datetime.now(timezone.utc)
            first_view = not contract.get("viewed_at")

            view_update: Dict[str, Any] = {
                "token_last_viewed_at": viewed_at,
            }
            if first_view:
                view_update["viewed_at"] = viewed_at
                if contract.get("status") == ContractStatus.SENT.value:
                    view_update["status"] = ContractStatus.VIEWED.value
                    view_update["updated_at"] = viewed_at

            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": view_update},
            )

            contract["token_last_viewed_at"] = viewed_at
            if first_view:
                contract["viewed_at"] = viewed_at
                if contract.get("status") == ContractStatus.SENT.value:
                    contract["status"] = ContractStatus.VIEWED.value
                await self._log_contract_activity(
                    contract_id=contract_id,
                    root_contract_id=self._get_root_contract_id(contract),
                    activity_type=VendorContractActivityType.CONTRACT_VIEWED,
                    title="Contract viewed",
                    description=None,
                    actor_type="vendor",
                    actor_identifier=contract.get("vendor_email"),
                    actor_display_name=contract.get("vendor_name"),
                    created_at=viewed_at,
                )

            return self._sanitize_public_contract_response(contract)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching contract by token: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch contract")

    async def create_contract_revision(
        self,
        contract_id: str,
        created_by: str,
        revision_kind: str,
        reason: Optional[str] = None,
        copy_sections: bool = True,
        copy_terms_and_conditions: bool = True,
        copy_cancellation_policy: bool = True,
        copy_custom_clauses: bool = True,
    ) -> dict:
        """Create a new draft revision or amendment from the current live contract."""
        try:
            source_contract = await self.get_contract(
                contract_id, created_by=created_by
            )

            if not self._is_contract_current(source_contract):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot create a revision from a historical contract version",
                )

            if not self._can_create_revision_from_status(source_contract["status"]):
                raise HTTPException(
                    status_code=400,
                    detail="Only sent, viewed, or signed contracts can be revised",
                )

            if revision_kind not in {
                ContractKind.REVISION.value,
                ContractKind.AMENDMENT.value,
            }:
                raise HTTPException(
                    status_code=400,
                    detail="Revision kind must be 'revision' or 'amendment'",
                )

            root_contract_id = self._get_root_contract_id(source_contract)
            next_version_number = await self._get_next_contract_version_number(
                root_contract_id=root_contract_id,
                created_by=created_by,
            )

            revision_contract = self._build_contract_revision_copy(
                source_contract=source_contract,
                revision_kind=revision_kind,
                next_version_number=next_version_number,
                reason=reason,
                copy_sections=copy_sections,
                copy_terms_and_conditions=copy_terms_and_conditions,
                copy_cancellation_policy=copy_cancellation_policy,
                copy_custom_clauses=copy_custom_clauses,
            )

            await self.vendor_contracts.insert_one(revision_contract)
            self._serialize_doc(revision_contract)
            self._attach_contract_version_metadata(revision_contract)
            await self._log_contract_activity(
                contract_id=revision_contract["id"],
                root_contract_id=root_contract_id,
                activity_type=VendorContractActivityType.REVISION_CREATED,
                title=(
                    "Amendment draft created"
                    if revision_kind == ContractKind.AMENDMENT.value
                    else "Revision draft created"
                ),
                description=reason
                or (
                    "Created from the current contract version."
                    if revision_kind == ContractKind.REVISION.value
                    else "Created from the signed contract version."
                ),
                actor_type="planner",
                actor_identifier=created_by,
                actor_display_name=created_by,
                metadata={
                    "contract_kind": revision_kind,
                    "version_number": next_version_number,
                    "parent_contract_id": revision_contract.get("parent_contract_id"),
                    "supersedes_contract_id": revision_contract.get(
                        "supersedes_contract_id"
                    ),
                },
                created_at=revision_contract["created_at"],
            )
            return revision_contract

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating contract revision: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to create contract revision"
            )

    async def get_contract_revision_history(
        self, contract_id: str, created_by: str
    ) -> dict:
        """Return ordered version lineage for the contract chain containing this contract."""
        try:
            contract = await self.get_contract(contract_id, created_by=created_by)
            root_contract_id = self._get_root_contract_id(contract)
            lineage = await self._get_contract_lineage(
                root_contract_id=root_contract_id,
                created_by=created_by,
            )

            current_contract_id = next(
                (
                    lineage_contract["id"]
                    for lineage_contract in lineage
                    if lineage_contract.get("is_current_version", True)
                ),
                contract["id"],
            )

            versions = [
                {
                    "id": lineage_contract["id"],
                    "contract_number": lineage_contract.get("contract_number"),
                    "version_number": lineage_contract.get("version_number", 1),
                    "contract_kind": lineage_contract.get(
                        "contract_kind", ContractKind.ORIGINAL.value
                    ),
                    "status": lineage_contract["status"],
                    "is_current_version": lineage_contract.get(
                        "is_current_version", True
                    ),
                    "parent_contract_id": lineage_contract.get("parent_contract_id"),
                    "supersedes_contract_id": lineage_contract.get(
                        "supersedes_contract_id"
                    ),
                    "superseded_by_contract_id": lineage_contract.get(
                        "superseded_by_contract_id"
                    ),
                    "created_at": lineage_contract["created_at"],
                    "sent_at": lineage_contract.get("sent_at"),
                    "signed_at": lineage_contract.get("signed_at"),
                }
                for lineage_contract in lineage
            ]

            return {
                "current_contract_id": current_contract_id,
                "root_contract_id": root_contract_id,
                "versions": versions,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting contract revision history: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to fetch contract revision history"
            )

    async def send_contract(
        self,
        contract_id: str,
        created_by: str,
        message: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
    ) -> dict:
        """Send contract to vendor via email"""
        try:
            # Authorization: verify contract belongs to this user
            contract = await self.get_contract(contract_id, created_by=created_by)

            if contract.get("contract_kind", ContractKind.ORIGINAL.value) in {
                ContractKind.REVISION.value,
                ContractKind.AMENDMENT.value,
            } and not contract.get("supersedes_contract_id"):
                raise HTTPException(
                    status_code=400,
                    detail="Revision draft is missing its superseded contract reference",
                )

            if contract["status"] not in [
                ContractStatus.DRAFT.value,
                ContractStatus.PENDING_REVIEW.value,
            ]:
                raise HTTPException(
                    status_code=400, detail="Contract has already been sent"
                )

            superseded_contract: Optional[Dict[str, Any]] = None
            if contract.get("contract_kind") in {
                ContractKind.REVISION.value,
                ContractKind.AMENDMENT.value,
            }:
                superseded_contract = await self.get_contract(
                    contract["supersedes_contract_id"],
                    created_by=created_by,
                )

                if not self._is_contract_current(superseded_contract):
                    raise HTTPException(
                        status_code=409,
                        detail="This revision is based on an outdated contract version",
                    )

                if self._get_root_contract_id(
                    superseded_contract
                ) != self._get_root_contract_id(contract):
                    raise HTTPException(
                        status_code=400,
                        detail="Revision lineage does not match the contract it supersedes",
                    )

            # Get wedding info
            wedding = await self._get_wedding(contract["wedding_id"])
            couple_names = (
                wedding.get("couple_names", "our clients") if wedding else "our clients"
            )

            planner_settings = await self._get_planner_contract_settings(created_by)
            raw_token, token_update = self._issue_contract_access_token(
                contract_id=contract_id,
                planner_settings=planner_settings,
            )

            # Generate contract link
            base_url = os.getenv("FRONTEND_URL", "")
            contract_link = self._build_public_vendor_contract_link(
                base_url, contract_id, raw_token
            )

            # Build email
            subject = f"Contract for Review: {contract['contract_title']}"
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #1e3a8a 0%, #d97706 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                    .content {{ background: white; padding: 30px; border: 1px solid #e5e7eb; }}
                    .button {{ display: inline-block; background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
                    .details {{ background: #f3f4f6; padding: 15px; border-radius: 6px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Contract Ready for Review</h1>
                    </div>
                    <div class="content">
                        <p>Dear {contract["vendor_name"]},</p>

                        <p>A contract has been prepared for your services for the wedding of <strong>{couple_names}</strong>.</p>

                        {f"<p>{message}</p>" if message else ""}

                        <div class="details">
                            <h3>Contract Details:</h3>
                            <p><strong>Contract:</strong> {contract["contract_title"]}</p>
                            <p><strong>Contract #:</strong> {contract.get("contract_number", "N/A")}</p>
                            <p><strong>Service:</strong> {self._get_vendor_service_label(contract["service_category"], contract.get("custom_service_category"))}</p>
                            <p><strong>Total Amount:</strong> ${contract["total_amount"]:,.2f}</p>
                            {f"<p><strong>Deposit Required:</strong> ${contract['deposit_amount']:,.2f}</p>" if contract.get("deposit_amount") else ""}
                        </div>

                        <p>Please review the contract and sign electronically by clicking the button below:</p>

                        <div style="text-align: center;">
                            <a href="{contract_link}" class="button">Review & Sign Contract</a>
                        </div>

                        <p>If you have any questions or need to discuss any terms, please don't hesitate to contact us.</p>

                        <p>Best regards,<br>Wedding Planning Team</p>
                    </div>
                </div>
            </body>
            </html>
            """

            now = token_update["token_last_sent_at"]

            send_update: Dict[str, Any] = {
                "status": ContractStatus.SENT.value,
                "sent_at": now,
                "updated_at": now,
                "root_contract_id": self._get_root_contract_id(contract),
                "version_number": contract.get("version_number", 1),
                "parent_contract_id": contract.get("parent_contract_id"),
                "supersedes_contract_id": contract.get("supersedes_contract_id"),
                "superseded_by_contract_id": None,
                "is_current_version": True,
                "contract_kind": contract.get(
                    "contract_kind", ContractKind.ORIGINAL.value
                ),
                "amendment_reason": contract.get("amendment_reason"),
                "superseded_at": None,
                **token_update,
            }
            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": send_update},
            )

            if superseded_contract:
                await self._mark_contract_as_superseded(
                    contract_id=superseded_contract["id"],
                    superseded_by_contract_id=contract_id,
                )
                await self._revoke_contract_access_token(superseded_contract["id"])

            await self._log_contract_activity(
                contract_id=contract_id,
                root_contract_id=self._get_root_contract_id(contract),
                activity_type=VendorContractActivityType.CONTRACT_SENT,
                title="Contract sent",
                description=f"Sent to {contract['vendor_email']} for review and signature.",
                actor_type="planner",
                actor_identifier=created_by,
                actor_display_name=created_by,
                metadata={
                    "status": ContractStatus.SENT.value,
                    "cc_emails": cc_emails or [],
                },
                created_at=now,
            )

            if superseded_contract:
                await self._log_contract_activity(
                    contract_id=superseded_contract["id"],
                    root_contract_id=self._get_root_contract_id(superseded_contract),
                    activity_type=VendorContractActivityType.CONTRACT_SUPERSEDED,
                    title="Contract superseded",
                    description=(
                        f"Replaced by version {contract.get('version_number', 1)}."
                    ),
                    actor_type="planner",
                    actor_identifier=created_by,
                    actor_display_name=created_by,
                    metadata={
                        "superseded_by_contract_id": contract_id,
                        "superseding_version_number": contract.get("version_number", 1),
                        "superseding_contract_kind": contract.get(
                            "contract_kind", ContractKind.ORIGINAL.value
                        ),
                    },
                    created_at=now,
                )

            email_warning: Optional[str] = None
            try:
                email_result = await self.email_service.send_email(
                    to_email=contract["vendor_email"],
                    subject=subject,
                    html_content=html_content,
                    from_name="Wedding Planning Team",
                )
                if not email_result.get("success"):
                    email_warning = "Contract was secured and marked sent, but email delivery failed."
                else:
                    await self._log_communication(
                        vendor_profile_id=contract["vendor_profile_id"],
                        comm_type="contract_sent",
                        content=f"Contract sent: {contract['contract_title']}",
                        created_by=created_by,
                        wedding_id=contract["wedding_id"],
                        contract_id=contract_id,
                        subject=subject,
                        sent_to=contract["vendor_email"],
                    )
            except Exception as email_error:
                logger.error(
                    "Contract email delivery failed after send commit: %s", email_error
                )
                email_warning = (
                    "Contract was secured and marked sent, but email delivery failed."
                )

            response = {
                "message": "Contract sent successfully",
                "sent_to": contract["vendor_email"],
            }
            if email_warning:
                response["warning"] = email_warning
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending contract: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to send contract: {str(e)}"
            )

    async def sign_contract(
        self,
        contract_id: str,
        token: str,
        signer_name: str,
        signer_email: str,
        signature_ip: Optional[str] = None,
    ) -> dict:
        """Sign a contract (vendor action)."""
        try:
            contract = await self._validate_contract_public_token(contract_id, token)

            if contract["status"] == ContractStatus.SIGNED.value:
                raise HTTPException(
                    status_code=400, detail="Contract has already been signed"
                )

            if contract["status"] not in [
                ContractStatus.SENT.value,
                ContractStatus.VIEWED.value,
            ]:
                raise HTTPException(
                    status_code=400, detail="Contract cannot be signed in current state"
                )

            signed_at = datetime.now(timezone.utc)

            async def _sign_in_transaction(session: Any) -> None:
                await self.vendor_contracts.update_one(
                    {"_id": ObjectId(contract_id)},
                    {
                        "$set": {
                            "status": ContractStatus.SIGNED.value,
                            "signed_at": signed_at,
                            "signed_by_name": signer_name,
                            "signed_by_email": signer_email,
                            "signature_ip": signature_ip,
                            "updated_at": signed_at,
                        }
                    },
                    session=session,
                )

                if contract.get("vendor_profile_id"):
                    await self.vendor_assignments.update_one(
                        {
                            "vendor_profile_id": contract["vendor_profile_id"],
                            "wedding_id": contract["wedding_id"],
                        },
                        {
                            "$set": {
                                "status": "contracted",
                                "contract_id": contract_id,
                                "contracted_amount": contract["total_amount"],
                                "updated_at": signed_at,
                            }
                        },
                        session=session,
                    )

            await self._run_required_transaction(
                "Vendor contract signing",
                _sign_in_transaction,
            )

            planner_email = contract["created_by"]
            subject = f"Contract Signed: {contract['vendor_name']}"
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Contract Signed!</h2>
                <p>Great news! {contract["vendor_name"]} has signed the contract.</p>
                <div style="background: #f3f4f6; padding: 15px; border-radius: 6px;">
                    <p><strong>Contract:</strong> {contract["contract_title"]}</p>
                    <p><strong>Signed by:</strong> {signer_name}</p>
                    <p><strong>Signed at:</strong> {signed_at.strftime("%B %d, %Y at %H:%M UTC")}</p>
                </div>
                <p>Log in to your dashboard to view the signed contract.</p>
            </body>
            </html>
            """

            try:
                await self.email_service.send_email(
                    to_email=planner_email,
                    subject=subject,
                    html_content=html_content,
                    from_name="Wedding Platform",
                )
            except Exception as email_error:
                logger.error(
                    "Planner notification failed after contract sign commit: %s",
                    email_error,
                )

            await self._log_contract_activity(
                contract_id=contract_id,
                root_contract_id=self._get_root_contract_id(contract),
                activity_type=VendorContractActivityType.CONTRACT_SIGNED,
                title="Contract signed",
                description=f"Signed by {signer_name}.",
                actor_type="vendor",
                actor_identifier=signer_email,
                actor_display_name=signer_name,
                metadata={"signature_ip": signature_ip},
                created_at=signed_at,
            )

            return {
                "message": "Contract signed successfully",
                "signed_at": signed_at.isoformat(),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error signing contract: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to sign contract")

    # =========================================================================
    # CONTRACT CUSTOMIZATION
    # =========================================================================

    async def update_contract(
        self, contract_id: str, data: dict, updated_by: str
    ) -> dict:
        """Update a contract (only draft contracts can be modified)"""
        try:
            # Authorization: verify contract belongs to this user
            contract = await self.get_contract(contract_id, created_by=updated_by)
            await self._ensure_contract_editable(contract)

            # Fields that can be updated
            allowed_fields = [
                "contract_title",
                "total_amount",
                "deposit_amount",
                "deposit_due_date",
                "terms_and_conditions",
                "cancellation_policy",
                "custom_clauses",
                "service_date",
                "service_start_time",
                "service_end_time",
                "service_location",
                "internal_notes",
                "sections",
            ]

            update_data = {
                k: v for k, v in data.items() if k in allowed_fields and v is not None
            }
            update_data["updated_at"] = datetime.now(timezone.utc)

            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)}, {"$set": update_data}
            )

            changed_fields = sorted(
                key for key in update_data.keys() if key != "updated_at"
            )
            if changed_fields:
                await self._log_contract_activity(
                    contract_id=contract_id,
                    root_contract_id=self._get_root_contract_id(contract),
                    activity_type=VendorContractActivityType.CONTRACT_UPDATED,
                    title="Contract updated",
                    description=(
                        f"Updated {', '.join(changed_fields)}."
                        if changed_fields
                        else None
                    ),
                    actor_type="planner",
                    actor_identifier=updated_by,
                    actor_display_name=updated_by,
                    metadata={"changed_fields": changed_fields},
                    created_at=update_data["updated_at"],
                )

            return await self.get_contract(contract_id, created_by=updated_by)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating contract: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update contract")

    async def update_contract_sections(
        self,
        contract_id: str,
        sections: List[Dict[str, Any]],
        updated_by: str,
        terms_and_conditions: Optional[str] = None,
        cancellation_policy: Optional[str] = None,
        custom_clauses: Optional[str] = None,
    ) -> dict:
        """Update contract sections - add, modify, or remove sections"""
        try:
            # Authorization: verify contract belongs to this user
            contract = await self.get_contract(contract_id, created_by=updated_by)
            await self._ensure_contract_editable(contract)

            # Validate sections
            processed_sections = []
            for i, section in enumerate(sections):
                processed_sections.append(
                    {
                        "id": section.get("id", str(ObjectId())),
                        "title": section.get("title", f"Section {i + 1}"),
                        "content": section.get("content", ""),
                        "order": section.get("order", i),
                    }
                )

            # Sort by order
            processed_sections.sort(key=lambda x: x["order"])

            update_data: Dict[str, Any] = {
                "sections": processed_sections,
                "updated_at": datetime.now(timezone.utc),
            }
            if terms_and_conditions is not None:
                update_data["terms_and_conditions"] = terms_and_conditions
            if cancellation_policy is not None:
                update_data["cancellation_policy"] = cancellation_policy
            if custom_clauses is not None:
                update_data["custom_clauses"] = custom_clauses

            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": update_data},
            )

            changed_parts = ["sections"]
            if terms_and_conditions is not None:
                changed_parts.append("terms_and_conditions")
            if cancellation_policy is not None:
                changed_parts.append("cancellation_policy")
            if custom_clauses is not None:
                changed_parts.append("custom_clauses")

            await self._log_contract_activity(
                contract_id=contract_id,
                root_contract_id=self._get_root_contract_id(contract),
                activity_type=VendorContractActivityType.CONTRACT_UPDATED,
                title="Contract document updated",
                description="Updated contract sections and document copy.",
                actor_type="planner",
                actor_identifier=updated_by,
                actor_display_name=updated_by,
                metadata={
                    "changed_fields": changed_parts,
                    "section_count": len(processed_sections),
                },
                created_at=update_data["updated_at"],
            )

            return await self.get_contract(contract_id, created_by=updated_by)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating contract sections: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to update contract sections"
            )

    # =========================================================================
    # FORM DATA INTEGRATION
    # =========================================================================

    async def get_form_data_for_contract(
        self, contract_id: str, created_by: Optional[str] = None
    ) -> dict:
        """
        Get vendor form submissions that can be used to populate contract fields.
        Looks for form submissions from the same vendor email.
        """
        try:
            # Authorization: verify contract belongs to this user if created_by is provided
            contract = await self.get_contract(contract_id, created_by=created_by)
            vendor_email = contract.get("vendor_email")

            if not vendor_email:
                return {
                    "vendor_submissions": [],
                    "available_fields": {},
                    "suggested_contract_fields": {},
                }

            # Find vendor form submissions for this vendor
            vendor_submissions = (
                await mongo.db["vendor_submissions"]
                .find({"vendor_email": vendor_email})
                .to_list(length=20)
            )

            # Also check vendor_forms that have been submitted
            vendor_forms = (
                await mongo.db["vendor_forms"]
                .find({"vendor_email": vendor_email, "status": "submitted"})
                .to_list(length=20)
            )

            submissions = []
            for sub in vendor_submissions:
                submissions.append(
                    self._summarize_contract_form_submission(
                        submission=sub,
                        source="vendor_submission",
                    )
                )

            for form in vendor_forms:
                if form.get("submission_data"):
                    submissions.append(
                        self._summarize_contract_form_submission(
                            submission=form,
                            source="vendor_form",
                        )
                    )

            # Extract available fields that could populate contract
            available_fields: Dict[str, Dict[str, Any]] = {}
            for sub in submissions:
                data = sub.get("data", {})
                if isinstance(data, dict):
                    for key, value in data.items():
                        if value and isinstance(value, (str, int, float)):
                            available_fields[key] = {
                                "value": value,
                                "source": sub.get("source", "unknown"),
                                "source_id": sub["_id"],
                                "original_key": key,
                            }

            return {
                "vendor_submissions": submissions,
                "available_fields": available_fields,
                "suggested_contract_fields": self._suggest_field_mappings(
                    available_fields
                ),
            }

        except Exception as e:
            logger.error(f"Error getting form data for contract: {str(e)}")
            return {
                "vendor_submissions": [],
                "available_fields": {},
                "suggested_contract_fields": {},
            }

    def _summarize_contract_form_submission(
        self, submission: Dict[str, Any], source: str
    ) -> Dict[str, Any]:
        """Normalize vendor form documents into a stable contract form-data summary."""
        raw_id = submission.get("_id")
        submission_data = submission.get("submission_data", {})
        submitted_at = (
            submission.get("submitted_at")
            or submission.get("created_at")
            or submission.get("updated_at")
        )
        form_name = (
            submission.get("form_name")
            or submission.get("title")
            or submission.get("name")
            or "Vendor Submission"
        )

        return {
            "_id": str(raw_id) if raw_id is not None else "",
            "form_name": form_name,
            "submitted_at": submitted_at,
            "source": source,
            "data": submission_data if isinstance(submission_data, dict) else {},
        }

    def _suggest_field_mappings(
        self, available_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Suggest mappings from form fields to contract placeholders"""
        mappings: Dict[str, Dict[str, Any]] = {}

        # Common field name patterns to contract placeholders
        patterns = {
            "portfolio": "{{vendor_portfolio}}",
            "portfolio_link": "{{vendor_portfolio}}",
            "packages": "{{service_packages}}",
            "price": "{{quoted_price}}",
            "price_range": "{{price_range}}",
            "availability": "{{vendor_availability}}",
            "experience": "{{years_experience}}",
            "equipment": "{{equipment_list}}",
            "menu": "{{menu_options}}",
            "dietary": "{{dietary_options}}",
            "service_style": "{{service_style}}",
            "specialties": "{{specialties}}",
            "hours": "{{coverage_hours}}",
            "deliverables": "{{deliverables}}",
            "timeline": "{{delivery_timeline}}",
        }

        for field_name, field_data in available_fields.items():
            field_lower = field_name.lower()
            for pattern, placeholder in patterns.items():
                if pattern in field_lower and placeholder not in mappings:
                    mappings[placeholder] = {
                        "source_field": field_name,
                        "value": field_data.get("value"),
                    }
                    break

        return mappings

    def _apply_placeholder_replacements(
        self, content: Optional[str], replacements: Dict[str, str]
    ) -> Optional[str]:
        """Apply placeholder replacements to an optional string field."""
        if content is None:
            return None

        updated = content
        for placeholder, value in replacements.items():
            updated = updated.replace(placeholder, value)
        return updated

    async def apply_form_data_to_contract(
        self,
        contract_id: str,
        form_submission_id: str,
        field_mappings: Optional[Dict[str, str]] = None,
        applied_by: Optional[str] = None,
    ) -> dict:
        """Apply data from a vendor form submission to populate contract sections"""
        try:
            # Authorization: verify contract belongs to this user
            contract = await self.get_contract(contract_id, created_by=applied_by)

            if contract["status"] not in [
                ContractStatus.DRAFT.value,
                ContractStatus.PENDING_REVIEW.value,
            ]:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot apply form data to a contract that has been sent",
                )

            submission_object_id = validate_object_id(
                form_submission_id, "form submission ID"
            )

            # Try to find the submission in vendor_submissions first
            submission = await mongo.db["vendor_submissions"].find_one(
                {"_id": submission_object_id}
            )

            if not submission:
                # Try vendor_forms
                submission = await mongo.db["vendor_forms"].find_one(
                    {"_id": submission_object_id}
                )

            if not submission:
                raise HTTPException(status_code=404, detail="Form submission not found")

            submission_data = submission.get("submission_data", {})
            if not isinstance(submission_data, dict):
                raise HTTPException(
                    status_code=400, detail="Invalid submission data format"
                )

            # Build placeholder replacements
            replacements: Dict[str, str] = {}
            normalized_mappings: Dict[str, str] = {}

            # Default mappings from submission data
            for key, value in submission_data.items():
                if value and isinstance(value, (str, int, float)):
                    placeholder = f"{{{{{key}}}}}"
                    replacements[placeholder] = str(value)
                    normalized_mappings[key] = placeholder

            # Apply custom field mappings if provided
            if field_mappings:
                for field_name, placeholder in field_mappings.items():
                    if field_name in submission_data:
                        replacements[placeholder] = str(submission_data[field_name])
                        normalized_mappings[field_name] = placeholder

            # Apply replacements to contract sections
            updated_sections = []
            for section in contract.get("sections", []):
                updated_sections.append(
                    {
                        **section,
                        "content": self._apply_placeholder_replacements(
                            section.get("content", ""),
                            replacements,
                        ),
                    }
                )

            existing_submission_ids = contract.get("form_submission_ids") or []
            updated_submission_ids = list(
                dict.fromkeys([*existing_submission_ids, form_submission_id])
            )

            # Update contract
            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "sections": updated_sections,
                        "terms_and_conditions": self._apply_placeholder_replacements(
                            contract.get("terms_and_conditions"),
                            replacements,
                        ),
                        "cancellation_policy": self._apply_placeholder_replacements(
                            contract.get("cancellation_policy"),
                            replacements,
                        ),
                        "custom_clauses": self._apply_placeholder_replacements(
                            contract.get("custom_clauses"),
                            replacements,
                        ),
                        "form_data_applied": True,
                        "form_submission_id": form_submission_id,
                        "form_submission_ids": updated_submission_ids,
                        "form_data_mappings": normalized_mappings,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            applied_at = datetime.now(timezone.utc)
            await self._log_contract_activity(
                contract_id=contract_id,
                root_contract_id=self._get_root_contract_id(contract),
                activity_type=VendorContractActivityType.FORM_DATA_APPLIED,
                title="Vendor form data applied",
                description="Applied submitted vendor data to the contract document.",
                actor_type="planner",
                actor_identifier=applied_by,
                actor_display_name=applied_by,
                metadata={
                    "form_submission_id": form_submission_id,
                    "field_mappings": normalized_mappings,
                },
                created_at=applied_at,
            )

            return await self.get_contract(contract_id, created_by=applied_by)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error applying form data to contract: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to apply form data")

    # =========================================================================
    # PAYMENT MILESTONES
    # =========================================================================

    async def create_payment_milestones(
        self, contract_id: str, milestones: List[Dict], created_by: str
    ) -> List[dict]:
        """Create payment milestones for a contract"""
        try:
            # Authorization: verify contract belongs to this user
            contract = await self.get_contract(contract_id, created_by=created_by)
            self._ensure_contract_current_for_payments(
                contract, action="create payment milestones"
            )

            created_milestones = []
            for m in milestones:
                milestone = {
                    "contract_id": contract_id,
                    "wedding_id": contract["wedding_id"],
                    "vendor_profile_id": contract.get("vendor_profile_id"),
                    "budget_category_id": contract.get("budget_category_id"),
                    "description": m["description"],
                    "amount": m["amount"],
                    "currency": contract.get("currency", "USD"),
                    "percentage_of_total": m.get("percentage_of_total"),
                    "due_date": (
                        m["due_date"]
                        if isinstance(m["due_date"], datetime)
                        else datetime.fromisoformat(m["due_date"])
                    ),
                    "days_before_event": m.get("days_before_event"),
                    "status": PaymentMilestoneStatus.PENDING.value,
                    "paid_amount": 0.0,
                    "vendor_name": contract["vendor_name"],
                    "vendor_email": contract["vendor_email"],
                    "created_by": created_by,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }

                result = await self.payment_milestones.insert_one(milestone)
                milestone["_id"] = str(result.inserted_id)
                created_milestones.append(milestone)

            if created_milestones:
                await self._log_contract_activity(
                    contract_id=contract_id,
                    root_contract_id=self._get_root_contract_id(contract),
                    activity_type=VendorContractActivityType.MILESTONES_CREATED,
                    title="Payment milestones created",
                    description=f"Created {len(created_milestones)} payment milestone(s).",
                    actor_type="planner",
                    actor_identifier=created_by,
                    actor_display_name=created_by,
                    metadata={"milestone_count": len(created_milestones)},
                    created_at=created_milestones[-1]["created_at"],
                )

            return created_milestones

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating milestones: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to create payment milestones"
            )

    async def get_payment_milestones(
        self,
        contract_id: Optional[str] = None,
        wedding_id: Optional[str] = None,
        status: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> List[dict]:
        """Get payment milestones"""
        try:
            query: Dict[str, Any] = {}

            if contract_id and created_by:
                await self.get_contract(contract_id, created_by=created_by)

            if contract_id:
                query["contract_id"] = contract_id
            if wedding_id:
                query["wedding_id"] = wedding_id
            if status:
                query["status"] = status
            if created_by and not contract_id:
                query["created_by"] = created_by

            cursor = self.payment_milestones.find(query).sort("due_date", 1)
            milestones = await cursor.to_list(length=100)

            # Track IDs of milestones that need status update
            overdue_milestone_ids = []
            now = datetime.now(timezone.utc)

            for m in milestones:
                m["_id"] = str(m["_id"])
                # Check if overdue and persist the status change
                if m["status"] == PaymentMilestoneStatus.PENDING.value:
                    if m.get("due_date") and m["due_date"] < now:
                        m["status"] = PaymentMilestoneStatus.OVERDUE.value
                        overdue_milestone_ids.append(ObjectId(m["_id"]))

            # Persist overdue status changes to database
            if overdue_milestone_ids:
                await self.payment_milestones.update_many(
                    {"_id": {"$in": overdue_milestone_ids}},
                    {
                        "$set": {
                            "status": PaymentMilestoneStatus.OVERDUE.value,
                            "updated_at": now,
                        }
                    },
                )
                logger.info(
                    f"Marked {len(overdue_milestone_ids)} milestones as overdue"
                )

            return milestones

        except Exception as e:
            logger.error(f"Error fetching milestones: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch milestones")

    async def _get_owned_payment_milestone(
        self, milestone_id: str, created_by: str
    ) -> Dict[str, Any]:
        """Fetch one milestone and fail closed if it is not owned by this planner scope."""
        milestone_object_id = validate_object_id(milestone_id, "milestone ID")
        milestone = await self.payment_milestones.find_one({"_id": milestone_object_id})
        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found")

        contract_id = milestone.get("contract_id")
        if contract_id:
            contract = await self.get_contract(contract_id, created_by=created_by)
            self._ensure_contract_current_for_payments(
                contract, action="record payment"
            )
            return milestone

        if milestone.get("created_by") == created_by:
            return milestone

        raise HTTPException(status_code=404, detail="Milestone not found")

    async def record_payment(
        self,
        milestone_id: str,
        amount: float,
        payment_method: str,
        created_by: str,
        payment_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        receipt_url: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
    ) -> dict:
        """Record a payment against a milestone."""
        try:
            milestone = await self._get_owned_payment_milestone(
                milestone_id=milestone_id,
                created_by=created_by,
            )

            # Guard 1: Stripe intent idempotency.
            # Stripe retries webhooks and the planner UI can double-submit a
            # record. Without this check, the same PaymentIntent could be
            # recorded twice and the rollups inflated. This guard runs first
            # so a same-milestone retry returns an idempotent ack rather than
            # falling through to the status / clamp guards (which would 409
            # / 400 a legitimate retry).
            #   - Same milestone + same intent => idempotent ack (200).
            #   - Different milestone + same intent => 409 (Stripe intents are
            #     globally unique per charge; a re-use is a routing bug).
            # Note: this guard only catches manual+manual races. The webhook
            # path at handle_payment_link_webhook does not currently set
            # stripe_payment_intent_id on the milestone, so manual+webhook
            # races are still open. Tracked as a follow-up fix.
            if stripe_payment_intent_id:
                if (
                    milestone.get("stripe_payment_intent_id")
                    == stripe_payment_intent_id
                ):
                    logger.info(
                        "Idempotent record_payment: intent %s already on milestone %s",
                        stripe_payment_intent_id,
                        milestone_id,
                    )
                    return {**milestone, "_id": str(milestone["_id"])}
                duplicate = await self.payment_milestones.find_one(
                    {"stripe_payment_intent_id": stripe_payment_intent_id}
                )
                if duplicate is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "This Stripe payment is already recorded against "
                            "another milestone"
                        ),
                    )

            # Guard 2: status lock.
            # Once a milestone reaches PAID (and we have NOT already returned
            # the idempotent ack above), additional record_payment calls would
            # silently inflate paid_amount past the milestone amount and
            # double-credit the assignment / vendor / budget rollups. Reject
            # explicitly with 409 so the caller can surface the conflict.
            if milestone.get("status") == PaymentMilestoneStatus.PAID.value:
                raise HTTPException(
                    status_code=409,
                    detail="Milestone is already fully paid",
                )

            # Guard 3: amount clamp.
            # Without this, amount > remaining over-credits paid_amount and
            # the rollup $inc on vendor_assignments / vendor_profiles. The
            # 0.005 tolerance absorbs float-rounding on cent boundaries
            # (e.g. 33.33 + 33.33 + 33.34 vs. 100.00).
            current_paid = float(milestone.get("paid_amount", 0) or 0)
            milestone_amount = float(milestone["amount"])
            remaining = milestone_amount - current_paid
            if amount > remaining + 0.005:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Payment amount ${amount:.2f} exceeds remaining "
                        f"balance ${remaining:.2f} on this milestone"
                    ),
                )

            contract = None
            if milestone.get("contract_id"):
                contract = await self.get_contract(
                    milestone["contract_id"], created_by=created_by
                )

            new_paid_amount = current_paid + amount

            # Determine new status
            if new_paid_amount >= milestone["amount"]:
                new_status = PaymentMilestoneStatus.PAID.value
            elif new_paid_amount > 0:
                new_status = PaymentMilestoneStatus.PARTIAL.value
            else:
                new_status = milestone["status"]

            update_data = {
                "paid_amount": new_paid_amount,
                "status": new_status,
                "payment_method": payment_method,
                "paid_at": payment_date or datetime.now(timezone.utc),
                "notes": notes,
                "receipt_url": receipt_url,
                "updated_at": datetime.now(timezone.utc),
            }

            if stripe_payment_intent_id:
                update_data["stripe_payment_intent_id"] = stripe_payment_intent_id

            async def _record_in_transaction(session: Any) -> None:
                await self.payment_milestones.update_one(
                    {"_id": ObjectId(milestone_id)},
                    {"$set": update_data},
                    session=session,
                )

                if milestone.get("vendor_profile_id") and milestone.get("wedding_id"):
                    await self.vendor_assignments.update_one(
                        {
                            "vendor_profile_id": milestone["vendor_profile_id"],
                            "wedding_id": milestone["wedding_id"],
                        },
                        {"$inc": {"paid_amount": amount}},
                        session=session,
                    )

                if milestone.get("vendor_profile_id"):
                    await self.vendor_profiles.update_one(
                        {"_id": ObjectId(milestone["vendor_profile_id"])},
                        {"$inc": {"total_revenue": amount}},
                        session=session,
                    )

                if milestone.get("budget_category_id"):
                    await self.budget_categories.update_one(
                        {"_id": ObjectId(milestone["budget_category_id"])},
                        {"$inc": {"actual_spent": amount}},
                        session=session,
                    )

            await self._run_required_transaction(
                "Vendor milestone payment recording",
                _record_in_transaction,
            )

            updated = await self.payment_milestones.find_one(
                {"_id": ObjectId(milestone_id)}
            )
            if not updated:
                raise HTTPException(
                    status_code=404, detail="Milestone not found after update"
                )
            updated["_id"] = str(updated["_id"])

            if milestone.get("contract_id") and contract:
                await self._log_contract_activity(
                    contract_id=milestone["contract_id"],
                    root_contract_id=self._get_root_contract_id(contract),
                    activity_type=VendorContractActivityType.PAYMENT_RECORDED,
                    title="Payment recorded",
                    description=(
                        f"Recorded {amount:,.2f} via {payment_method.replace('_', ' ')}."
                    ),
                    actor_type="planner",
                    actor_identifier=created_by,
                    actor_display_name=created_by,
                    metadata={
                        "milestone_id": milestone_id,
                        "amount": amount,
                        "payment_method": payment_method,
                    },
                    created_at=update_data["paid_at"],
                )

            return updated

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error recording payment: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to record payment")

    async def get_contract_activity(self, contract_id: str, created_by: str) -> dict:
        """Return contract-scoped activity with synthesized fallback for legacy records."""
        try:
            contract = await self.get_contract(contract_id, created_by=created_by)
            root_contract_id = self._get_root_contract_id(contract)

            cursor = self.vendor_contract_activities.find(
                {"contract_id": contract_id}
            ).sort("created_at", -1)
            explicit_items = await cursor.to_list(length=200)
            serialized_items = [
                self._serialize_contract_activity_item(activity)
                for activity in explicit_items
            ]

            if explicit_items:
                explicit_types = {
                    item.get("activity_type")
                    for item in explicit_items
                    if item.get("activity_type")
                }
                synthesized_items = [
                    item
                    for item in self._build_synthesized_contract_activity(contract)
                    if item.get("activity_type") not in explicit_types
                ]
            else:
                synthesized_items = self._build_synthesized_contract_activity(contract)

            items = [*serialized_items, *synthesized_items]
            items.sort(
                key=lambda item: (
                    item.get("created_at") or datetime.min.replace(tzinfo=timezone.utc)
                ),
                reverse=True,
            )

            return {
                "contract_id": contract["id"],
                "root_contract_id": root_contract_id,
                "items": items,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching contract activity: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to fetch contract activity"
            )

    # =========================================================================
    # FILE STORAGE
    # =========================================================================

    async def upload_contract_document(
        self,
        contract_id: str,
        file: UploadFile,
        document_type: str = "signed",
        created_by: Optional[str] = None,
    ) -> dict:
        """Upload a contract document to S3.

        ``created_by`` is the actor's planner email. When provided, the
        contract lookup is scoped to that owner so a planner cannot
        overwrite another tenant's ``document_url``. Pass ``None`` for
        the root-admin bypass case.
        """
        try:
            # Validate MIME type
            if file.content_type not in ALLOWED_CONTRACT_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{file.content_type}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_CONTRACT_TYPES))}",
                )

            # Verify the contract exists and belongs to this planner BEFORE
            # we burn an S3 object on a foreign-tenant write attempt.
            owned_contract = await self._get_owned_contract(contract_id, created_by)
            if not owned_contract:
                raise HTTPException(status_code=404, detail="Contract not found")

            # Generate unique key
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = (
                f"contracts/{contract_id}/{document_type}_{timestamp}_{file.filename}"
            )

            # Upload to S3
            file_content = await file.read()
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=file_content,
                ContentType=file.content_type,
            )

            file_url = f"{self.media_domain}/{filename}"

            # Update contract with document URL — re-scope the update query
            # to the owner so a TOCTOU swap between the ownership check
            # and the write cannot smuggle in a foreign contract.
            field = f"{document_type}_document_url"
            update_query: Dict[str, Any] = {"_id": ObjectId(contract_id)}
            normalized_actor = normalize_planner_email(created_by)
            if normalized_actor is not None:
                update_query["created_by"] = normalized_actor
            await self.vendor_contracts.update_one(
                update_query,
                {"$set": {field: file_url, "updated_at": datetime.now(timezone.utc)}},
            )

            return {"url": file_url, "key": filename}

        except HTTPException:
            raise
        except ClientError as e:
            logger.error(f"S3 upload error: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to upload document")
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to upload document")

    # =========================================================================
    # COMMUNICATION HISTORY
    # =========================================================================

    async def get_vendor_communications(
        self, vendor_profile_id: str, wedding_id: Optional[str] = None, limit: int = 50
    ) -> List[dict]:
        """Get communication history with a vendor"""
        try:
            query = {"vendor_profile_id": vendor_profile_id}
            if wedding_id:
                query["wedding_id"] = wedding_id

            cursor = (
                self.vendor_communications.find(query)
                .sort("created_at", -1)
                .limit(limit)
            )
            communications = await cursor.to_list(length=limit)

            for c in communications:
                c["_id"] = str(c["_id"])

            return communications

        except Exception as e:
            logger.error(f"Error fetching communications: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to fetch communications"
            )

    # =========================================================================
    # PDF UPLOAD CONTRACT
    # =========================================================================

    async def upload_contract_pdf(
        self,
        file: UploadFile,
        wedding_id: str,
        vendor_profile_id: str,
        contract_title: str,
        total_amount: float,
        created_by: Optional[str] = None,
        deposit_amount: Optional[float] = None,
        service_date: Optional[datetime] = None,
        service_location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Create a contract by uploading an existing PDF.
        The planner uploads their own contract PDF instead of using templates.

        ``created_by`` is the actor's planner email. Pass ``None`` for the
        root-admin bypass case (skips the planner-ownership filter).
        """
        try:
            # Get vendor profile (scoped by planner ownership — prevents a
            # cross-tenant write via a client-supplied vendor_profile_id).
            # Use the helper so root-admin (created_by=None) skips the
            # ownership filter cleanly; the prior call to get_vendor_profile
            # would have run {"_id": ..., "created_by": None} and 404'd.
            vendor = await self._get_owned_vendor_profile(vendor_profile_id, created_by)
            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")

            # Get wedding (scoped by planner ownership — prevents a planner
            # from uploading a PDF against another tenant's wedding).
            wedding = await self._get_owned_wedding(wedding_id, created_by)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Validate file is PDF
            if file.content_type != "application/pdf":
                raise HTTPException(
                    status_code=400, detail="File must be a PDF (application/pdf)"
                )

            # Read file content
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:  # 10MB limit
                raise HTTPException(
                    status_code=400, detail="File too large. Maximum 10MB"
                )

            # Generate unique filename
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            safe_filename = f"contracts/{wedding_id}/{timestamp}_{file.filename}"

            # Upload to S3
            try:
                self.s3.put_object(
                    Bucket=self.bucket_name,
                    Key=safe_filename,
                    Body=content,
                    ContentType="application/pdf",
                )
                pdf_url = f"{self.media_domain}/{safe_filename}"
            except ClientError as e:
                logger.error(f"S3 upload error: {str(e)}")
                raise HTTPException(
                    status_code=500, detail="Failed to upload contract PDF"
                )

            # Create contract record
            contract_id = ObjectId()
            now = datetime.now(timezone.utc)
            contract_doc = {
                "_id": contract_id,
                "wedding_id": wedding_id,
                "vendor_profile_id": vendor_profile_id,
                "vendor_name": vendor["business_name"],
                "vendor_email": vendor["email"],
                "vendor_phone": vendor.get("phone"),
                "vendor_address": vendor.get("address"),
                "service_category": vendor["service_category"],
                "custom_service_category": vendor.get("custom_service_category"),
                "contract_title": contract_title,
                "contract_number": self._generate_contract_number(),
                "contract_type": ContractType.UPLOADED_PDF.value,
                "uploaded_pdf_url": pdf_url,
                "uploaded_pdf_name": file.filename,
                "sections": [],  # No sections for uploaded PDF
                "total_amount": total_amount,
                "currency": "USD",
                "deposit_amount": deposit_amount,
                "status": ContractStatus.DRAFT.value,
                "service_date": service_date,
                "service_location": service_location,
                "internal_notes": notes,
                "created_by": created_by,
                "version_number": 1,
                "root_contract_id": str(contract_id),
                "parent_contract_id": None,
                "supersedes_contract_id": None,
                "superseded_by_contract_id": None,
                "is_current_version": True,
                "contract_kind": ContractKind.ORIGINAL.value,
                "amendment_reason": None,
                "superseded_at": None,
                "created_at": now,
                "updated_at": now,
                "form_submission_ids": [],
                "form_data_mappings": {},
                **self._build_inactive_contract_token_fields(),
            }

            result = await self.vendor_contracts.insert_one(contract_doc)
            contract_doc["_id"] = result.inserted_id
            self._serialize_doc(contract_doc)
            self._attach_contract_version_metadata(contract_doc)

            logger.info(
                f"Created PDF contract {contract_doc['_id']} for vendor {vendor_profile_id}"
            )
            return contract_doc

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading contract PDF: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to upload contract: {str(e)}"
            )

    # =========================================================================
    # PAYMENT LINKS
    # =========================================================================

    async def create_payment_link(
        self,
        payer_type: str,
        payer_email: str,
        payer_name: str,
        recipient_type: str,
        recipient_email: str,
        recipient_name: str,
        amount: float,
        description: str,
        created_by: str,
        currency: str = "USD",
        due_date: Optional[datetime] = None,
        wedding_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        milestone_id: Optional[str] = None,
        vendor_profile_id: Optional[str] = None,
        email_subject: Optional[str] = None,
        email_message: Optional[str] = None,
        payer_phone: Optional[str] = None,
    ) -> dict:
        """
        Create a payment link that can be sent to vendors or couples.
        Integrates with Stripe for payment processing.
        """
        try:
            if not settings.stripe_enabled:
                raise HTTPException(
                    status_code=503, detail="Payment processing not available"
                )

            stripe.api_key = settings.stripe_secret_key

            # Create Stripe Payment Link
            try:
                # Create a price for this payment
                price = stripe.Price.create(
                    unit_amount=int(amount * 100),  # Convert to cents
                    currency=currency.lower(),
                    product_data={
                        "name": description[:100],  # Stripe limits to 100 chars
                    },
                )

                # Create payment link
                payment_link = stripe.PaymentLink.create(
                    line_items=[{"price": price.id, "quantity": 1}],
                    metadata={
                        "payer_type": payer_type,
                        "payer_email": payer_email,
                        "recipient_type": recipient_type,
                        "recipient_email": recipient_email,
                        "wedding_id": wedding_id or "",
                        "contract_id": contract_id or "",
                        "milestone_id": milestone_id or "",
                        "created_by": created_by,
                    },
                    after_completion={
                        "type": "redirect",
                        "redirect": {
                            "url": f"{os.getenv('FRONTEND_URL', '')}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
                        },
                    },
                )

                stripe_payment_link_id = payment_link.id
                stripe_payment_link_url = payment_link.url

            except stripe.StripeError as e:
                logger.error(f"Stripe error creating payment link: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Payment link creation failed: {str(e)}"
                )

            # Calculate expiration date (due_date + 7 days buffer, or 30 days from now)
            if due_date:
                expires_at = due_date + timedelta(days=7)
            else:
                expires_at = datetime.now(timezone.utc) + timedelta(
                    days=TOKEN_EXPIRY_DAYS
                )

            # Create payment link record
            payment_link_doc = {
                "wedding_id": wedding_id,
                "contract_id": contract_id,
                "milestone_id": milestone_id,
                "vendor_profile_id": vendor_profile_id,
                "payer_type": payer_type,
                "payer_email": payer_email,
                "payer_name": payer_name,
                "payer_phone": payer_phone,
                "recipient_type": recipient_type,
                "recipient_email": recipient_email,
                "recipient_name": recipient_name,
                "amount": amount,
                "currency": currency,
                "description": description,
                "due_date": due_date,
                "expires_at": expires_at,
                "stripe_payment_link_id": stripe_payment_link_id,
                "stripe_payment_link_url": stripe_payment_link_url,
                "status": PaymentLinkStatus.DRAFT.value,
                "email_subject": email_subject,
                "email_message": email_message,
                "access_token": self._generate_token(),
                "created_by": created_by,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "reminder_sent_count": 0,
            }

            result = await self.payment_links.insert_one(payment_link_doc)
            payment_link_doc["_id"] = str(result.inserted_id)

            logger.info(
                f"Created payment link {payment_link_doc['_id']} for {amount} {currency}"
            )
            return payment_link_doc

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating payment link: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create payment link: {str(e)}"
            )

    async def send_payment_link(
        self,
        payment_link_id: str,
        planner_email: str,
        custom_message: Optional[str] = None,
    ) -> dict:
        """
        Send a payment link to the payer via email.
        """
        try:
            # Get payment link
            payment_link = await self.payment_links.find_one(
                {"_id": ObjectId(payment_link_id)}
            )
            if not payment_link:
                raise HTTPException(status_code=404, detail="Payment link not found")

            # Get planner info for from name
            planner = await self.users.find_one({"email": planner_email})
            planner_name = (
                planner.get("name", "Your Wedding Planner")
                if planner
                else "Your Wedding Planner"
            )

            # Build email
            subject = (
                payment_link.get("email_subject")
                or f"Payment Request: {payment_link['description']}"
            )
            payment_url = payment_link["stripe_payment_link_url"]

            message = custom_message or payment_link.get("email_message") or ""
            if message:
                message = f"<p>{message}</p>"

            email_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #1e3a8a 0%, #d97706 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                    .content {{ background: white; padding: 30px; border: 1px solid #e5e7eb; }}
                    .amount {{ font-size: 32px; font-weight: bold; color: #1e3a8a; text-align: center; margin: 20px 0; }}
                    .button {{ display: inline-block; background: #059669; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
                    .footer {{ background: #f9fafb; padding: 20px; text-align: center; border-radius: 0 0 8px 8px; font-size: 12px; color: #6b7280; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Payment Request</h1>
                    </div>
                    <div class="content">
                        <p>Dear {payment_link["payer_name"]},</p>
                        {message}
                        <p>You have a payment request for:</p>
                        <p><strong>{payment_link["description"]}</strong></p>
                        <div class="amount">${payment_link["amount"]:,.2f} {payment_link["currency"]}</div>
                        <p>Payment to: <strong>{payment_link["recipient_name"]}</strong></p>
                        {"<p><strong>Due Date:</strong> " + payment_link["due_date"].strftime("%B %d, %Y") + "</p>" if payment_link.get("due_date") else ""}
                        <div style="text-align: center;">
                            <a href="{payment_url}" class="button">Pay Now</a>
                        </div>
                        <p style="font-size: 12px; color: #6b7280;">
                            This is a secure payment link powered by Stripe. Your payment information is encrypted and secure.
                        </p>
                    </div>
                    <div class="footer">
                        <p>Sent by {planner_name} via The Special Wedding</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Send email
            await self.email_service.send_email(
                to_email=payment_link["payer_email"],
                subject=subject,
                html_content=email_html,
            )

            # Update payment link status
            await self.payment_links.update_one(
                {"_id": ObjectId(payment_link_id)},
                {
                    "$set": {
                        "status": PaymentLinkStatus.SENT.value,
                        "sent_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            logger.info(
                f"Sent payment link {payment_link_id} to {payment_link['payer_email']}"
            )
            return {
                "message": "Payment link sent",
                "sent_to": payment_link["payer_email"],
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending payment link: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to send payment link: {str(e)}"
            )

    async def get_payment_links(
        self,
        planner_email: str,
        wedding_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[dict]:
        """Get payment links created by a planner"""
        try:
            query = {"created_by": planner_email}
            if wedding_id:
                query["wedding_id"] = wedding_id
            if status:
                query["status"] = status

            cursor = (
                self.payment_links.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            links = await cursor.to_list(length=limit)

            for link in links:
                link["_id"] = str(link["_id"])

            return links

        except Exception as e:
            logger.error(f"Error fetching payment links: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch payment links")

    async def handle_payment_link_webhook(self, stripe_event: dict) -> dict:
        """
        Handle Stripe webhook for payment link completion.

        On `checkout.session.completed`:
          1. Route the milestone credit through `record_payment` — the canonical
             primitive — so the three guards (intent idempotency, status lock,
             amount clamp) and the transactional rollup to vendor_assignments,
             vendor_profiles, and budget_categories all run.
          2. ONLY on record_payment success (or its translated idempotent acks)
             do we mark the payment_link row PAID. If record_payment raises
             non-idempotently, the link stays in its prior status and Stripe
             will retry — on retry record_payment can complete cleanly.

        The legacy inline milestone update bypassed `record_payment`, so:
          - Stripe webhook retries → milestone double-credited (paid_amount inflated).
          - A milestone already PAID via another path silently re-credited.
          - vendor_assignments.paid_amount, vendor_profiles.total_revenue, and
            budget_categories.actual_spent never moved on payment-link-paid milestones.

        Guard rejections are translated into idempotent 200-style returns so
        Stripe stops retrying — re-driving the same intent through this path
        is benign now.

        Stale-state protection on the payment_link doc update:
          - CANCELLED links: do NOT credit, do NOT overwrite status; log WARNING
            and return processed=True so Stripe stops retrying.
          - Already-PAID links (replay): do NOT clobber paid_at; only fill in
            stripe_checkout_session_id / stripe_payment_intent_id if missing.
          - Missing milestone (deleted between link creation and webhook fire):
            translate the inner 404 into an ERROR log + processed=True so
            Stripe stops retrying. Ops finds the orphan via the log.
        """
        # Pull these out early so the outer except can reference them.
        payment_link_id: Optional[str] = None
        event_id = stripe_event.get("id") if isinstance(stripe_event, dict) else None
        try:
            event_type = stripe_event.get("type")
            data = stripe_event.get("data", {}).get("object", {})

            # Authoritative settlement time from Stripe — falls back to None
            # (record_payment defaults to now) if absent.
            event_created = stripe_event.get("created")
            event_payment_date: Optional[datetime] = None
            if event_created is not None:
                try:
                    event_payment_date = datetime.fromtimestamp(
                        int(event_created), tz=timezone.utc
                    )
                except (TypeError, ValueError, OSError):
                    event_payment_date = None

            if event_type == "checkout.session.completed":
                # Find payment link by checkout session
                payment_link_id = data.get("metadata", {}).get("payment_link_id")
                if not payment_link_id:
                    # Try to find by Stripe payment link ID
                    stripe_pl_id = data.get("payment_link")
                    if stripe_pl_id:
                        payment_link = await self.payment_links.find_one(
                            {"stripe_payment_link_id": stripe_pl_id}
                        )
                        if payment_link:
                            payment_link_id = str(payment_link["_id"])

                if payment_link_id:
                    # Re-read the payment_link doc up front so we can route the
                    # milestone credit through the canonical primitive BEFORE
                    # we touch the link doc itself.
                    payment_link = await self.payment_links.find_one(
                        {"_id": ObjectId(payment_link_id)}
                    )

                    # CANCELLED short-circuit: link was explicitly killed by
                    # the planner. A late Stripe webhook should not credit and
                    # should not overwrite the audit trail. Acknowledge so
                    # Stripe stops retrying.
                    if (
                        payment_link
                        and payment_link.get("status")
                        == PaymentLinkStatus.CANCELLED.value
                    ):
                        logger.warning(
                            "payment_link_webhook: late webhook for CANCELLED "
                            "link; skipping credit and preserving audit",
                            extra={
                                "payment_link_id": payment_link_id,
                                "event_id": event_id,
                                "stripe_payment_intent_id": data.get("payment_intent"),
                            },
                        )
                        return {"processed": True}

                    record_payment_succeeded = False

                    if payment_link and payment_link.get("milestone_id"):
                        milestone_id = str(payment_link["milestone_id"])
                        created_by = payment_link.get("created_by")
                        amount = float(payment_link.get("amount") or 0)
                        payment_intent_id = data.get("payment_intent")

                        # Best-effort receipt URL: Stripe gives us the PI id on
                        # the checkout.session payload, but not the charge's
                        # receipt URL. Fetch the PI and pull `latest_charge`.
                        # This is best-effort — failures here must NOT prevent
                        # the milestone credit from being recorded.
                        receipt_url: Optional[str] = None
                        if payment_intent_id:
                            try:
                                pi = stripe.PaymentIntent.retrieve(
                                    payment_intent_id,
                                    expand=["latest_charge"],
                                )
                                latest_charge = getattr(pi, "latest_charge", None)
                                if latest_charge and not isinstance(latest_charge, str):
                                    receipt_url = getattr(
                                        latest_charge, "receipt_url", None
                                    )
                            except stripe.StripeError as exc:
                                logger.warning(
                                    "payment_link_webhook: could not fetch "
                                    "receipt_url for intent %s: %s",
                                    payment_intent_id,
                                    exc,
                                )

                        if not created_by:
                            # Without a created_by we can't look up the
                            # milestone (record_payment scopes by ownership).
                            # Log and bail on the milestone credit. The
                            # payment_link doc still gets the PAID update
                            # below — the planner needs the doc to reflect
                            # what Stripe collected, even though the rollup
                            # never ran. Ops finds these via the ERROR log.
                            logger.error(
                                "payment_link_webhook: missing created_by; "
                                "cannot route to record_payment, milestone "
                                "NOT credited",
                                extra={
                                    "payment_link_id": payment_link_id,
                                    "milestone_id": milestone_id,
                                    "stripe_payment_intent_id": payment_intent_id,
                                    "event_id": event_id,
                                    "amount": amount,
                                },
                            )
                            # Allow the link doc update below to run; without
                            # it the Stripe-provided session/PI ids never
                            # land on the doc.
                            record_payment_succeeded = True
                        else:
                            try:
                                await self.record_payment(
                                    milestone_id=milestone_id,
                                    amount=amount,
                                    payment_method="stripe",
                                    created_by=created_by,
                                    payment_date=event_payment_date,
                                    stripe_payment_intent_id=payment_intent_id,
                                    receipt_url=receipt_url,
                                )
                                record_payment_succeeded = True
                            except HTTPException as exc:
                                # Translate guard rejections into idempotent
                                # 200-style returns so Stripe stops retrying.
                                #   404 milestone-not-found → milestone was
                                #     deleted between link creation and
                                #     webhook fire. Don't mark the link PAID
                                #     (record_payment did NOT run); log ERROR
                                #     so ops finds the orphan, return
                                #     processed=True to stop Stripe retries.
                                #   409 with "already recorded" / status PAID →
                                #     benign retry; the milestone is in the
                                #     intended end state already.
                                #   400 amount clamp → log + swallow; should be
                                #     impossible if the link's amount matches
                                #     the milestone, but a stale link against
                                #     a partially-paid milestone could trip it.
                                detail = str(exc.detail or "").lower()
                                if exc.status_code == 404:
                                    logger.error(
                                        "payment_link_webhook: milestone not "
                                        "found (likely deleted between link "
                                        "creation and webhook fire); skipping "
                                        "credit and link update",
                                        extra={
                                            "payment_link_id": payment_link_id,
                                            "milestone_id": milestone_id,
                                            "stripe_payment_intent_id": (
                                                payment_intent_id
                                            ),
                                            "event_id": event_id,
                                            "amount": amount,
                                            "detail": exc.detail,
                                        },
                                    )
                                    return {"processed": True}
                                if exc.status_code == 409 and ("already" in detail):
                                    logger.info(
                                        "payment_link_webhook: idempotent "
                                        "replay (record_payment 409)",
                                        extra={
                                            "payment_link_id": payment_link_id,
                                            "milestone_id": milestone_id,
                                            "stripe_payment_intent_id": (
                                                payment_intent_id
                                            ),
                                            "event_id": event_id,
                                            "detail": exc.detail,
                                        },
                                    )
                                    record_payment_succeeded = True
                                elif exc.status_code == 400 and (
                                    "exceeds remaining" in detail
                                ):
                                    logger.warning(
                                        "payment_link_webhook: amount clamp "
                                        "rejected by record_payment; "
                                        "swallowing so Stripe does not "
                                        "infinite-retry",
                                        extra={
                                            "payment_link_id": payment_link_id,
                                            "milestone_id": milestone_id,
                                            "stripe_payment_intent_id": (
                                                payment_intent_id
                                            ),
                                            "event_id": event_id,
                                            "amount": amount,
                                            "detail": exc.detail,
                                        },
                                    )
                                    record_payment_succeeded = True
                                else:
                                    raise
                    else:
                        # No milestone bound — link doc update is the only
                        # action this webhook performs. Treat as success so
                        # the doc update below runs.
                        record_payment_succeeded = True

                    # Only mark the link doc PAID if record_payment succeeded
                    # (or returned an idempotent ack). On non-idempotent
                    # failure we want Stripe's retry to find the link still
                    # in its prior status so the credit can be re-attempted.
                    if record_payment_succeeded:
                        # Stale-state guard: only DRAFT/SENT/CLICKED links
                        # may transition to PAID via this fast path. The
                        # filter is the source of truth — it prevents
                        # CANCELLED audit overwrite (defence-in-depth on top
                        # of the early-return above) and prevents replay
                        # from clobbering the original paid_at on already-
                        # PAID docs.
                        update_result = await self.payment_links.update_one(
                            {
                                "_id": ObjectId(payment_link_id),
                                "status": {
                                    "$in": [
                                        PaymentLinkStatus.DRAFT.value,
                                        PaymentLinkStatus.SENT.value,
                                        PaymentLinkStatus.CLICKED.value,
                                    ]
                                },
                            },
                            {
                                "$set": {
                                    "status": PaymentLinkStatus.PAID.value,
                                    "paid_at": datetime.now(timezone.utc),
                                    "stripe_checkout_session_id": data.get("id"),
                                    "stripe_payment_intent_id": data.get(
                                        "payment_intent"
                                    ),
                                    "updated_at": datetime.now(timezone.utc),
                                }
                            },
                        )

                        if update_result.matched_count == 0:
                            # Either the link is already PAID (replay) or in
                            # some other terminal state. For replay, fill in
                            # missing session/intent ids defensively but do
                            # NOT touch paid_at.
                            await self.payment_links.update_one(
                                {
                                    "_id": ObjectId(payment_link_id),
                                    "status": PaymentLinkStatus.PAID.value,
                                    "$or": [
                                        {
                                            "stripe_checkout_session_id": {
                                                "$in": [None, ""]
                                            }
                                        },
                                        {
                                            "stripe_checkout_session_id": {
                                                "$exists": False
                                            }
                                        },
                                        {
                                            "stripe_payment_intent_id": {
                                                "$in": [None, ""]
                                            }
                                        },
                                        {
                                            "stripe_payment_intent_id": {
                                                "$exists": False
                                            }
                                        },
                                    ],
                                },
                                {
                                    "$set": {
                                        "stripe_checkout_session_id": data.get("id"),
                                        "stripe_payment_intent_id": data.get(
                                            "payment_intent"
                                        ),
                                        "updated_at": datetime.now(timezone.utc),
                                    }
                                },
                            )

                        # Structured success log so dashboards / alerts can
                        # filter on stable keys.
                        milestone_log_id: Optional[str] = None
                        amount_log: Optional[float] = None
                        if payment_link and payment_link.get("milestone_id"):
                            milestone_log_id = str(payment_link["milestone_id"])
                            amount_log = float(payment_link.get("amount") or 0)
                        logger.info(
                            "payment_link_webhook: payment_link marked PAID",
                            extra={
                                "payment_link_id": payment_link_id,
                                "milestone_id": milestone_log_id,
                                "stripe_payment_intent_id": data.get("payment_intent"),
                                "stripe_checkout_session_id": data.get("id"),
                                "amount": amount_log,
                                "event_id": event_id,
                            },
                        )

            return {"processed": True}

        except Exception as e:
            logger.exception(
                "payment_link_webhook failed",
                extra={
                    "payment_link_id": payment_link_id,
                    "event_id": event_id,
                    "event_type": stripe_event.get("type")
                    if isinstance(stripe_event, dict)
                    else None,
                },
            )
            return {"processed": False, "error": str(e)}


# Singleton instance
vendor_service = VendorService()
