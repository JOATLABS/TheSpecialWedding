import hashlib
import hmac
import html
import logging
import os
import secrets
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.database import mongo
from app.core.settings import settings
from app.models.form import (
    CreateFormRequest,
    DuplicateFormRequest,
    FormDistributionStatus,
    SendFormRequest,
    SubmitFormRequest,
    UpdateFormRequest,
)
from app.services.email_service_resend import ResendEmailService
from app.services.form_upload_service import FormUploadService
from app.utils.csv_export import CSVSecurityError, FormResponseCSVExporter
from app.utils.form_conditional_logic import (
    filter_responses_to_visible,
    is_field_visible,
)
from app.utils.security_utils import FormSecurityValidator, InputSanitizer, rate_limiter

logger = logging.getLogger(__name__)


class FormService:
    # How long a per-recipient form access token is valid for. Mirrors the
    # contract token expiry to keep the planner mental model consistent.
    DEFAULT_FORM_TOKEN_TTL_DAYS = 30

    def __init__(self):
        self.forms_collection = mongo.get_forms_collection()
        self.responses_collection = mongo.db["form_responses"]
        self.distributions_collection = mongo.db["form_distributions"]
        self.wedding_collection = mongo.db["weddings"]
        self.email_service = ResendEmailService()
        self.upload_service = FormUploadService()

    # ------------------------------------------------------------------
    # Per-recipient access tokens
    # ------------------------------------------------------------------

    def _hash_form_access_token(self, raw_token: str) -> str:
        secret_key = settings.secret_key
        if not secret_key:
            raise RuntimeError("SECRET_KEY is required for form token hashing")

        return hmac.new(
            secret_key.encode("utf-8"),
            raw_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _verify_form_access_token(self, raw_token: str, stored_hash: str) -> bool:
        if not raw_token or not stored_hash:
            return False
        return hmac.compare_digest(
            self._hash_form_access_token(raw_token), stored_hash
        )

    def _issue_form_access_token(self) -> tuple[str, str, datetime]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_form_access_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.DEFAULT_FORM_TOKEN_TTL_DAYS
        )
        return raw_token, token_hash, expires_at

    @staticmethod
    def _planner_state_key(email: str) -> str:
        """Deterministic, collision-safe key for ``planner_state`` field paths.

        The previous implementation was ``email.replace(".", "_")``, which
        collided ``alice.smith@x`` with ``alice_smith@x`` and lost view
        state across distinct planners. We replace it with a SHA256 hex
        digest of the lowercased email so the keyspace is dot-free
        (Mongo nested-path requirement), case-insensitive, and
        collision-free.

        ``_legacy_planner_state_key`` is the old format and is consulted
        as a fallback in read paths so existing documents keep working
        across deploys; the next write under the new key tombstones the
        legacy entry via a ``$unset`` so the migration is incremental.
        """
        if not email:
            return "anonymous"
        normalized = email.strip().lower()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"u_{digest}"

    @staticmethod
    def _legacy_planner_state_key(email: str) -> str:
        return email.replace(".", "_")

    def _read_planner_state(
        self, planner_state: Dict[str, Any], email: str
    ) -> Dict[str, Any]:
        """Read a planner's state entry, transparently falling back to
        legacy key shapes for un-migrated docs.

        Lookup order: new SHA256 key, legacy ``email.replace('.', '_')``,
        bare email (used by some seed paths). The first match wins; any
        write path will tombstone the legacy entry on next save.
        """
        if not isinstance(planner_state, dict):
            return {}
        new_key = self._planner_state_key(email)
        if new_key in planner_state:
            return planner_state[new_key] or {}
        legacy_key = self._legacy_planner_state_key(email)
        if legacy_key in planner_state:
            return planner_state[legacy_key] or {}
        # Bare-email fallback: some pre-existing seed data and integration
        # paths used the raw email (with dots intact) as the field name —
        # which Mongo only accepts at the top level of a planner_state
        # subdocument. Honoring it here keeps in-flight data readable.
        if email and email in planner_state:
            return planner_state[email] or {}
        return {}

    @staticmethod
    def _normalize_owner_alias_emails(
        owner_alias_emails: Optional[List[str]],
    ) -> List[str]:
        normalized: list[str] = []
        for email in owner_alias_emails or []:
            if not email:
                continue
            candidate = email.lower().strip()
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        return normalized

    def _build_creator_query(
        self,
        created_by: Optional[str],
        owner_alias_emails: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        if created_by is None:
            return {}

        aliases = self._normalize_owner_alias_emails(owner_alias_emails)
        if aliases:
            return {"created_by": {"$in": aliases}}

        if not InputSanitizer.validate_email(created_by):
            raise HTTPException(status_code=400, detail="Invalid creator email")
        return {"created_by": created_by.lower().strip()}

    async def create_form(
        self,
        form_data: CreateFormRequest,
        created_by: str,
        *,
        actor_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new form with enhanced security validation"""
        try:
            # Rate limiting check
            if not rate_limiter.check_rate_limit(
                f"form_creation_{created_by}", limit=10, window_seconds=3600
            ):
                raise HTTPException(
                    status_code=429,
                    detail="Too many forms created. Please try again later.",
                )

            # Validate and sanitize form data
            try:
                sanitized_data = FormSecurityValidator.validate_form_data(
                    form_data.dict()
                )
            except ValueError as e:
                logger.warning(
                    f"Form validation failed for user {created_by}: {str(e)}"
                )
                raise HTTPException(status_code=400, detail=str(e))

            # Generate unique form ID
            form_id = f"form_{int(datetime.now().timestamp() * 1000)}"

            # Validate field IDs are unique (double-check after sanitization)
            field_ids = [field["id"] for field in sanitized_data["fields"]]
            if len(field_ids) != len(set(field_ids)):
                raise HTTPException(status_code=400, detail="Field IDs must be unique")

            # Sanitize created_by email
            if not InputSanitizer.validate_email(created_by):
                raise HTTPException(status_code=400, detail="Invalid creator email")

            creator_email = created_by.lower().strip()

            planner_state_key = self._planner_state_key(creator_email)
            planner_state = {
                planner_state_key: {
                    "last_viewed_responses_at": None,
                    "last_viewed_submission_count": 0,
                    "last_viewed_analytics_at": None,
                }
            }

            # Create form document with sanitized data
            form_doc = {
                "_id": form_id,
                "name": InputSanitizer.sanitize_text(sanitized_data["name"], 100),
                "form_type": sanitized_data.get("form_type", "general"),
                "settings": sanitized_data["settings"],
                "fields": sanitized_data["fields"],
                "created_by": creator_email,
                "wedding_id": sanitized_data.get("wedding_id"),
                "template_type": sanitized_data.get("template_type"),
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "submission_count": 0,
                "planner_state": planner_state,
            }
            if actor_email and actor_email.lower().strip() != creator_email:
                form_doc["created_by_actor"] = actor_email.lower().strip()

            # Insert form
            result = await self.forms_collection.insert_one(form_doc)

            if result.inserted_id:
                return {"id": form_id, "message": "Form created successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to create form")

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error creating form: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create form: {str(e)}"
            )

    async def duplicate_form(
        self,
        source_form_id: str,
        payload: DuplicateFormRequest,
        created_by: str,
        *,
        owner_alias_emails: Optional[List[str]] = None,
        actor_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a copy of an existing form for the same planner."""
        try:
            # Ensure the user can access the source form
            original_form = await self.get_form(
                source_form_id,
                created_by,
                owner_alias_emails=owner_alias_emails,
            )

            # Build the new form payload using the original structure
            duplicated_fields = deepcopy(original_form.get("fields", []))
            duplicated_settings = deepcopy(original_form.get("settings", {}))

            new_form_request = CreateFormRequest(
                name=payload.new_name,
                settings=duplicated_settings,
                fields=duplicated_fields,
                wedding_id=original_form.get("wedding_id"),
                template_type=original_form.get("template_type"),
            )

            return await self.create_form(
                new_form_request,
                created_by,
                actor_email=actor_email,
            )

        except HTTPException:
            raise
        except Exception as exc:
            logging.error(
                "Error duplicating form %s for user %s: %s",
                source_form_id,
                created_by,
                str(exc),
            )
            raise HTTPException(status_code=500, detail="Failed to duplicate form")

    async def get_forms(
        self,
        created_by: str,
        wedding_id: Optional[str] = None,
        is_root_admin: bool = False,
        *,
        viewer_email: Optional[str] = None,
        owner_alias_emails: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get forms for a user"""
        try:
            # ROOT_ADMIN can see all forms, others see only their own
            query: Dict[str, Any] = {"is_active": True}
            if not is_root_admin:
                query.update(self._build_creator_query(created_by, owner_alias_emails))
            if wedding_id:
                query["wedding_id"] = wedding_id

            forms = (
                await self.forms_collection.find(query)
                .sort("created_at", -1)
                .to_list(length=None)
            )

            # Convert ObjectId to string and format response
            viewer_key = None
            raw_viewer_email = None
            if not is_root_admin:
                raw_viewer_email = (viewer_email or created_by).lower().strip()
                viewer_key = self._planner_state_key(raw_viewer_email)

            for form in forms:
                form["id"] = form["_id"]
                form.pop("_id", None)

                submission_total = int(form.get("submission_count", 0) or 0)
                planner_state = form.get("planner_state", {}) or {}
                unread = 0

                if viewer_key:
                    # Read via the dual-key helper (new SHA256 key first,
                    # legacy email-replace key as fallback) so existing
                    # docs keep their state across the migration.
                    state = (
                        self._read_planner_state(planner_state, raw_viewer_email or "")
                        if raw_viewer_email
                        else (planner_state.get(viewer_key) or {})
                    )
                    last_seen = int(state.get("last_viewed_submission_count", 0) or 0)
                    unread = max(submission_total - last_seen, 0)

                form["unread_responses"] = unread
                form.pop("planner_state", None)

            return forms

        except Exception as e:
            logging.error(f"Error fetching forms: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch forms: {str(e)}"
            )

    async def get_form(
        self,
        form_id: str,
        created_by: Optional[str] = None,
        *,
        owner_alias_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get a specific form with security validation"""
        try:
            logger.info(f"get_form called: form_id={form_id}, created_by={created_by}")
            # Validate form_id format to prevent injection
            if not form_id or not isinstance(form_id, str):
                raise HTTPException(status_code=400, detail="Invalid form ID")

            # Sanitize form_id
            logger.info(f"Sanitizing form_id: {form_id}")
            form_id = InputSanitizer.sanitize_text(form_id, 100)
            if not form_id:
                raise HTTPException(status_code=400, detail="Invalid form ID")
            logger.info(f"Form ID after sanitization: {form_id}")

            query = {"_id": form_id, "is_active": True}
            if created_by is not None:
                logger.info(f"Validating created_by email: {created_by}")
                query.update(self._build_creator_query(created_by, owner_alias_emails))
            logger.info(f"Database query: {query}")
            form = await self.forms_collection.find_one(query)
            logger.info(f"Form found: {form is not None}")

            if not form:
                logger.info(f"Form not found: {form_id} for user: {created_by}")
                raise HTTPException(status_code=404, detail="Form not found")

            # Sanitize form data before returning
            form["id"] = form["_id"]
            form.pop("_id", None)
            form.pop("planner_state", None)

            # Sanitize sensitive data for public access
            if not created_by:  # Public access
                # Remove sensitive information
                form.pop("created_by", None)
                form.pop("template_type", None)
                form.pop("submission_count", None)

            # Sanitize settings for XSS protection
            if "settings" in form:
                settings = form["settings"]
                if "title" in settings:
                    settings["title"] = html.escape(settings["title"])
                if "description" in settings:
                    settings["description"] = html.escape(settings["description"])

            # Sanitize field labels and descriptions
            if "fields" in form:
                for field in form["fields"]:
                    if "label" in field:
                        field["label"] = html.escape(field["label"])
                    if "description" in field:
                        field["description"] = html.escape(field["description"])
                    if "placeholder" in field:
                        field["placeholder"] = html.escape(field["placeholder"])

            return form

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching form: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch form: {str(e)}"
            )

    async def update_form(
        self,
        form_id: str,
        form_data: UpdateFormRequest,
        created_by: str,
        *,
        owner_alias_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update an existing form with security validation"""
        try:
            # Validate inputs
            if not form_id or not isinstance(form_id, str):
                raise HTTPException(status_code=400, detail="Invalid form ID")

            if not InputSanitizer.validate_email(created_by):
                raise HTTPException(status_code=400, detail="Invalid creator email")

            # Sanitize form_id
            form_id = InputSanitizer.sanitize_text(form_id, 100)

            # Check if form exists and user owns it
            existing_form = await self.forms_collection.find_one(
                {
                    "_id": form_id,
                    "is_active": True,
                    **self._build_creator_query(created_by, owner_alias_emails),
                }
            )

            if not existing_form:
                logger.warning(
                    f"Update attempt on non-existent form {form_id} by {created_by}"
                )
                raise HTTPException(status_code=404, detail="Form not found")

            # Build update document with sanitization
            update_doc: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

            if form_data.name is not None:
                sanitized_name = InputSanitizer.sanitize_text(form_data.name, 100)
                if not sanitized_name:
                    raise HTTPException(status_code=400, detail="Invalid form name")
                update_doc["name"] = sanitized_name

            if form_data.settings is not None:
                try:
                    sanitized_settings = FormSecurityValidator.validate_form_settings(
                        form_data.settings.dict()
                    )
                    update_doc["settings"] = sanitized_settings
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))

            if form_data.fields is not None:
                try:
                    # Validate and sanitize fields
                    sanitized_fields = []
                    field_ids = []

                    for field in form_data.fields:
                        sanitized_field = FormSecurityValidator.validate_form_field(
                            field.dict()
                        )
                        sanitized_fields.append(sanitized_field)
                        field_ids.append(sanitized_field["id"])

                    # Check for unique field IDs
                    if len(field_ids) != len(set(field_ids)):
                        raise HTTPException(
                            status_code=400, detail="Field IDs must be unique"
                        )

                    update_doc["fields"] = sanitized_fields

                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))

            if form_data.is_active is not None:
                update_doc["is_active"] = bool(form_data.is_active)

            # Update form
            result = await self.forms_collection.update_one(
                {"_id": form_id}, {"$set": update_doc}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Form not found")

            return {"message": "Form updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error updating form: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update form: {str(e)}"
            )

    async def delete_form(
        self,
        form_id: str,
        created_by: str,
        is_root_admin: bool = False,
        *,
        owner_alias_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Soft delete a form"""
        try:
            logger.info(
                f"delete_form called: form_id={form_id}, created_by={created_by}, is_root_admin={is_root_admin}"
            )
            # ROOT_ADMIN can delete any form, others can only delete their own
            if is_root_admin:
                query = {"_id": form_id}
                logger.info(f"Using ROOT_ADMIN query: {query}")
            else:
                query = {
                    "_id": form_id,
                    **self._build_creator_query(created_by, owner_alias_emails),
                }
                logger.info(f"Using regular user query: {query}")
            # First, check if form exists
            existing_form = await self.forms_collection.find_one({"_id": form_id})
            logger.info(f"Form exists check: {existing_form is not None}")
            if existing_form:
                logger.info(
                    f"Form details: _id={existing_form.get('_id')}, created_by={existing_form.get('created_by')}, is_active={existing_form.get('is_active')}"
                )
            result = await self.forms_collection.update_one(
                query,
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info(
                f"Update result: matched_count={result.matched_count}, modified_count={result.modified_count}"
            )

            if result.matched_count == 0:
                logger.warning(
                    f"No form matched for deletion: form_id={form_id}, query={query}"
                )
                raise HTTPException(status_code=404, detail="Form not found")

            logger.info(f"Form {form_id} deleted successfully")
            return {"message": "Form deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting form: {str(e)}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500, detail=f"Failed to delete form: {str(e)}"
            )

    async def send_form(
        self,
        form_id: str,
        send_data: SendFormRequest,
        created_by: str,
        *,
        owner_alias_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send form to recipients via email"""
        try:
            # Get form
            form = await self.get_form(
                form_id,
                created_by,
                owner_alias_emails=owner_alias_emails,
            )

            # Generate form URL
            frontend_url = os.getenv("FRONTEND_URL")
            if not frontend_url:
                raise ValueError("FRONTEND_URL environment variable is required")
            form_url = f"{frontend_url}/forms/{form_id}"

            sent_count = 0
            failed_count = 0

            for recipient_email in send_data.recipient_emails:
                try:
                    # Create distribution record + per-recipient access token
                    distribution_id = str(uuid.uuid4())
                    raw_token, token_hash, token_expires_at = (
                        self._issue_form_access_token()
                    )
                    distribution_doc = {
                        "_id": distribution_id,
                        "form_id": form_id,
                        "recipient_email": recipient_email,
                        "wedding_id": send_data.wedding_id,
                        "sent_at": datetime.now(timezone.utc),
                        "status": FormDistributionStatus.SENDING.value,
                        "access_token_hash": token_hash,
                        "token_expires_at": token_expires_at,
                        # Snapshot reminder context so the scheduler can
                        # re-send without re-reading the form doc, and so
                        # later edits to the form's email settings don't
                        # retroactively change reminder behaviour for
                        # already-sent distributions.
                        "send_reminder": bool(
                            send_data.email_settings.send_reminder
                        ),
                        "reminder_days": int(
                            send_data.email_settings.reminder_days
                        ),
                        "reminder_subject": send_data.email_settings.subject,
                        "reminder_message": send_data.email_settings.message,
                        "reminder_sender_name": send_data.email_settings.sender_name,
                        "reminder_sent_at": None,
                        "reminder_count": 0,
                    }

                    # Per-recipient URL carries the distribution_id (join key)
                    # AND a one-time access token (?t=). The token is verified
                    # at submit-time so the link cannot be replayed once
                    # consumed and cannot be guessed without the email.
                    recipient_form_url = (
                        f"{form_url}?dist={distribution_id}&t={raw_token}"
                    )

                    # Generate personalized email content
                    email_html = self._generate_form_email_html(
                        form_title=form["settings"]["title"],
                        form_description=form["settings"].get("description", ""),
                        form_url=recipient_form_url,
                        sender_name=send_data.email_settings.sender_name,
                        custom_message=send_data.email_settings.message,
                    )

                    # Send email
                    if self.email_service.configured:
                        email_result = await self.email_service.send_email(
                            to_email=recipient_email,
                            subject=send_data.email_settings.subject,
                            html_content=email_html,
                            from_name=send_data.email_settings.sender_name,
                        )

                        if email_result.get("success"):
                            distribution_doc["status"] = FormDistributionStatus.SENT.value
                            distribution_doc["email_id"] = email_result.get("email_id")
                            sent_count += 1
                        else:
                            distribution_doc["status"] = FormDistributionStatus.FAILED.value
                            failed_count += 1
                    else:
                        distribution_doc["status"] = FormDistributionStatus.FAILED.value
                        failed_count += 1

                    # Save distribution record
                    await self.distributions_collection.insert_one(distribution_doc)

                except Exception as email_error:
                    logging.error(
                        f"Failed to send form to {recipient_email}: {str(email_error)}"
                    )
                    failed_count += 1

            return {
                "sent": sent_count,
                "failed": failed_count,
                "form_url": form_url,
                "message": f"Form sent to {sent_count} recipients",
            }

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error sending form: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to send form: {str(e)}"
            )

    async def send_form_reminders(self, *, now: Optional[datetime] = None) -> Dict[str, int]:
        """Send a one-shot reminder email per overdue, unsubmitted distribution.

        A distribution is eligible iff its snapshot at send-time enabled
        reminders, no response has been submitted yet, no reminder has
        previously been sent, the access token is still within its TTL,
        and (now - sent_at) >= reminder_days. Each reminder rotates the
        access token so the new email link is fresh and the prior link
        is invalidated — same security model as the original send.

        Designed to be called by a daily scheduler. Returns a small
        ``{sent, skipped, failed}`` summary for logging.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        frontend_url = os.getenv("FRONTEND_URL")
        if not frontend_url:
            logger.warning(
                "FRONTEND_URL not set — skipping form reminder pass"
            )
            return {"sent": 0, "skipped": 0, "failed": 0}

        eligible_cursor = self.distributions_collection.find(
            {
                "send_reminder": True,
                "submitted_at": None,
                "reminder_sent_at": None,
                "status": {
                    "$in": [
                        FormDistributionStatus.SENT.value,
                        FormDistributionStatus.OPENED.value,
                        FormDistributionStatus.CLICKED.value,
                    ]
                },
            }
        )
        candidates = await eligible_cursor.to_list(length=None)

        sent = 0
        skipped = 0
        failed = 0

        for distribution in candidates:
            distribution_id = distribution.get("_id")
            try:
                # Skip if reminder window not yet reached.
                sent_at = distribution.get("sent_at")
                if not sent_at:
                    skipped += 1
                    continue
                if sent_at.tzinfo is None:
                    sent_at = sent_at.replace(tzinfo=timezone.utc)
                reminder_days = int(distribution.get("reminder_days", 7))
                if (now - sent_at) < timedelta(days=reminder_days):
                    skipped += 1
                    continue

                # Skip if the access token has already expired — a stale
                # link in a reminder helps no one.
                token_expires_at = distribution.get("token_expires_at")
                if token_expires_at:
                    if token_expires_at.tzinfo is None:
                        token_expires_at = token_expires_at.replace(tzinfo=timezone.utc)
                    if token_expires_at < now:
                        skipped += 1
                        continue

                form = await self.forms_collection.find_one(
                    {"_id": distribution.get("form_id")}
                )
                if not form or not form.get("is_active", True):
                    skipped += 1
                    continue

                # Rotate the token so the new email link is fresh and the
                # original link stops working (prevents stale-link
                # confusion if the recipient kept it open).
                raw_token, token_hash, new_expires_at = (
                    self._issue_form_access_token()
                )
                reminder_form_url = (
                    f"{frontend_url}/forms/{distribution['form_id']}"
                    f"?dist={distribution_id}&t={raw_token}"
                )

                subject_base = (
                    distribution.get("reminder_subject")
                    or form.get("settings", {}).get("title", "Form")
                )
                reminder_subject = f"Reminder: {subject_base}"
                custom_message = (
                    distribution.get("reminder_message") or ""
                )
                sender_name = distribution.get("reminder_sender_name") or ""

                email_html = self._generate_form_email_html(
                    form_title=form["settings"]["title"],
                    form_description=form["settings"].get("description", ""),
                    form_url=reminder_form_url,
                    sender_name=sender_name,
                    custom_message=custom_message,
                )

                if self.email_service.configured:
                    email_result = await self.email_service.send_email(
                        to_email=distribution["recipient_email"],
                        subject=reminder_subject,
                        html_content=email_html,
                        from_name=sender_name,
                    )
                else:
                    email_result = {"success": False}

                if email_result.get("success"):
                    await self.distributions_collection.update_one(
                        {"_id": distribution_id},
                        {
                            "$set": {
                                "access_token_hash": token_hash,
                                "token_expires_at": new_expires_at,
                                "reminder_sent_at": now,
                            },
                            "$inc": {"reminder_count": 1},
                        },
                    )
                    sent += 1
                else:
                    failed += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "Reminder send failed for distribution %s: %s",
                    distribution_id,
                    exc,
                )
                failed += 1

        if sent or failed:
            logger.info(
                "Form reminder pass complete: sent=%d skipped=%d failed=%d",
                sent,
                skipped,
                failed,
            )
        return {"sent": sent, "skipped": skipped, "failed": failed}

    async def submit_form_response(
        self,
        form_id: str,
        response_data: SubmitFormRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a form response with security validation"""
        try:
            # Rate limiting for form submissions
            rate_key = f"form_submission_{ip_address or 'unknown'}"
            if not rate_limiter.check_rate_limit(
                rate_key, limit=100, window_seconds=3600
            ):
                raise HTTPException(
                    status_code=429,
                    detail="Too many form submissions. Please try again later.",
                )

            # Validate form_id
            if not form_id or not isinstance(form_id, str):
                raise HTTPException(status_code=400, detail="Invalid form ID")

            form_id = InputSanitizer.sanitize_text(form_id, 100)
            if not form_id:
                raise HTTPException(status_code=400, detail="Invalid form ID")

            # Get form (public access)
            form = await self.get_form(form_id)

            if not form["is_active"]:
                logger.info(f"Submission attempt to inactive form: {form_id}")
                raise HTTPException(
                    status_code=400, detail="Form is no longer accepting responses"
                )

            # Validate and sanitize response data
            try:
                sanitized_responses = FormSecurityValidator.validate_form_response(
                    response_data.responses, form["fields"]
                )
            except ValueError as e:
                logger.warning(f"Invalid form response for form {form_id}: {str(e)}")
                raise HTTPException(status_code=400, detail="Invalid response data")

            # Drop values for fields hidden by conditional_logic so stale data
            # from a temporarily-shown branch can't be persisted.
            sanitized_responses = filter_responses_to_visible(
                form["fields"], sanitized_responses
            )

            # Resolve FILE_UPLOAD field values to verified upload metadata.
            # FILE_UPLOAD requires a tokenized link (we need the
            # distribution_id to scope the lookup); the response value
            # must be a file_id that was actually issued by store_upload
            # for this same form + distribution.
            file_upload_field_ids = {
                field["id"]
                for field in form["fields"]
                if field.get("type") == "file_upload"
            }
            if file_upload_field_ids:
                for field_id in list(sanitized_responses.keys()):
                    if field_id not in file_upload_field_ids:
                        continue
                    raw_value = sanitized_responses[field_id]
                    file_id = (
                        raw_value
                        if isinstance(raw_value, str)
                        else (raw_value.get("file_id") if isinstance(raw_value, dict) else None)
                    )
                    if not file_id:
                        raise HTTPException(
                            status_code=400,
                            detail="File upload reference is invalid",
                        )
                    if not response_data.distribution_id:
                        raise HTTPException(
                            status_code=400,
                            detail="File upload requires the original form link",
                        )
                    upload_record = (
                        await self.upload_service.get_upload_for_form_distribution(
                            file_id=file_id,
                            form_id=form_id,
                            distribution_id=response_data.distribution_id,
                        )
                    )
                    if not upload_record or upload_record.get("field_id") != field_id:
                        raise HTTPException(
                            status_code=400,
                            detail="Unrecognized file upload",
                        )
                    sanitized_responses[field_id] = {
                        "file_id": upload_record["_id"],
                        "filename": upload_record.get("filename"),
                        "content_type": upload_record.get("content_type"),
                        "size_bytes": upload_record.get("size_bytes"),
                        "url": upload_record.get("url"),
                    }

            # Validate required fields, skipping any whose conditional_logic
            # makes them hidden under the current responses.
            for field in form["fields"]:
                if not field.get("required"):
                    continue
                if not is_field_visible(field, sanitized_responses):
                    continue
                if field["id"] not in sanitized_responses:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Required field '{html.escape(field['label'])}' is missing",
                    )

            # Sanitize submitter information
            submitted_by_email = None
            submitted_by_name = None

            if response_data.submitted_by_email:
                if InputSanitizer.validate_email(response_data.submitted_by_email):
                    submitted_by_email = (
                        response_data.submitted_by_email.lower().strip()
                    )
                else:
                    raise HTTPException(status_code=400, detail="Invalid email address")

            if response_data.submitted_by_name:
                submitted_by_name = InputSanitizer.sanitize_text(
                    response_data.submitted_by_name, 100
                )

            # Resolve the optional distribution_id hint from the per-recipient
            # link. Two paths:
            #   1. Tokenized path (distribution_id + access_token both supplied):
            #      strict verification — wrong token -> 403, expired -> 410,
            #      already submitted -> 409. Single-submission is enforced
            #      per-distribution regardless of the form's
            #      allow_multiple_submissions flag.
            #   2. Hint-only path (distribution_id only, no token):
            #      kept for the Item 3 query-param flow; bad ids silently
            #      dropped without penalty so the submission still proceeds.
            resolved_distribution_id: Optional[str] = None
            if response_data.distribution_id:
                distribution_match = await self.distributions_collection.find_one(
                    {"_id": response_data.distribution_id, "form_id": form_id}
                )
                if not distribution_match:
                    if response_data.access_token:
                        # A token was supplied for an unknown distribution —
                        # treat as forbidden, not a benign typo.
                        raise HTTPException(
                            status_code=403, detail="Invalid form access link"
                        )
                    logger.info(
                        "Ignoring distribution_id %s on submission to form %s "
                        "(no matching distribution row)",
                        response_data.distribution_id,
                        form_id,
                    )
                else:
                    if response_data.access_token:
                        stored_hash = distribution_match.get("access_token_hash")
                        if not stored_hash or not self._verify_form_access_token(
                            response_data.access_token, stored_hash
                        ):
                            raise HTTPException(
                                status_code=403, detail="Invalid form access link"
                            )
                        token_expires_at = distribution_match.get("token_expires_at")
                        if token_expires_at:
                            # Mongo can return naive datetimes; assume UTC.
                            if token_expires_at.tzinfo is None:
                                token_expires_at = token_expires_at.replace(
                                    tzinfo=timezone.utc
                                )
                            if token_expires_at < datetime.now(timezone.utc):
                                raise HTTPException(
                                    status_code=410,
                                    detail="This form access link has expired",
                                )
                        if distribution_match.get("submitted_at"):
                            raise HTTPException(
                                status_code=409,
                                detail="A response has already been submitted with this link",
                            )
                    resolved_distribution_id = response_data.distribution_id

            # Check if multiple submissions are allowed
            if not form["settings"].get("allow_multiple_submissions", False):
                if submitted_by_email:
                    existing_response = await self.responses_collection.find_one(
                        {"form_id": form_id, "submitted_by_email": submitted_by_email}
                    )
                    if existing_response:
                        raise HTTPException(
                            status_code=400,
                            detail="You have already submitted a response to this form",
                        )

            # Create response document with sanitized data
            response_id = str(uuid.uuid4())

            # Sanitize IP address and user agent
            safe_ip = (
                InputSanitizer.sanitize_text(ip_address, 45) if ip_address else None
            )
            safe_user_agent = (
                InputSanitizer.sanitize_text(user_agent, 500) if user_agent else None
            )

            response_doc = {
                "_id": response_id,
                "form_id": form_id,
                "distribution_id": resolved_distribution_id,
                "responses": sanitized_responses,
                "submitted_by_email": submitted_by_email,
                "submitted_by_name": submitted_by_name,
                "wedding_id": form.get("wedding_id"),
                "ip_address": safe_ip,
                "user_agent": safe_user_agent,
                "submitted_at": datetime.now(timezone.utc),
                "metadata": {
                    "security_validated": True,
                    "sanitized_at": datetime.now(timezone.utc),
                },
            }

            # Save response
            result = await self.responses_collection.insert_one(response_doc)

            if result.inserted_id:
                # Update form submission count
                await self.forms_collection.update_one(
                    {"_id": form_id},
                    {
                        "$inc": {"submission_count": 1},
                        "$set": {"updated_at": datetime.now(timezone.utc)},
                    },
                )

                # Update distribution status. Prefer the explicit
                # distribution_id from the per-recipient link; fall back to
                # email-match for legacy / non-tokenized flows.
                distribution_query: Optional[Dict[str, Any]] = None
                if resolved_distribution_id:
                    distribution_query = {
                        "_id": resolved_distribution_id,
                        "form_id": form_id,
                    }
                elif submitted_by_email:
                    distribution_query = {
                        "form_id": form_id,
                        "recipient_email": submitted_by_email,
                    }

                if distribution_query is not None:
                    await self.distributions_collection.update_one(
                        distribution_query,
                        {
                            "$set": {
                                "submitted_at": datetime.now(timezone.utc),
                                "status": FormDistributionStatus.SUBMITTED.value,
                            }
                        },
                    )

                # Log successful submission for security monitoring
                logger.info(
                    f"Form submission successful: form_id={form_id}, "
                    f"email={submitted_by_email}, ip={safe_ip}"
                )

                # Notify planner about the form submission
                await self._notify_planner_form_submission(
                    form=form,
                    submitter_name=submitted_by_name
                    or submitted_by_email
                    or "Anonymous",
                    form_id=form_id,
                )

                # Sanitize response message to prevent XSS
                success_message = form["settings"].get(
                    "success_message", "Thank you for your submission!"
                )
                safe_success_message = html.escape(success_message)

                redirect_url = form["settings"].get("redirect_url")
                safe_redirect_url = None
                if redirect_url and InputSanitizer.validate_url(redirect_url):
                    safe_redirect_url = redirect_url

                return {
                    "id": response_id,
                    "message": safe_success_message,
                    "redirect_url": safe_redirect_url,
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to save response")

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error submitting form response: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to submit response: {str(e)}"
            )

    async def get_form_responses(
        self,
        form_id: str,
        created_by: str,
        *,
        owner_alias_emails: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get all responses for a form"""
        try:
            # Verify user owns the form
            await self.get_form(
                form_id,
                created_by,
                owner_alias_emails=owner_alias_emails,
            )

            responses = (
                await self.responses_collection.find({"form_id": form_id})
                .sort("submitted_at", -1)
                .to_list(length=None)
            )

            # Format responses
            for response in responses:
                response["id"] = response["_id"]
                response.pop("_id", None)

            return responses

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching form responses: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch responses: {str(e)}"
            )

    async def check_form_distribution_link(
        self,
        form_id: str,
        distribution_id: str,
        access_token: str,
    ) -> Dict[str, Any]:
        """Public, unauthenticated check for a per-recipient form link.

        Returns ``{valid, expired, already_submitted, recipient_name}`` so
        the public form page can decide whether to render the form, show
        an "already responded" message, or show "link expired" — without
        ever leaking distribution data to bad tokens (404 instead).
        """
        if not (form_id and distribution_id and access_token):
            raise HTTPException(status_code=400, detail="Invalid form access link")

        distribution = await self.distributions_collection.find_one(
            {"_id": distribution_id, "form_id": form_id}
        )
        if not distribution:
            # Indistinguishable from a wrong token to prevent enumeration.
            raise HTTPException(status_code=404, detail="Form access link not found")

        stored_hash = distribution.get("access_token_hash")
        if not stored_hash or not self._verify_form_access_token(
            access_token, stored_hash
        ):
            raise HTTPException(status_code=404, detail="Form access link not found")

        expired = False
        token_expires_at = distribution.get("token_expires_at")
        if token_expires_at:
            if token_expires_at.tzinfo is None:
                token_expires_at = token_expires_at.replace(tzinfo=timezone.utc)
            expired = token_expires_at < datetime.now(timezone.utc)

        already_submitted = distribution.get("submitted_at") is not None

        # Best-effort: record the click on first valid hit
        if not already_submitted and not expired and not distribution.get("clicked_at"):
            await self.distributions_collection.update_one(
                {"_id": distribution_id, "form_id": form_id},
                {
                    "$set": {
                        "clicked_at": datetime.now(timezone.utc),
                        "status": FormDistributionStatus.CLICKED.value,
                    }
                },
            )

        return {
            "valid": not expired and not already_submitted,
            "expired": expired,
            "already_submitted": already_submitted,
            "recipient_name": distribution.get("recipient_name"),
            "recipient_email": distribution.get("recipient_email"),
        }

    async def get_form_distributions(
        self,
        form_id: str,
        created_by: str,
        *,
        owner_alias_emails: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List distribution rows for a form with their submission state.

        Powers the "who has not responded" surface: each row carries the
        recipient, the timeline (sent/opened/clicked/submitted), and the
        joinable distribution_id that responses now persist.
        """
        try:
            # Ownership check piggybacks on get_form
            await self.get_form(
                form_id,
                created_by,
                owner_alias_emails=owner_alias_emails,
            )

            query: Dict[str, Any] = {"form_id": form_id}
            if status:
                try:
                    # Single source of truth for the status vocabulary —
                    # invalid values now raise the same 400 they used to,
                    # but we get type-checker support for callers.
                    query["status"] = FormDistributionStatus(status).value
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail="Invalid distribution status filter"
                    )

            distributions = (
                await self.distributions_collection.find(query)
                .sort("sent_at", -1)
                .to_list(length=None)
            )

            for dist in distributions:
                dist["id"] = dist["_id"]
                dist.pop("_id", None)

            return distributions

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching form distributions: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to fetch distributions"
            )

    async def mark_form_viewed(
        self,
        form_id: str,
        viewer_email: str,
        scope: str,
        submission_count: Optional[int] = None,
        *,
        owner_alias_emails: Optional[List[str]] = None,
        is_root_admin: bool = False,
    ) -> Dict[str, Any]:
        """Persist when a planner last viewed responses or analytics for a form."""

        if not InputSanitizer.validate_email(viewer_email):
            raise HTTPException(status_code=400, detail="Invalid viewer email")

        if scope not in {"responses", "analytics"}:
            raise HTTPException(status_code=400, detail="Unsupported view scope")

        if not form_id or not isinstance(form_id, str):
            raise HTTPException(status_code=400, detail="Invalid form ID")

        sanitized_form_id = InputSanitizer.sanitize_text(form_id, 100)
        if not sanitized_form_id:
            raise HTTPException(status_code=400, detail="Invalid form ID")

        normalized_email = viewer_email.lower().strip()
        state_key = self._planner_state_key(normalized_email)

        base_projection = {
            "planner_state": 1,
            "submission_count": 1,
            "is_active": 1,
            "created_by": 1,
        }
        if is_root_admin:
            form = await self.forms_collection.find_one(
                {"_id": sanitized_form_id}, base_projection
            )
        else:
            form = await self.forms_collection.find_one(
                {
                    "_id": sanitized_form_id,
                    "is_active": True,
                    **self._build_creator_query(normalized_email, owner_alias_emails),
                },
                base_projection,
            )

        if not form:
            if not is_root_admin:
                # Differentiate between unauthorized access and missing forms for clearer errors
                exists = await self.forms_collection.find_one(
                    {"_id": sanitized_form_id}, {"_id": 1}
                )
                if exists:
                    raise HTTPException(status_code=403, detail="Access denied to form")
            raise HTTPException(status_code=404, detail="Form not found")

        if not form.get("is_active", True) and not is_root_admin:
            raise HTTPException(status_code=404, detail="Form not found")

        now = datetime.now(timezone.utc)
        update_fields: Dict[str, Any] = {}

        total_submissions = int(form.get("submission_count", 0) or 0)
        planner_state = form.get("planner_state", {}) or {}
        existing_state = self._read_planner_state(planner_state, normalized_email)
        unread_after_update = max(
            total_submissions
            - int(existing_state.get("last_viewed_submission_count", 0) or 0),
            0,
        )

        if scope == "responses":
            latest_known = submission_count
            if latest_known is None:
                latest_known = total_submissions

            latest_int = max(int(latest_known or 0), 0)
            update_fields[f"planner_state.{state_key}.last_viewed_submission_count"] = (
                latest_int
            )
            update_fields[f"planner_state.{state_key}.last_viewed_responses_at"] = now
            unread_after_update = max(total_submissions - latest_int, 0)

        if scope == "analytics":
            update_fields[f"planner_state.{state_key}.last_viewed_analytics_at"] = now

        # Tombstone the legacy key if we read state from it. We avoid
        # repeated $unset for already-migrated docs by guarding on the
        # presence of the legacy key in the loaded planner_state.
        update_payload: Dict[str, Any] = {"$set": update_fields}
        legacy_key = self._legacy_planner_state_key(normalized_email)
        if legacy_key != state_key and legacy_key in planner_state:
            update_payload["$unset"] = {f"planner_state.{legacy_key}": ""}

        await self.forms_collection.update_one(
            {"_id": sanitized_form_id}, update_payload, upsert=False
        )

        return {
            "message": "Form view recorded",
            "unread_responses": unread_after_update,
        }

    async def get_form_analytics(
        self,
        form_id: str,
        created_by: str,
        *,
        owner_alias_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get analytics for a form"""
        try:
            # Verify user owns the form
            form = await self.get_form(
                form_id,
                created_by,
                owner_alias_emails=owner_alias_emails,
            )

            # Get response count
            response_count = await self.responses_collection.count_documents(
                {"form_id": form_id}
            )

            # Get distribution stats
            distributions = await self.distributions_collection.find(
                {"form_id": form_id}
            ).to_list(length=None)
            sent_count = len(distributions)
            opened_count = len([d for d in distributions if d.get("opened_at")])
            clicked_count = len([d for d in distributions if d.get("clicked_at")])
            submitted_count = len([d for d in distributions if d.get("submitted_at")])

            # Calculate rates
            open_rate = round(
                (opened_count / sent_count * 100) if sent_count > 0 else 0, 1
            )
            click_rate = round(
                (clicked_count / sent_count * 100) if sent_count > 0 else 0, 1
            )
            completion_rate = round(
                (submitted_count / sent_count * 100) if sent_count > 0 else 0, 1
            )

            return {
                "form_id": form_id,
                "form_name": form["name"],
                "total_responses": response_count,
                "distribution_stats": {
                    "sent": sent_count,
                    "opened": opened_count,
                    "clicked": clicked_count,
                    "submitted": submitted_count,
                    "open_rate": open_rate,
                    "click_rate": click_rate,
                    "completion_rate": completion_rate,
                },
                "created_at": form["created_at"],
                "last_response": await self._get_last_response_time(form_id),
            }

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching form analytics: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch analytics: {str(e)}"
            )

    async def _get_last_response_time(self, form_id: str):
        """Get the timestamp of the most recent form response"""
        try:
            last_response = await self.responses_collection.find_one(
                {"form_id": form_id}, sort=[("submitted_at", -1)]
            )
            return last_response.get("submitted_at") if last_response else None
        except Exception:
            return None

    def _generate_form_email_html(
        self,
        form_title: str,
        form_description: str,
        form_url: str,
        sender_name: str,
        custom_message: str,
    ) -> str:
        """Generate HTML email for form distribution"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 1px; }}
                .header p {{ margin: 10px 0 0; font-size: 16px; opacity: 0.9; }}
                .content {{ background: #ffffff; padding: 40px 30px; }}
                .content p {{ margin: 15px 0; }}
                .form-preview {{ background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 25px 0; text-align: center; }}
                .form-preview h3 {{ margin: 0 0 10px; color: #1e3a5f; }}
                .form-preview p {{ margin: 0; color: #666; font-size: 14px; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; transition: background-color 0.3s; }}
                .button:hover {{ background-color: #b6736d; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
                .footer p {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Form Request</h1>
                    <p>From {sender_name}</p>
                </div>
                <div class="content">
                    <p>Hello,</p>
                    <p>{custom_message}</p>

                    <div class="form-preview">
                        <h3>{form_title}</h3>
                        {f"<p>{form_description}</p>" if form_description else ""}
                    </div>

                    <p>Please click the button below to access and complete the form:</p>

                    <div class="button-container">
                        <a href="{form_url}" class="button">Complete Form</a>
                    </div>

                    <p style="text-align: center; color: #666; font-size: 14px;">
                        If the button doesn't work, copy and paste this link into your browser:<br>
                        <a href="{form_url}">{form_url}</a>
                    </p>
                </div>
                <div class="footer">
                    <p>This form was sent via Special Wedding Platform</p>
                    <p> 2025 Special Wedding. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

    async def export_form_responses_csv(
        self,
        form_id: str,
        created_by: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_metadata: bool = True,
        *,
        owner_alias_emails: Optional[List[str]] = None,
        exported_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export form responses to CSV format with enhanced security validation.

        Args:
            form_id: The form ID to export responses for
            created_by: Email of the user requesting the export (for authorization)
            date_from: Optional start date filter (ISO format string)
            date_to: Optional end date filter (ISO format string)
            include_metadata: Whether to include submission metadata columns

        Returns:
            Dict containing CSV content and export metadata

        Raises:
            HTTPException: For validation, authorization, or processing errors
            CSVSecurityError: For CSV security-related issues
        """
        try:
            # Rate limiting for CSV exports (more restrictive than regular API calls)
            if not rate_limiter.check_rate_limit(
                f"csv_export_{created_by}", limit=5, window_seconds=3600
            ):
                raise HTTPException(
                    status_code=429,
                    detail="Too many CSV exports requested. Please try again later.",
                )

            # Validate and sanitize inputs
            if not form_id or not isinstance(form_id, str):
                raise HTTPException(status_code=400, detail="Invalid form ID")

            if not InputSanitizer.validate_email(created_by):
                raise HTTPException(status_code=400, detail="Invalid creator email")

            form_id = InputSanitizer.sanitize_text(form_id, 100)
            if not form_id:
                raise HTTPException(status_code=400, detail="Invalid form ID")

            # Get form (this also verifies user ownership)
            form = await self.get_form(
                form_id,
                created_by,
                owner_alias_emails=owner_alias_emails,
            )
            if not form:
                raise HTTPException(status_code=404, detail="Form not found")

            # Get all responses for the form
            responses = await self.get_form_responses(
                form_id,
                created_by,
                owner_alias_emails=owner_alias_emails,
            )

            # Validate date parameters
            parsed_date_from = None
            parsed_date_to = None

            if date_from:
                try:
                    # Support various date formats
                    date_from = InputSanitizer.sanitize_text(date_from, 50)
                    parsed_date_from = datetime.fromisoformat(
                        date_from.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid date_from parameter: {date_from}")
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid date_from format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                    )

            if date_to:
                try:
                    date_to = InputSanitizer.sanitize_text(date_to, 50)
                    parsed_date_to = datetime.fromisoformat(
                        date_to.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid date_to parameter: {date_to}")
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid date_to format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                    )

            # Validate date range
            if (
                parsed_date_from
                and parsed_date_to
                and parsed_date_from > parsed_date_to
            ):
                raise HTTPException(
                    status_code=400, detail="date_from cannot be after date_to"
                )

            # Log export attempt for security audit
            logger.info(
                f"CSV export requested: form_id={form_id}, user={created_by}, "
                f"responses_count={len(responses)}, date_from={date_from}, date_to={date_to}"
            )

            # Check if there are any responses to export
            if not responses:
                logger.info(f"No responses to export for form {form_id}")
                # Still generate empty CSV with headers

            # Limit export size to prevent DoS
            max_export_size = 10000  # Maximum number of responses to export
            total_response_count = len(responses)
            truncated = total_response_count > max_export_size
            truncated_count = (
                total_response_count - max_export_size if truncated else 0
            )
            if truncated:
                logger.warning(
                    "Export size limited: %s responses truncated to %s for form %s "
                    "(user=%s); %s rows omitted from CSV",
                    total_response_count,
                    max_export_size,
                    form_id,
                    created_by,
                    truncated_count,
                )
                responses = responses[:max_export_size]

            # Prepare export options
            export_options = {
                "include_metadata": include_metadata,
                "date_from": parsed_date_from,
                "date_to": parsed_date_to,
                "max_responses": max_export_size,
            }

            # Use the CSV exporter utility
            csv_exporter = FormResponseCSVExporter()
            export_result = csv_exporter.export_responses(
                form_data=form, responses=responses, options=export_options
            )

            # Add additional metadata. Surfacing truncation lets the
            # planner UI render an honest banner ("Exported 10,000 of
            # 47,832 responses") instead of silently dropping data.
            export_result.update(
                {
                    "form_id": form_id,
                    "form_name": form.get("name", "Unknown Form"),
                    "exported_by": exported_by or created_by,
                    "total_response_count": total_response_count,
                    "truncated": truncated,
                    "truncated_count": truncated_count,
                    "max_export_size": max_export_size,
                    "request_params": {
                        "date_from": date_from,
                        "date_to": date_to,
                        "include_metadata": include_metadata,
                    },
                }
            )

            # Log successful export
            logger.info(
                f"CSV export completed: form_id={form_id}, user={created_by}, "
                f"exported_count={export_result.get('exported_count', 0)}, "
                f"file_size={export_result.get('size', 0)} bytes"
            )

            return export_result

        except HTTPException:
            raise
        except CSVSecurityError as e:
            logger.error(f"CSV security error in export: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Export failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error exporting form responses to CSV: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to export form responses. Please try again later.",
            )

    async def _notify_planner_form_submission(
        self, form: Dict[str, Any], submitter_name: str, form_id: str
    ):
        """Notify the planner about a form submission"""
        try:
            wedding_id = form.get("wedding_id")
            form_title = form.get("settings", {}).get(
                "title", form.get("name", "Unknown Form")
            )

            # If no wedding_id, try to find planner from the form creator
            planner_email = None

            if wedding_id:
                # Get wedding to find planner
                wedding = await self.wedding_collection.find_one({"_id": wedding_id})
                if wedding:
                    planner_email = wedding.get("assigned_planner_email")
            else:
                # Use form creator as fallback
                planner_email = form.get("created_by")

            if not planner_email:
                logger.debug(f"No planner found for form {form_id}")
                return

            # Import here to avoid circular imports
            from app.services.planner_notification_service import (
                planner_notification_service,
            )

            await planner_notification_service.notify_form_submission(
                planner_id=planner_email,
                wedding_id=wedding_id or "",
                form_type=form_title,
                submitter_name=submitter_name,
                form_id=form_id,
            )
            logger.info(f"Form submission notification sent to {planner_email}")

        except Exception as e:
            # Don't fail the form submission if notification fails
            logger.error(f"Failed to send form submission notification: {str(e)}")
