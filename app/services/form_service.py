from fastapi import HTTPException
from app.core.database import mongo
from app.models.form import (
    FormModel,
    FormResponse,
    FormDistribution,
    CreateFormRequest,
    UpdateFormRequest,
    SendFormRequest,
    SubmitFormRequest,
    DuplicateFormRequest,
)
from app.services.email_service_resend import ResendEmailService
from app.utils.security_utils import (
    FormSecurityValidator, InputSanitizer, rate_limiter
)
from app.utils.csv_export import FormResponseCSVExporter, CSVSecurityError
from datetime import datetime
from typing import List, Dict, Any, Optional
from copy import deepcopy
import logging
import uuid
import os
import html

logger = logging.getLogger(__name__)


class FormService:
    def __init__(self):
        self.forms_collection = mongo.get_forms_collection()
        self.responses_collection = mongo.db["form_responses"]
        self.distributions_collection = mongo.db["form_distributions"]
        self.wedding_collection = mongo.db["weddings"]
        self.email_service = ResendEmailService()

    @staticmethod
    def _planner_state_key(email: str) -> str:
        return email.replace('.', '_')

    async def create_form(self, form_data: CreateFormRequest, created_by: str) -> Dict[str, Any]:
        """Create a new form with enhanced security validation"""
        try:
            # Rate limiting check
            if not rate_limiter.check_rate_limit(
                f"form_creation_{created_by}",
                limit=10,
                window_seconds=3600
            ):
                raise HTTPException(
                    status_code=429,
                    detail="Too many forms created. Please try again later."
                )

            # Validate and sanitize form data
            try:
                sanitized_data = FormSecurityValidator.validate_form_data(form_data.dict())
            except ValueError as e:
                logger.warning(f"Form validation failed for user {created_by}: {str(e)}")
                raise HTTPException(status_code=400, detail=str(e))

            # Generate unique form ID
            form_id = f"form_{int(datetime.now().timestamp() * 1000)}"

            # Validate field IDs are unique (double-check after sanitization)
            field_ids = [field['id'] for field in sanitized_data['fields']]
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
                "name": InputSanitizer.sanitize_text(sanitized_data['name'], 100),
                "settings": sanitized_data['settings'],
                "fields": sanitized_data['fields'],
                "created_by": creator_email,
                "wedding_id": sanitized_data.get('wedding_id'),
                "template_type": sanitized_data.get('template_type'),
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "submission_count": 0,
                "planner_state": planner_state,
            }

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
            raise HTTPException(status_code=500, detail=f"Failed to create form: {str(e)}")

    async def duplicate_form(self, source_form_id: str, payload: DuplicateFormRequest, created_by: str) -> Dict[str, Any]:
        """Create a copy of an existing form for the same planner."""
        try:
            # Ensure the user can access the source form
            original_form = await self.get_form(source_form_id, created_by)

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

            return await self.create_form(new_form_request, created_by)

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

    async def get_forms(self, created_by: str, wedding_id: Optional[str] = None, is_root_admin: bool = False) -> List[Dict[str, Any]]:
        """Get forms for a user"""
        try:
            # ROOT_ADMIN can see all forms, others see only their own
            query: Dict[str, Any] = {"is_active": True}
            if not is_root_admin:
                query["created_by"] = created_by
            if wedding_id:
                query["wedding_id"] = wedding_id

            forms = await self.forms_collection.find(query).sort("created_at", -1).to_list(length=None)

            # Convert ObjectId to string and format response
            viewer_key = None
            raw_viewer_email = None
            if created_by and not is_root_admin:
                raw_viewer_email = created_by.lower().strip()
                viewer_key = self._planner_state_key(raw_viewer_email)

            for form in forms:
                form["id"] = form["_id"]
                form.pop("_id", None)

                submission_total = int(form.get("submission_count", 0) or 0)
                planner_state = form.get("planner_state", {}) or {}
                unread = 0

                if viewer_key:
                    state = (
                        planner_state.get(viewer_key) or (planner_state.get(raw_viewer_email) if raw_viewer_email else {}) or {}
                    )
                    last_seen = int(state.get("last_viewed_submission_count", 0) or 0)
                    unread = max(submission_total - last_seen, 0)

                form["unread_responses"] = unread
                form.pop("planner_state", None)

            return forms

        except Exception as e:
            logging.error(f"Error fetching forms: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch forms: {str(e)}")

    async def get_form(self, form_id: str, created_by: Optional[str] = None) -> Dict[str, Any]:
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
                # Validate and sanitize created_by email
                if not InputSanitizer.validate_email(created_by):
                    raise HTTPException(status_code=400, detail="Invalid creator email")
                query["created_by"] = created_by.lower().strip()
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
            raise HTTPException(status_code=500, detail=f"Failed to fetch form: {str(e)}")

    async def update_form(self, form_id: str, form_data: UpdateFormRequest, created_by: str) -> Dict[str, Any]:
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
            existing_form = await self.forms_collection.find_one({
                "_id": form_id,
                "created_by": created_by.lower().strip(),
                "is_active": True
            })

            if not existing_form:
                logger.warning(f"Update attempt on non-existent form {form_id} by {created_by}")
                raise HTTPException(status_code=404, detail="Form not found")

            # Build update document with sanitization
            update_doc: Dict[str, Any] = {"updated_at": datetime.utcnow()}

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
                        sanitized_field = FormSecurityValidator.validate_form_field(field.dict())
                        sanitized_fields.append(sanitized_field)
                        field_ids.append(sanitized_field['id'])

                    # Check for unique field IDs
                    if len(field_ids) != len(set(field_ids)):
                        raise HTTPException(status_code=400, detail="Field IDs must be unique")

                    update_doc["fields"] = sanitized_fields

                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))

            if form_data.is_active is not None:
                update_doc["is_active"] = bool(form_data.is_active)

            # Update form
            result = await self.forms_collection.update_one(
                {"_id": form_id},
                {"$set": update_doc}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Form not found")

            return {"message": "Form updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error updating form: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update form: {str(e)}")

    async def delete_form(self, form_id: str, created_by: str, is_root_admin: bool = False) -> Dict[str, Any]:
        """Soft delete a form"""
        try:
            logger.info(f"delete_form called: form_id={form_id}, created_by={created_by}, is_root_admin={is_root_admin}")
            # ROOT_ADMIN can delete any form, others can only delete their own
            if is_root_admin:
                query = {"_id": form_id}
                logger.info(f"Using ROOT_ADMIN query: {query}")
            else:
                query = {"_id": form_id, "created_by": created_by}
                logger.info(f"Using regular user query: {query}")
            # First, check if form exists
            existing_form = await self.forms_collection.find_one({"_id": form_id})
            logger.info(f"Form exists check: {existing_form is not None}")
            if existing_form:
                logger.info(f"Form details: _id={existing_form.get('_id')}, created_by={existing_form.get('created_by')}, is_active={existing_form.get('is_active')}")
            result = await self.forms_collection.update_one(
                query,
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            logger.info(f"Update result: matched_count={result.matched_count}, modified_count={result.modified_count}")

            if result.matched_count == 0:
                logger.warning(f"No form matched for deletion: form_id={form_id}, query={query}")
                raise HTTPException(status_code=404, detail="Form not found")

            logger.info(f"Form {form_id} deleted successfully")
            return {"message": "Form deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting form: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to delete form: {str(e)}")

    async def send_form(self, form_id: str, send_data: SendFormRequest, created_by: str) -> Dict[str, Any]:
        """Send form to recipients via email"""
        try:
            # Get form
            form = await self.get_form(form_id, created_by)

            # Generate form URL
            frontend_url = os.getenv("FRONTEND_URL")
            if not frontend_url:
                raise ValueError("FRONTEND_URL environment variable is required")
            form_url = f"{frontend_url}/forms/{form_id}"

            sent_count = 0
            failed_count = 0

            for recipient_email in send_data.recipient_emails:
                try:
                    # Create distribution record
                    distribution_id = str(uuid.uuid4())
                    distribution_doc = {
                        "_id": distribution_id,
                        "form_id": form_id,
                        "recipient_email": recipient_email,
                        "wedding_id": send_data.wedding_id,
                        "sent_at": datetime.utcnow(),
                        "status": "sending"
                    }

                    # Generate personalized email content
                    email_html = self._generate_form_email_html(
                        form_title=form["settings"]["title"],
                        form_description=form["settings"].get("description", ""),
                        form_url=form_url,
                        sender_name=send_data.email_settings.sender_name,
                        custom_message=send_data.email_settings.message
                    )

                    # Send email
                    if self.email_service.configured:
                        email_result = await self.email_service.send_email(
                            to_email=recipient_email,
                            subject=send_data.email_settings.subject,
                            html_content=email_html,
                            from_name=send_data.email_settings.sender_name
                        )

                        if email_result.get("success"):
                            distribution_doc["status"] = "sent"
                            distribution_doc["email_id"] = email_result.get("email_id")
                            sent_count += 1
                        else:
                            distribution_doc["status"] = "failed"
                            failed_count += 1
                    else:
                        distribution_doc["status"] = "failed"
                        failed_count += 1

                    # Save distribution record
                    await self.distributions_collection.insert_one(distribution_doc)

                except Exception as email_error:
                    logging.error(f"Failed to send form to {recipient_email}: {str(email_error)}")
                    failed_count += 1

            return {
                "sent": sent_count,
                "failed": failed_count,
                "form_url": form_url,
                "message": f"Form sent to {sent_count} recipients"
            }

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error sending form: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to send form: {str(e)}")

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
            if not rate_limiter.check_rate_limit(rate_key, limit=100, window_seconds=3600):
                raise HTTPException(
                    status_code=429,
                    detail="Too many form submissions. Please try again later."
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
                raise HTTPException(status_code=400, detail="Form is no longer accepting responses")

            # Validate and sanitize response data
            try:
                sanitized_responses = FormSecurityValidator.validate_form_response(
                    response_data.responses, form["fields"]
                )
            except ValueError as e:
                logger.warning(f"Invalid form response for form {form_id}: {str(e)}")
                raise HTTPException(status_code=400, detail="Invalid response data")

            # Validate required fields
            for field in form["fields"]:
                if field["required"] and field["id"] not in sanitized_responses:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Required field '{html.escape(field['label'])}' is missing"
                    )

            # Sanitize submitter information
            submitted_by_email = None
            submitted_by_name = None

            if response_data.submitted_by_email:
                if InputSanitizer.validate_email(response_data.submitted_by_email):
                    submitted_by_email = response_data.submitted_by_email.lower().strip()
                else:
                    raise HTTPException(status_code=400, detail="Invalid email address")

            if response_data.submitted_by_name:
                submitted_by_name = InputSanitizer.sanitize_text(
                    response_data.submitted_by_name, 100
                )

            # Check if multiple submissions are allowed
            if not form["settings"].get("allow_multiple_submissions", False):
                if submitted_by_email:
                    existing_response = await self.responses_collection.find_one({
                        "form_id": form_id,
                        "submitted_by_email": submitted_by_email
                    })
                    if existing_response:
                        raise HTTPException(
                            status_code=400,
                            detail="You have already submitted a response to this form"
                        )

            # Create response document with sanitized data
            response_id = str(uuid.uuid4())

            # Sanitize IP address and user agent
            safe_ip = InputSanitizer.sanitize_text(ip_address, 45) if ip_address else None
            safe_user_agent = InputSanitizer.sanitize_text(user_agent, 500) if user_agent else None

            response_doc = {
                "_id": response_id,
                "form_id": form_id,
                "responses": sanitized_responses,
                "submitted_by_email": submitted_by_email,
                "submitted_by_name": submitted_by_name,
                "wedding_id": form.get("wedding_id"),
                "ip_address": safe_ip,
                "user_agent": safe_user_agent,
                "submitted_at": datetime.utcnow(),
                "metadata": {
                    "security_validated": True,
                    "sanitized_at": datetime.utcnow()
                }
            }

            # Save response
            result = await self.responses_collection.insert_one(response_doc)

            if result.inserted_id:
                # Update form submission count
                await self.forms_collection.update_one(
                    {"_id": form_id},
                    {
                        "$inc": {"submission_count": 1},
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                )

                # Update distribution status if applicable
                if submitted_by_email:
                    await self.distributions_collection.update_one(
                        {"form_id": form_id, "recipient_email": submitted_by_email},
                        {"$set": {"submitted_at": datetime.utcnow(), "status": "submitted"}}
                    )

                # Log successful submission for security monitoring
                logger.info(
                    f"Form submission successful: form_id={form_id}, "
                    f"email={submitted_by_email}, ip={safe_ip}"
                )

                # Notify planner about the form submission
                await self._notify_planner_form_submission(
                    form=form,
                    submitter_name=submitted_by_name or submitted_by_email or "Anonymous",
                    form_id=form_id
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
                    "redirect_url": safe_redirect_url
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to save response")

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error submitting form response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to submit response: {str(e)}")

    async def get_form_responses(self, form_id: str, created_by: str) -> List[Dict[str, Any]]:
        """Get all responses for a form"""
        try:
            # Verify user owns the form
            await self.get_form(form_id, created_by)

            responses = await self.responses_collection.find(
                {"form_id": form_id}
            ).sort("submitted_at", -1).to_list(length=None)

            # Format responses
            for response in responses:
                response["id"] = response["_id"]
                response.pop("_id", None)

            return responses

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching form responses: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch responses: {str(e)}")

    async def mark_form_viewed(
        self,
        form_id: str,
        viewer_email: str,
        scope: str,
        submission_count: Optional[int] = None,
        *,
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

        base_projection = {"planner_state": 1, "submission_count": 1, "is_active": 1, "created_by": 1}
        if is_root_admin:
            form = await self.forms_collection.find_one({"_id": sanitized_form_id}, base_projection)
        else:
            form = await self.forms_collection.find_one(
                {"_id": sanitized_form_id, "is_active": True, "created_by": normalized_email},
                base_projection,
            )

        if not form:
            if not is_root_admin:
                # Differentiate between unauthorized access and missing forms for clearer errors
                exists = await self.forms_collection.find_one({"_id": sanitized_form_id}, {"_id": 1})
                if exists:
                    raise HTTPException(status_code=403, detail="Access denied to form")
            raise HTTPException(status_code=404, detail="Form not found")

        if not form.get("is_active", True) and not is_root_admin:
            raise HTTPException(status_code=404, detail="Form not found")

        now = datetime.utcnow()
        update_fields: Dict[str, Any] = {}

        total_submissions = int(form.get("submission_count", 0) or 0)
        planner_state = form.get("planner_state", {}) or {}
        existing_state = planner_state.get(state_key) or planner_state.get(normalized_email) or {}
        unread_after_update = max(total_submissions - int(existing_state.get("last_viewed_submission_count", 0) or 0), 0)

        if scope == "responses":
            latest_known = submission_count
            if latest_known is None:
                latest_known = total_submissions

            latest_int = max(int(latest_known or 0), 0)
            update_fields[f"planner_state.{state_key}.last_viewed_submission_count"] = latest_int
            update_fields[f"planner_state.{state_key}.last_viewed_responses_at"] = now
            unread_after_update = max(total_submissions - latest_int, 0)

        if scope == "analytics":
            update_fields[f"planner_state.{state_key}.last_viewed_analytics_at"] = now

        await self.forms_collection.update_one({"_id": sanitized_form_id}, {"$set": update_fields}, upsert=False)

        return {
            "message": "Form view recorded",
            "unread_responses": unread_after_update,
        }

    async def get_form_analytics(self, form_id: str, created_by: str) -> Dict[str, Any]:
        """Get analytics for a form"""
        try:
            # Verify user owns the form
            form = await self.get_form(form_id, created_by)

            # Get response count
            response_count = await self.responses_collection.count_documents({"form_id": form_id})

            # Get distribution stats
            distributions = await self.distributions_collection.find({"form_id": form_id}).to_list(length=None)
            sent_count = len(distributions)
            opened_count = len([d for d in distributions if d.get("opened_at")])
            clicked_count = len([d for d in distributions if d.get("clicked_at")])
            submitted_count = len([d for d in distributions if d.get("submitted_at")])

            # Calculate rates
            open_rate = round((opened_count / sent_count * 100) if sent_count > 0 else 0, 1)
            click_rate = round((clicked_count / sent_count * 100) if sent_count > 0 else 0, 1)
            completion_rate = round((submitted_count / sent_count * 100) if sent_count > 0 else 0, 1)

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
                    "completion_rate": completion_rate
                },
                "created_at": form["created_at"],
                "last_response": await self._get_last_response_time(form_id)
            }

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching form analytics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")

    async def _get_last_response_time(self, form_id: str):
        """Get the timestamp of the most recent form response"""
        try:
            last_response = await self.responses_collection.find_one(
                {"form_id": form_id},
                sort=[("submitted_at", -1)]
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
                        {f'<p>{form_description}</p>' if form_description else ''}
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
        include_metadata: bool = True
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
                f"csv_export_{created_by}",
                limit=5,
                window_seconds=3600
            ):
                raise HTTPException(
                    status_code=429,
                    detail="Too many CSV exports requested. Please try again later."
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
            form = await self.get_form(form_id, created_by)
            if not form:
                raise HTTPException(status_code=404, detail="Form not found")

            # Get all responses for the form
            responses = await self.get_form_responses(form_id, created_by)

            # Validate date parameters
            parsed_date_from = None
            parsed_date_to = None

            if date_from:
                try:
                    # Support various date formats
                    date_from = InputSanitizer.sanitize_text(date_from, 50)
                    parsed_date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid date_from parameter: {date_from}")
                    raise HTTPException(status_code=400, detail="Invalid date_from format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")

            if date_to:
                try:
                    date_to = InputSanitizer.sanitize_text(date_to, 50)
                    parsed_date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid date_to parameter: {date_to}")
                    raise HTTPException(status_code=400, detail="Invalid date_to format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")

            # Validate date range
            if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
                raise HTTPException(status_code=400, detail="date_from cannot be after date_to")

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
            if len(responses) > max_export_size:
                logger.warning(
                    f"Export size limited: {len(responses)} responses truncated to {max_export_size}"
                )
                responses = responses[:max_export_size]

            # Prepare export options
            export_options = {
                'include_metadata': include_metadata,
                'date_from': parsed_date_from,
                'date_to': parsed_date_to,
                'max_responses': max_export_size
            }

            # Use the CSV exporter utility
            csv_exporter = FormResponseCSVExporter()
            export_result = csv_exporter.export_responses(
                form_data=form,
                responses=responses,
                options=export_options
            )

            # Add additional metadata
            export_result.update({
                'form_id': form_id,
                'form_name': form.get('name', 'Unknown Form'),
                'exported_by': created_by,
                'request_params': {
                    'date_from': date_from,
                    'date_to': date_to,
                    'include_metadata': include_metadata
                }
            })

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
                detail="Failed to export form responses. Please try again later."
            )

    async def _notify_planner_form_submission(
        self,
        form: Dict[str, Any],
        submitter_name: str,
        form_id: str
    ):
        """Notify the planner about a form submission"""
        try:
            wedding_id = form.get("wedding_id")
            form_title = form.get("settings", {}).get("title", form.get("name", "Unknown Form"))

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
            from app.services.planner_notification_service import planner_notification_service

            await planner_notification_service.notify_form_submission(
                planner_id=planner_email,
                wedding_id=wedding_id or "",
                form_type=form_title,
                submitter_name=submitter_name,
                form_id=form_id
            )
            logger.info(f"Form submission notification sent to {planner_email}")

        except Exception as e:
            # Don't fail the form submission if notification fails
            logger.error(f"Failed to send form submission notification: {str(e)}")
