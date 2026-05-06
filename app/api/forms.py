import html
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel, EmailStr, Field
from typing_extensions import TypedDict

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    require_team_or_planner,
)
from app.models.form import (
    CreateFormRequest,
    DuplicateFormRequest,
    FormField,
    FormSettings,
    FormViewUpdateRequest,
    SendFormRequest,
    SubmitFormRequest,
    UpdateFormRequest,
)
from app.services.form_service import FormService
from app.services.form_template_catalog import FORM_TEMPLATES as _CATALOG_TEMPLATES
from app.services.form_upload_service import (
    MAX_UPLOAD_BYTES,
    FormUploadService,
)
from app.services.security_audit_service import (
    SecurityEventType,
    SecuritySeverity,
    security_audit,
)
from app.utils.planner_ownership import build_team_owner_query, normalize_planner_email
from app.utils.security_utils import InputSanitizer, SecurityHeaders, rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter()
form_service = FormService()
form_upload_service = FormUploadService()


class FormOwnerScope(TypedDict):
    owner_email: str
    owner_alias_emails: list[str]


class FormTemplateFieldDataRequired(TypedDict):
    id: str
    label: str
    type: str
    required: bool
    order: int


class FormTemplateFieldData(FormTemplateFieldDataRequired, total=False):
    description: str
    placeholder: str
    options: list[str]


class FormTemplateDefinition(TypedDict):
    id: str
    name: str
    description: str
    category: str
    fields: list[FormTemplateFieldData]


class FormTemplateResponse(TypedDict):
    templates: list[FormTemplateDefinition]


async def _resolve_form_owner_scope(
    current_user: ExtendedAuthUser,
) -> FormOwnerScope:
    """Resolve shared planner ownership for forms while preserving legacy team-created records."""
    owner_email = normalize_planner_email(
        current_user.team_owner_email
        if current_user.is_team_member
        else current_user.email
    )
    owner_alias_emails = {
        email
        for email in (
            owner_email,
            normalize_planner_email(current_user.email),
        )
        if email
    }

    owner_id = (
        current_user.parent_planner_id
        if current_user.is_team_member
        else current_user.user_data.get("_id")
    )
    team_query = build_team_owner_query(owner_id, owner_email)
    if team_query:
        team_members = (
            await form_service.forms_collection.database["team_members"]
            .find(
                team_query,
                {"email": 1},
            )
            .to_list(length=None)
        )
        for member in team_members:
            normalized_member_email = normalize_planner_email(member.get("email"))
            if normalized_member_email:
                owner_alias_emails.add(normalized_member_email)

    return {
        "owner_email": owner_email or current_user.email.lower().strip(),
        "owner_alias_emails": sorted(owner_alias_emails),
    }


# Admin endpoints (require authentication)
@router.post("/forms", tags=["Forms"])
async def create_form(
    form_data: CreateFormRequest,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Create a new form with enhanced security validation"""
    enforce_team_permission(current_user, "manage_forms")

    # Validate wedding access if wedding_id is provided
    if form_data.wedding_id:
        if not await check_wedding_access(current_user, form_data.wedding_id):
            logger.warning(
                f"User {current_user.email} attempted to create form for "
                f"wedding {form_data.wedding_id} without access"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied. You don't have access to this wedding.",
            )

    # Log form creation attempt
    client_ip = getattr(request.client, "host", None) if request.client else None
    logger.info(
        f"Form creation attempt: user={current_user.email}, "
        f"ip={client_ip}, wedding_id={form_data.wedding_id}"
    )

    try:
        owner_scope = await _resolve_form_owner_scope(current_user)
        result = await form_service.create_form(
            form_data,
            owner_scope["owner_email"],
            actor_email=current_user.email,
        )

        # Log successful creation
        logger.info(
            f"Form created successfully: id={result.get('id')}, "
            f"user={current_user.email}"
        )
        # Security audit log
        await security_audit.log_security_event(
            event_type=SecurityEventType.FORM_CREATION,
            severity=SecuritySeverity.MEDIUM,
            user_email=current_user.email,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            resource="forms",
            action="create",
            details={
                "form_id": result.get("id"),
                "wedding_id": form_data.wedding_id,
                "form_name": form_data.name,
                "field_count": len(form_data.fields),
            },
            success=True,
            form_id=result.get("id"),
            wedding_id=form_data.wedding_id,
        )

        return result

    except Exception as e:
        logger.error(f"Form creation failed: user={current_user.email}, error={str(e)}")
        raise


@router.get("/forms", tags=["Forms"])
async def get_forms(
    wedding_id: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Get all forms for the current user with security validation"""

    # Validate wedding_id if provided
    if wedding_id:
        # Sanitize wedding_id
        wedding_id = InputSanitizer.sanitize_text(wedding_id, 100)
        # Check wedding access
        if not await check_wedding_access(current_user, wedding_id):
            logger.warning(
                f"User {current_user.email} attempted to access forms for "
                f"wedding {wedding_id} without access"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied. You don't have access to this wedding.",
            )

    try:
        owner_scope = await _resolve_form_owner_scope(current_user)
        forms = await form_service.get_forms(
            owner_scope["owner_email"],
            wedding_id,
            current_user.is_root_admin,
            viewer_email=current_user.email,
            owner_alias_emails=owner_scope["owner_alias_emails"],
        )

        # Log access
        logger.info(
            f"Forms accessed: user={current_user.email}, "
            f"wedding_id={wedding_id}, count={len(forms)}"
        )

        return forms

    except Exception as e:
        logger.error(
            f"Forms access failed: user={current_user.email}, "
            f"wedding_id={wedding_id}, error={str(e)}"
        )
        raise


@router.get("/forms/{form_id}", tags=["Forms"])
async def get_form(
    form_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Get a specific form with authorization validation"""

    # Validate form_id
    if not form_id or not isinstance(form_id, str):
        raise HTTPException(status_code=400, detail="Invalid form ID")

    form_id = InputSanitizer.sanitize_text(form_id, 100)
    if not form_id:
        raise HTTPException(status_code=400, detail="Invalid form ID")

    try:
        owner_scope = await _resolve_form_owner_scope(current_user)
        form = await form_service.get_form(
            form_id,
            owner_scope["owner_email"],
            owner_alias_emails=owner_scope["owner_alias_emails"],
        )

        # Additional wedding access check if form has wedding_id
        if form.get("wedding_id") and not await check_wedding_access(
            current_user, form["wedding_id"]
        ):
            logger.warning(
                f"User {current_user.email} attempted to access form {form_id} "
                f"for wedding {form['wedding_id']} without access"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied. You don't have access to this wedding.",
            )

        # Log access
        logger.info(f"Form accessed: id={form_id}, user={current_user.email}")

        return form

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Form access failed: id={form_id}, user={current_user.email}, "
            f"error={str(e)}"
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve form")


@router.put("/forms/{form_id}", tags=["Forms"])
async def update_form(
    form_id: str,
    form_data: UpdateFormRequest,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Update a form with enhanced security validation"""
    enforce_team_permission(current_user, "manage_forms")

    # Validate form_id
    if not form_id or not isinstance(form_id, str):
        raise HTTPException(status_code=400, detail="Invalid form ID")

    form_id = InputSanitizer.sanitize_text(form_id, 100)
    if not form_id:
        raise HTTPException(status_code=400, detail="Invalid form ID")

    # Get existing form to check wedding access
    try:
        owner_scope = await _resolve_form_owner_scope(current_user)
        existing_form = await form_service.get_form(
            form_id,
            owner_scope["owner_email"],
            owner_alias_emails=owner_scope["owner_alias_emails"],
        )

        # Check wedding access if form has wedding_id
        if existing_form.get("wedding_id"):
            if not await check_wedding_access(
                current_user, existing_form["wedding_id"]
            ):
                logger.warning(
                    f"User {current_user.email} attempted to update form {form_id} "
                    f"for wedding {existing_form['wedding_id']} without access"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You don't have access to this wedding.",
                )

        # Log update attempt
        client_ip = getattr(request.client, "host", None) if request.client else None
        logger.info(
            f"Form update attempt: id={form_id}, user={current_user.email}, "
            f"ip={client_ip}"
        )

        result = await form_service.update_form(
            form_id,
            form_data,
            owner_scope["owner_email"],
            owner_alias_emails=owner_scope["owner_alias_emails"],
        )

        # Log successful update
        logger.info(
            f"Form updated successfully: id={form_id}, user={current_user.email}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Form update failed: id={form_id}, user={current_user.email}, "
            f"error={str(e)}"
        )
        raise HTTPException(status_code=500, detail="Failed to update form")


@router.delete("/forms/{form_id}", tags=["Forms"])
async def delete_form(
    form_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Delete a form with enhanced security validation"""
    logger.info(
        f"DELETE /forms/{form_id} called by {current_user.email}, is_root_admin={current_user.is_root_admin}"
    )
    enforce_team_permission(current_user, "manage_forms")

    # Validate form_id
    if not form_id or not isinstance(form_id, str):
        logger.error(f"Invalid form_id type: {type(form_id)}, value: {form_id}")
        raise HTTPException(status_code=400, detail="Invalid form ID")
    form_id = InputSanitizer.sanitize_text(form_id, 100)
    if not form_id:
        logger.error("Form ID sanitization failed")
        raise HTTPException(status_code=400, detail="Invalid form ID")

    logger.info(f"Form ID after sanitization: {form_id}")

    try:
        owner_scope = await _resolve_form_owner_scope(current_user)
        logger.info("About to get existing form for access check...")

        # For ROOT_ADMIN, get form without created_by constraint
        if current_user.is_root_admin:
            existing_form = await form_service.get_form(
                form_id
            )  # No created_by for ROOT_ADMIN
            logger.info("ROOT_ADMIN form retrieval successful")
        else:
            existing_form = await form_service.get_form(
                form_id,
                owner_scope["owner_email"],
                owner_alias_emails=owner_scope["owner_alias_emails"],
            )
            logger.info("Regular user form retrieval successful")
        # Check wedding access if form has wedding_id
        if existing_form.get("wedding_id"):
            logger.info(
                f"Checking wedding access for wedding_id: {existing_form['wedding_id']}"
            )
            if not await check_wedding_access(
                current_user, existing_form["wedding_id"]
            ):
                logger.warning(
                    f"User {current_user.email} attempted to delete form {form_id} "
                    f"for wedding {existing_form['wedding_id']} without access"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You don't have access to this wedding.",
                )

        # Log deletion attempt
        client_ip: str = (
            getattr(request.client, "host", "unknown") if request.client else "unknown"
        )
        logger.warning(
            f"Form deletion attempt: id={form_id}, user={current_user.email}, "
            f"ip={client_ip}"
        )

        logger.info("About to call form_service.delete_form...")
        result = await form_service.delete_form(
            form_id,
            owner_scope["owner_email"],
            current_user.is_root_admin,
            owner_alias_emails=owner_scope["owner_alias_emails"],
        )

        # Log successful deletion
        logger.warning(f"Form deleted: id={form_id}, user={current_user.email}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Form deletion failed: id={form_id}, user={current_user.email}, "
            f"error={str(e)}"
        )
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to delete form")


@router.post("/forms/{form_id}/send", tags=["Forms"])
async def send_form(
    form_id: str,
    send_data: SendFormRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Send form to recipients via email"""
    enforce_team_permission(current_user, "manage_forms")
    owner_scope = await _resolve_form_owner_scope(current_user)
    return await form_service.send_form(
        form_id,
        send_data,
        owner_scope["owner_email"],
        owner_alias_emails=owner_scope["owner_alias_emails"],
    )


@router.get("/forms/{form_id}/responses", tags=["Forms"])
async def get_form_responses(
    form_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
    skip: int = Query(
        0,
        ge=0,
        description="Number of responses to skip (offset for pagination)",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
        description="Page size (max 500). Default 100.",
    ),
):
    """Get a page of form responses with total count.

    Returns ``{items, total, skip, limit, has_more}``. Pagination is
    required: a form with 50,000 responses would otherwise OOM the API
    if loaded into a single response.
    """
    owner_scope = await _resolve_form_owner_scope(current_user)
    return await form_service.get_form_responses(
        form_id,
        owner_scope["owner_email"],
        owner_alias_emails=owner_scope["owner_alias_emails"],
        skip=skip,
        limit=limit,
    )


@router.get("/forms/{form_id}/distributions", tags=["Forms"])
async def get_form_distributions(
    form_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
    status: Optional[str] = Query(
        None,
        description="Filter by distribution status: sent, opened, clicked, submitted, failed",
    ),
):
    """List distribution rows for a form (the join key for 'who has not responded')."""
    owner_scope = await _resolve_form_owner_scope(current_user)
    return await form_service.get_form_distributions(
        form_id,
        owner_scope["owner_email"],
        owner_alias_emails=owner_scope["owner_alias_emails"],
        status=status,
    )


@router.post("/forms/{form_id}/views", tags=["Forms"])
async def mark_form_view(
    form_id: str,
    payload: FormViewUpdateRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Update the planner's last viewed timestamp for a form scope."""
    enforce_team_permission(current_user, "manage_forms")
    owner_scope = await _resolve_form_owner_scope(current_user)

    return await form_service.mark_form_viewed(
        form_id,
        current_user.email,
        payload.scope,
        submission_count=payload.submission_count,
        owner_alias_emails=owner_scope["owner_alias_emails"],
        is_root_admin=current_user.is_root_admin,
    )


@router.get("/forms/{form_id}/analytics", tags=["Forms"])
async def get_form_analytics(
    form_id: str, current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Get analytics for a form"""
    owner_scope = await _resolve_form_owner_scope(current_user)
    return await form_service.get_form_analytics(
        form_id,
        owner_scope["owner_email"],
        owner_alias_emails=owner_scope["owner_alias_emails"],
    )


@router.get("/forms/{form_id}/export/csv", tags=["Forms"])
async def export_form_responses_csv(
    form_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
    date_from: Optional[str] = Query(
        None,
        description="Start date filter (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    ),
    date_to: Optional[str] = Query(
        None,
        description="End date filter (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    ),
    include_metadata: bool = Query(
        True, description="Include submission metadata (date, IP, etc.)"
    ),
):
    """
    Export form responses to CSV format with enhanced security and filtering.

    This endpoint allows authorized users to export form responses as CSV files
    with comprehensive security measures and filtering options.

    Features:
    - Role-based access control (wedding planners and root admins only)
    - Wedding assignment validation (planners can only export their forms)
    - Rate limiting (5 exports per hour per user)
    - Data sanitization and CSV injection protection
    - Optional date range filtering
    - Configurable metadata inclusion
    - Audit logging for security monitoring
    Args:
        form_id: The ID of the form to export responses for
        date_from: Optional start date for filtering responses (ISO format)
        date_to: Optional end date for filtering responses (ISO format)
        include_metadata: Whether to include submission metadata columns

    Returns:
        CSV file download with form responses

    Raises:
        403: Access denied (insufficient permissions or wedding access)
        404: Form not found
        400: Invalid parameters (malformed dates, invalid form ID)
        429: Rate limit exceeded (too many exports)
        500: Server error during export processing
    """
    try:
        enforce_team_permission(current_user, "manage_forms")
        owner_scope = await _resolve_form_owner_scope(current_user)

        # Validate form_id format
        if not form_id or not isinstance(form_id, str):
            raise HTTPException(status_code=400, detail="Invalid form ID")

        form_id = InputSanitizer.sanitize_text(form_id, 100)
        if not form_id:
            raise HTTPException(status_code=400, detail="Invalid form ID")

        # Get form to check wedding access before export
        try:
            form = await form_service.get_form(
                form_id,
                owner_scope["owner_email"],
                owner_alias_emails=owner_scope["owner_alias_emails"],
            )

            # Additional wedding access check if form has wedding_id
            if form.get("wedding_id") and not await check_wedding_access(
                current_user, form["wedding_id"]
            ):
                logger.warning(
                    f"User {current_user.email} attempted to export CSV for form {form_id} "
                    f"for wedding {form['wedding_id']} without access"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. You don't have access to this wedding's forms.",
                )
        except HTTPException as e:
            if e.status_code == 404:
                logger.info(
                    f"CSV export attempted for non-existent form {form_id} by {current_user.email}"
                )
            raise
        # Log CSV export attempt for security audit
        client_ip: str = (
            getattr(request.client, "host", "unknown") if request.client else "unknown"
        )
        logger.info(
            f"CSV export attempt: form_id={form_id}, user={current_user.email}, "
            f"ip={client_ip}, date_from={date_from}, date_to={date_to}, "
            f"include_metadata={include_metadata}"
        )
        # Call the form service to generate CSV
        export_result = await form_service.export_form_responses_csv(
            form_id=form_id,
            created_by=current_user.email,
            date_from=date_from,
            date_to=date_to,
            include_metadata=include_metadata,
            owner_alias_emails=owner_scope["owner_alias_emails"],
            exported_by=current_user.email,
        )
        # Log successful export for audit
        await security_audit.log_security_event(
            event_type=SecurityEventType.DATA_EXPORT,
            severity=SecuritySeverity.MEDIUM,
            user_email=current_user.email,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            resource="forms",
            action="csv_export",
            details={
                "form_id": form_id,
                "form_name": export_result.get("form_name"),
                "exported_count": export_result.get("exported_count", 0),
                "file_size": export_result.get("size", 0),
                "filters": {
                    "date_from": date_from,
                    "date_to": date_to,
                    "include_metadata": include_metadata,
                },
            },
            success=True,
            form_id=form_id,
            wedding_id=form.get("wedding_id"),
        )
        logger.info(
            f"CSV export successful: form_id={form_id}, user={current_user.email}, "
            f"exported_count={export_result.get('exported_count', 0)}, "
            f"file_size={export_result.get('size', 0)} bytes"
        )
        # Return CSV file as download. X-Total-Count / X-Truncated /
        # X-Truncated-Count headers let the frontend show an honest
        # "Exported 10,000 of 47,832 — 37,832 omitted" banner instead of
        # silently shipping a partial dataset.
        truncated = bool(export_result.get("truncated"))
        truncated_count = int(export_result.get("truncated_count") or 0)
        total_count = int(export_result.get("total_response_count") or 0)
        max_export_size = int(export_result.get("max_export_size") or 0)
        return FastAPIResponse(
            content=export_result["content"],
            media_type=export_result["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{export_result["filename"]}"',
                "Content-Length": str(export_result["size"]),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Total-Count": str(total_count),
                "X-Truncated": "true" if truncated else "false",
                "X-Truncated-Count": str(truncated_count),
                "X-Max-Export-Size": str(max_export_size),
                # Browsers strip non-CORS-allowed headers from
                # cross-origin reads; planners UI shares the same origin
                # in production, but expose these explicitly to be safe.
                "Access-Control-Expose-Headers": (
                    "Content-Disposition,X-Total-Count,X-Truncated,"
                    "X-Truncated-Count,X-Max-Export-Size"
                ),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"CSV export failed: form_id={form_id}, user={current_user.email}, "
            f"error={str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to export form responses. Please try again later.",
        )


# Public endpoints (no authentication required) - Enhanced security
@router.get("/public/forms/{form_id}", tags=["Public Forms"])
async def get_public_form(form_id: str, request: Request, response: Response):
    """Get a form for public submission with security validation"""
    try:
        # Rate limiting for public form access
        client_ip = (
            getattr(request.client, "host", None) if request.client else "unknown"
        )
        if not rate_limiter.check_rate_limit(
            f"public_form_access_{client_ip}", limit=50, window_seconds=3600
        ):
            logger.warning(
                f"Rate limit exceeded for public form access from IP: {client_ip}"
            )
            raise HTTPException(
                status_code=429, detail="Too many requests. Please try again later."
            )

        # Validate form_id
        if not form_id or not isinstance(form_id, str):
            logger.warning(
                f"Invalid form ID in public access: {form_id} from IP: {client_ip}"
            )
            raise HTTPException(status_code=400, detail="Invalid form ID")

        form_id = InputSanitizer.sanitize_text(form_id, 100)
        if not form_id:
            raise HTTPException(status_code=400, detail="Invalid form ID")

        # Get form with public access (no creator email)
        form = await form_service.get_form(form_id)

        # Verify form is public
        if not form.get("settings", {}).get("is_public", False):
            logger.warning(
                f"Attempt to access non-public form {form_id} from IP: {client_ip}"
            )
            raise HTTPException(
                status_code=403, detail="Form is not publicly accessible"
            )
        # Only return necessary fields for public access with sanitization
        public_form = {
            "id": form["id"],
            "settings": {
                "title": html.escape(form["settings"].get("title", "")),
                "description": html.escape(form["settings"].get("description", "")),
                "submit_button_text": html.escape(
                    form["settings"].get("submit_button_text", "Submit")
                ),
                "collect_email": form["settings"].get("collect_email", True),
                "allow_multiple_submissions": form["settings"].get(
                    "allow_multiple_submissions", False
                ),
            },
            "fields": [
                {
                    "id": field["id"],
                    "label": html.escape(field.get("label", "")),
                    "type": field["type"],
                    "placeholder": html.escape(field.get("placeholder", "")),
                    "required": field.get("required", False),
                    "description": html.escape(field.get("description", "")),
                    "options": [html.escape(opt) for opt in field.get("options", [])],
                    "order": field.get("order", 0),
                    # conditional_logic powers the hide/show evaluator on the
                    # client. Field IDs/operators in this object reference
                    # other field IDs already exposed in this same payload.
                    "conditional_logic": field.get("conditional_logic"),
                }
                for field in form["fields"]
            ],
            "is_active": form["is_active"],
        }

        # Add security headers
        for (
            header_name,
            header_value,
        ) in SecurityHeaders.get_form_security_headers().items():
            response.headers[header_name] = header_value

        # Log public access
        logger.info(f"Public form accessed: id={form_id}, ip={client_ip}")

        return public_form

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching public form {form_id}: {str(e)}")
        raise HTTPException(status_code=404, detail="Form not found")


@router.get(
    "/public/forms/{form_id}/distributions/{distribution_id}/check",
    tags=["Public Forms"],
)
async def check_public_form_distribution_link(
    form_id: str,
    distribution_id: str,
    request: Request,
    t: str = Query(..., description="Per-recipient access token from the email link"),
):
    """Validate a per-recipient form link before the page renders the form.

    Returns ``{valid, expired, already_submitted, recipient_name, ...}`` for
    a known good link and 404 for any wrong/forged token to avoid leaking
    distribution data to enumeration attempts.
    """
    client_ip = getattr(request.client, "host", None) if request.client else "unknown"
    if not rate_limiter.check_rate_limit(
        f"public_form_link_check_{client_ip}", limit=120, window_seconds=3600
    ):
        raise HTTPException(
            status_code=429, detail="Too many requests. Please try again later."
        )

    return await form_service.check_form_distribution_link(
        form_id=InputSanitizer.sanitize_text(form_id, 100),
        distribution_id=InputSanitizer.sanitize_text(distribution_id, 64),
        access_token=t,
    )


@router.post(
    "/public/forms/{form_id}/uploads",
    tags=["Public Forms"],
)
async def upload_public_form_file(
    form_id: str,
    request: Request,
    distribution_id: str = Form(
        ..., description="FormDistribution ID from the email link"
    ),
    access_token: str = Form(..., description="Per-recipient access token"),
    field_id: str = Form(
        ..., description="ID of the FILE_UPLOAD field this attachment belongs to"
    ),
    upload: UploadFile = File(..., description="The file to upload"),
):
    """Upload a single file for a FILE_UPLOAD field on a public form.

    Requires the same ``(distribution_id, access_token)`` pair used by
    submission — anonymous uploads are not accepted, by design, to keep
    the public bucket from becoming a free-for-all. Size capped at
    10 MB; allowed MIME types are images, PDFs, and common doc formats.
    """
    client_ip = getattr(request.client, "host", None) if request.client else "unknown"
    if not rate_limiter.check_rate_limit(
        f"public_form_upload_{client_ip}", limit=30, window_seconds=3600
    ):
        raise HTTPException(
            status_code=429, detail="Too many uploads. Please try again later."
        )

    safe_form_id = InputSanitizer.sanitize_text(form_id, 100)
    safe_distribution_id = InputSanitizer.sanitize_text(distribution_id, 64)
    safe_field_id = InputSanitizer.sanitize_text(field_id, 64)

    # Token check (returns 404 on bad token, 410 on expired etc).
    link_state = await form_service.check_form_distribution_link(
        form_id=safe_form_id,
        distribution_id=safe_distribution_id,
        access_token=access_token,
    )
    if not link_state.get("valid"):
        # Already submitted / expired — no new uploads allowed.
        raise HTTPException(
            status_code=409,
            detail="This form access link is no longer accepting uploads",
        )

    # Re-fetch form + distribution for the upload service.
    form = await form_service.get_form(safe_form_id)
    distribution = await form_service.distributions_collection.find_one(
        {"_id": safe_distribution_id, "form_id": safe_form_id}
    )
    if not distribution:
        raise HTTPException(status_code=404, detail="Distribution not found")

    contents = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    return await form_upload_service.store_upload(
        form=form,
        distribution=distribution,
        field_id=safe_field_id,
        filename=upload.filename,
        content_type=upload.content_type,
        contents=contents,
    )


@router.get(
    "/public/form-templates/{template_id}/preview.pdf",
    tags=["Public Forms"],
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Template not found"},
        429: {"description": "Rate limited"},
        503: {"description": "PDF rendering not available"},
    },
)
async def preview_form_template_pdf(
    template_id: str,
    request: Request,
):
    """Public, unauthenticated PDF preview of a catalog template.

    Powers the marketing surface ("Free Wedding Planner Templates")
    and serves as the upstream renderer for in-app previews. Rate-
    limited (60/hour/IP) and rendered off the event loop via
    ``asyncio.to_thread`` so a 200–500 ms WeasyPrint pass cannot block
    other requests. Output is cached in-memory by template id, so
    repeat requests return without re-rendering.
    """
    import asyncio

    client_ip = getattr(request.client, "host", None) if request.client else "unknown"
    if not rate_limiter.check_rate_limit(
        f"public_template_pdf_{client_ip}", limit=60, window_seconds=3600
    ):
        raise HTTPException(
            status_code=429, detail="Too many requests. Please try again later."
        )

    safe_template_id = InputSanitizer.sanitize_text(template_id, 64)
    if not safe_template_id:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        from app.services.form_template_pdf_service import render_form_template_pdf

        pdf_bytes = await asyncio.to_thread(render_form_template_pdf, safe_template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")
    except ImportError:
        raise HTTPException(
            status_code=503, detail="PDF generation is temporarily unavailable"
        )

    filename = f"{safe_template_id}.pdf"
    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            # Public marketing assets — short browser cache + revalidation
            # is fine. The render itself is cached process-side via lru_cache.
            "Cache-Control": "public, max-age=300, must-revalidate",
        },
    )


# Phase C: lead-capture for the public template-download surface.
# Pydantic v2 validators per the canonical guidance at
# https://pydantic.dev/docs/validation/latest/concepts/validators/.
class _MarketingTemplateDownloadRequest(BaseModel):
    template_id: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    name: Optional[str] = Field(None, max_length=120)
    utm_source: Optional[str] = Field(None, max_length=60)
    utm_medium: Optional[str] = Field(None, max_length=60)
    utm_campaign: Optional[str] = Field(None, max_length=120)


@router.post(
    "/public/marketing/template-download",
    tags=["Public Forms"],
    responses={
        200: {"description": "Lead recorded; PDF dispatched by email"},
        400: {"description": "Validation error"},
        404: {"description": "Unknown template"},
        429: {"description": "Rate limited"},
    },
)
async def public_marketing_template_download(
    payload: _MarketingTemplateDownloadRequest,
    request: Request,
):
    """Email-gated download of a catalog form template (Phase C).

    The marketing page collects email + optional name + UTM context;
    we record the lead in ``marketing_leads`` and dispatch the
    rendered PDF as an email attachment via Resend. Rate-limited
    aggressively (10/hour/IP) because each call costs an outbound
    email; idempotent on (email, template_id) so a determined visitor
    can re-trigger the email without polluting the lead table.
    """
    client_ip = getattr(request.client, "host", None) if request.client else "unknown"
    if not rate_limiter.check_rate_limit(
        f"marketing_template_download_{client_ip}",
        limit=10,
        window_seconds=3600,
    ):
        raise HTTPException(
            status_code=429, detail="Too many requests. Please try again later."
        )

    safe_template_id = InputSanitizer.sanitize_text(payload.template_id, 64)
    if not safe_template_id:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        from app.services.marketing_lead_service import MarketingLeadService

        service = MarketingLeadService()
        result = await service.capture_template_download(
            email=str(payload.email),
            template_id=safe_template_id,
            recipient_name=payload.name,
            utm_source=payload.utm_source,
            utm_medium=payload.utm_medium,
            utm_campaign=payload.utm_campaign,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "status": result.get("status"),
        "email_dispatched": result.get("email_dispatched"),
        "message": (
            "Check your inbox — the template is on its way."
            if result.get("email_dispatched")
            else (
                "We've recorded your request. If you don't receive the "
                "PDF in a few minutes, please try again."
            )
        ),
    }


@router.post("/public/forms/{form_id}/submit", tags=["Public Forms"])
async def submit_form(
    form_id: str, response_data: SubmitFormRequest, request: Request, response: Response
):
    """Submit a form response with enhanced security validation"""
    try:
        # Get client information
        client_ip: str = (
            getattr(request.client, "host", "unknown") if request.client else "unknown"
        )
        user_agent = request.headers.get("user-agent", "")

        # Enhanced rate limiting for form submissions
        if not rate_limiter.check_rate_limit(
            f"form_submission_{client_ip}", limit=20, window_seconds=3600
        ):
            logger.warning(
                f"Rate limit exceeded for form submission from IP: {client_ip}"
            )
            raise HTTPException(
                status_code=429,
                detail="Too many form submissions. Please try again later.",
            )

        # Validate form_id
        if not form_id or not isinstance(form_id, str):
            logger.warning(
                f"Invalid form ID in submission: {form_id} from IP: {client_ip}"
            )
            raise HTTPException(status_code=400, detail="Invalid form ID")

        form_id = InputSanitizer.sanitize_text(form_id, 100)
        if not form_id:
            raise HTTPException(status_code=400, detail="Invalid form ID")

        # Additional validation: Check if form allows public submissions
        try:
            form = await form_service.get_form(form_id)
            if not form.get("settings", {}).get("is_public", False):
                logger.warning(
                    f"Attempt to submit to non-public form {form_id} from IP: {client_ip}"
                )
                raise HTTPException(
                    status_code=403, detail="Form is not publicly accessible"
                )
        except HTTPException:
            raise
        except Exception:
            logger.error(f"Failed to validate form {form_id} for public submission")
            raise HTTPException(status_code=404, detail="Form not found")
        # Log submission attempt
        logger.info(
            f"Form submission attempt: id={form_id}, ip={client_ip}, "
            f"email={response_data.submitted_by_email}"
        )

        # Submit form with security validation
        result = await form_service.submit_form_response(
            form_id, response_data, client_ip, user_agent
        )

        # Add security headers
        for (
            header_name,
            header_value,
        ) in SecurityHeaders.get_form_security_headers().items():
            response.headers[header_name] = header_value

        # Log successful submission
        logger.info(
            f"Form submitted successfully: id={form_id}, "
            f"response_id={result.get('id')}, ip={client_ip}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting form {form_id}: {str(e)}, ip={client_ip}")
        raise HTTPException(status_code=500, detail="Failed to submit form")


# Form template endpoints
def _get_form_templates() -> list[FormTemplateDefinition]:
    """Build the static form template catalog exposed by the API."""
    templates: list[FormTemplateDefinition] = [
        {
            "id": "wedding_feedback",
            "name": "Wedding Feedback Form",
            "description": "Collect feedback from couples about their wedding experience",
            "category": "feedback",
            "fields": [
                {
                    "id": "overall_rating",
                    "label": "Overall Experience Rating",
                    "type": "rating",
                    "required": True,
                    "description": "Rate your overall wedding planning experience (1-5 stars)",
                    "order": 1,
                },
                {
                    "id": "planning_satisfaction",
                    "label": "Planning Process Satisfaction",
                    "type": "scale",
                    "required": True,
                    "description": "How satisfied were you with the planning process? (1-10 scale)",
                    "order": 2,
                },
                {
                    "id": "communication_rating",
                    "label": "Communication Quality",
                    "type": "rating",
                    "required": True,
                    "description": "Rate the quality of communication throughout the process",
                    "order": 3,
                },
                {
                    "id": "venue_satisfaction",
                    "label": "Venue Satisfaction",
                    "type": "rating",
                    "required": False,
                    "description": "How satisfied were you with the venue?",
                    "order": 4,
                },
                {
                    "id": "vendor_satisfaction",
                    "label": "Vendor Performance",
                    "type": "rating",
                    "required": False,
                    "description": "Rate the overall performance of vendors",
                    "order": 5,
                },
                {
                    "id": "timeline_satisfaction",
                    "label": "Timeline Management",
                    "type": "rating",
                    "required": False,
                    "description": "How well was the wedding timeline managed?",
                    "order": 6,
                },
                {
                    "id": "budget_satisfaction",
                    "label": "Budget Management",
                    "type": "rating",
                    "required": False,
                    "description": "Rate how well the budget was managed",
                    "order": 7,
                },
                {
                    "id": "favorite_moment",
                    "label": "Favorite Moment",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "Tell us about your favorite moment from the wedding...",
                    "description": "Share your most memorable moment",
                    "order": 8,
                },
                {
                    "id": "improvements",
                    "label": "Suggestions for Improvement",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "How could we improve our services?",
                    "description": "Any suggestions for how we could improve",
                    "order": 9,
                },
                {
                    "id": "recommendation",
                    "label": "Would you recommend our services?",
                    "type": "radio",
                    "required": True,
                    "options": [
                        "Definitely",
                        "Probably",
                        "Maybe",
                        "Probably not",
                        "Definitely not",
                    ],
                    "order": 10,
                },
                {
                    "id": "additional_comments",
                    "label": "Additional Comments",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "Any other thoughts or comments...",
                    "description": "Share any additional feedback",
                    "order": 11,
                },
            ],
        },
        {
            "id": "guest_feedback",
            "name": "Guest Experience Form",
            "description": "Collect feedback from wedding guests about their experience",
            "category": "feedback",
            "fields": [
                {
                    "id": "guest_name",
                    "label": "Your Name",
                    "type": "text",
                    "required": True,
                    "order": 1,
                },
                {
                    "id": "guest_email",
                    "label": "Email Address",
                    "type": "email",
                    "required": True,
                    "order": 2,
                },
                {
                    "id": "event_rating",
                    "label": "Overall Event Rating",
                    "type": "rating",
                    "required": True,
                    "description": "Rate your overall experience at the wedding",
                    "order": 3,
                },
                {
                    "id": "venue_rating",
                    "label": "Venue Rating",
                    "type": "rating",
                    "required": False,
                    "description": "How did you like the venue?",
                    "order": 4,
                },
                {
                    "id": "food_rating",
                    "label": "Food & Beverage Rating",
                    "type": "rating",
                    "required": False,
                    "description": "Rate the food and drinks",
                    "order": 5,
                },
                {
                    "id": "music_rating",
                    "label": "Music & Entertainment",
                    "type": "rating",
                    "required": False,
                    "description": "Rate the music and entertainment",
                    "order": 6,
                },
                {
                    "id": "favorite_part",
                    "label": "Favorite Part of the Wedding",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "What was your favorite moment?",
                    "order": 7,
                },
                {
                    "id": "guest_comments",
                    "label": "Additional Comments",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "Any other feedback for the couple...",
                    "order": 8,
                },
            ],
        },
        {
            "id": "vendor_questionnaire",
            "name": "Vendor Information Form",
            "description": "Collect detailed information from potential vendors",
            "category": "vendor",
            "fields": [
                {
                    "id": "company_name",
                    "label": "Company Name",
                    "type": "text",
                    "required": True,
                    "order": 1,
                },
                {
                    "id": "contact_name",
                    "label": "Primary Contact Name",
                    "type": "text",
                    "required": True,
                    "order": 2,
                },
                {
                    "id": "contact_email",
                    "label": "Contact Email",
                    "type": "email",
                    "required": True,
                    "order": 3,
                },
                {
                    "id": "contact_phone",
                    "label": "Phone Number",
                    "type": "phone",
                    "required": True,
                    "order": 4,
                },
                {
                    "id": "service_type",
                    "label": "Service Type",
                    "type": "select",
                    "required": True,
                    "options": [
                        "Photography",
                        "Videography",
                        "Catering",
                        "Florist",
                        "Music/DJ",
                        "Transportation",
                        "Other",
                    ],
                    "order": 5,
                },
                {
                    "id": "years_experience",
                    "label": "Years in Business",
                    "type": "number",
                    "required": True,
                    "order": 6,
                },
                {
                    "id": "service_description",
                    "label": "Service Description",
                    "type": "textarea",
                    "required": True,
                    "placeholder": "Describe your services in detail...",
                    "order": 7,
                },
                {
                    "id": "portfolio_url",
                    "label": "Portfolio/Website URL",
                    "type": "text",
                    "required": False,
                    "order": 8,
                },
                {
                    "id": "pricing_range",
                    "label": "Typical Pricing Range",
                    "type": "select",
                    "required": True,
                    "options": [
                        "$500-$1,000",
                        "$1,000-$2,500",
                        "$2,500-$5,000",
                        "$5,000-$10,000",
                        "$10,000+",
                    ],
                    "order": 9,
                },
                {
                    "id": "availability",
                    "label": "Availability",
                    "type": "textarea",
                    "required": True,
                    "placeholder": "Describe your availability for events...",
                    "order": 10,
                },
            ],
        },
    ]
    # Append the production catalog (couple intake, order of events,
    # guest dietary, vendor onboarding, photo shot list, bridal-party
    # logistics, vendor performance review, engagement session brief,
    # day-of emergency contacts). The catalog lives in its own module
    # (app/services/form_template_catalog.py) and is validated at
    # import-time by tests/backend/test_form_template_catalog.py — every
    # field passes through FormField.model_validate before this code
    # path can ship.
    templates.extend(_CATALOG_TEMPLATES)
    return templates


@router.get("/form-templates", tags=["Form Templates"])
def get_form_templates(
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
) -> FormTemplateResponse:
    """Get available form templates"""
    return {"templates": _get_form_templates()}


@router.get(
    "/forms/seeded/{catalog_template_id}",
    tags=["Forms"],
    responses={
        200: {"description": "Seeded form id resolved for this planner"},
        400: {"description": "Unknown catalog template id"},
        404: {"description": "No seeded template for this planner"},
    },
)
async def get_seeded_form_for_template(
    catalog_template_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Resolve a catalog template id (e.g. ``couple_intake``) to the
    planner's actual seeded form id (Phase D seeded forms).

    Used by the action-button toast on the planner UI: when the
    couple accepts the portal invite, the toast metadata carries
    catalog_template_id (stable across all planners), and this
    endpoint lets the frontend look up the per-planner form_id
    needed to call ``POST /admin/forms/{form_id}/send`` without
    scanning every form in the planner's workspace.
    """
    owner_scope = await _resolve_form_owner_scope(current_user)
    return await form_service.get_seeded_form_id(
        catalog_template_id,
        created_by=owner_scope["owner_email"],
        owner_alias_emails=owner_scope["owner_alias_emails"],
    )


@router.post("/forms/from-template/{template_id}", tags=["Form Templates"])
async def create_form_from_template(
    template_id: str,
    form_name: str,
    wedding_id: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Create a form from a template"""
    enforce_team_permission(current_user, "manage_forms")

    # Get templates
    templates = _get_form_templates()

    # Find the template
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    # Create form from template
    template_fields = [FormField.model_validate(field) for field in template["fields"]]
    form_data = CreateFormRequest(
        name=form_name,
        settings=FormSettings(
            title=template["name"],
            description=template["description"],
            submit_button_text="Submit",
            success_message="Thank you for your feedback!",
            redirect_url=None,
            allow_multiple_submissions=False,
            collect_email=True,
            is_public=True,
            requires_auth=False,
        ),
        fields=template_fields,
        wedding_id=wedding_id,
        template_type=template_id,
    )

    owner_scope = await _resolve_form_owner_scope(current_user)
    return await form_service.create_form(
        form_data,
        owner_scope["owner_email"],
        actor_email=current_user.email,
    )


@router.post("/forms/{form_id}/duplicate", tags=["Forms"])
async def duplicate_form(
    form_id: str,
    duplicate_request: DuplicateFormRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Duplicate an existing form for the authenticated planner."""
    enforce_team_permission(current_user, "manage_forms")
    owner_scope = await _resolve_form_owner_scope(current_user)

    return await form_service.duplicate_form(
        form_id,
        duplicate_request,
        owner_scope["owner_email"],
        owner_alias_emails=owner_scope["owner_alias_emails"],
        actor_email=current_user.email,
    )
