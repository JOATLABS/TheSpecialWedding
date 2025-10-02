from fastapi import APIRouter, HTTPException, Depends, Request, Response, Query
from fastapi.responses import Response as FastAPIResponse
from app.models.form import (
    CreateFormRequest,
    UpdateFormRequest,
    SendFormRequest,
    SubmitFormRequest,
    DuplicateFormRequest,
    FormViewUpdateRequest,
    FormModel,
    FormResponse,
)
from app.services.form_service import FormService
from app.dependencies.auth_extended import (
    get_current_user_extended, ExtendedAuthUser, check_wedding_access
)
from app.utils.security_utils import (
    InputSanitizer, SecurityHeaders, rate_limiter, FormSecurityValidator
)
from app.services.security_audit_service import (
    security_audit, SecurityEventType, SecuritySeverity
)
from typing import List, Dict, Any, Optional
import logging
import html
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()
form_service = FormService()

# Admin endpoints (require authentication)
@router.post("/forms", tags=["Forms"])
def create_form(
    form_data: CreateFormRequest,
    request: Request,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Create a new form with enhanced security validation"""
    # Enhanced authorization check
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        # Log unauthorized access attempt
        client_ip = getattr(request.client, 'host', None) if request.client else None
        security_audit.log_security_event(
            event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
            severity=SecuritySeverity.HIGH,
            user_email=current_user.email,
            ip_address=client_ip,
            user_agent=request.headers.get('user-agent'),
            resource="forms",
            action="create",
            details={
                "user_role": current_user.role,
                "required_role": "wedding_planner"
            },
            success=False,
            error_message="Insufficient privileges"
        )
        
        logger.warning(
            f"Unauthorized form creation attempt by {current_user.email} "
            f"with role {current_user.role}"
        )
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Wedding planner role required."
        )
    
    # Validate wedding access if wedding_id is provided
    if form_data.wedding_id:
        if not check_wedding_access(current_user, form_data.wedding_id):
            logger.warning(
                f"User {current_user.email} attempted to create form for "
                f"wedding {form_data.wedding_id} without access"
            )
            raise HTTPException(
                status_code=403, 
                detail="Access denied. You don't have access to this wedding."
            )
    
    # Log form creation attempt
    client_ip = getattr(request.client, 'host', None) if request.client else None
    logger.info(
        f"Form creation attempt: user={current_user.email}, "
        f"ip={client_ip}, wedding_id={form_data.wedding_id}"
    )
    
    try:
        result = form_service.create_form(form_data, current_user.email)
        
        # Log successful creation
        logger.info(
            f"Form created successfully: id={result.get('id')}, "
            f"user={current_user.email}"
        )
        
        # Security audit log
        security_audit.log_security_event(
            event_type=SecurityEventType.FORM_CREATION,
            severity=SecuritySeverity.MEDIUM,
            user_email=current_user.email,
            ip_address=client_ip,
            user_agent=request.headers.get('user-agent'),
            resource="forms",
            action="create",
            details={
                "form_id": result.get('id'),
                "wedding_id": form_data.wedding_id,
                "form_name": form_data.name,
                "field_count": len(form_data.fields)
            },
            success=True,
            form_id=result.get('id'),
            wedding_id=form_data.wedding_id
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Form creation failed: user={current_user.email}, "
            f"error={str(e)}"
        )
        raise

@router.get("/forms", tags=["Forms"])
def get_forms(
    wedding_id: Optional[str] = None,
    request: Request = None,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Get all forms for the current user with security validation"""
    # Enhanced authorization check
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        logger.warning(
            f"Unauthorized forms access attempt by {current_user.email}"
        )
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Wedding planner role required."
        )
    
    # Validate wedding_id if provided
    if wedding_id:
        # Sanitize wedding_id
        wedding_id = InputSanitizer.sanitize_text(wedding_id, 100)
        
        # Check wedding access
        if not check_wedding_access(current_user, wedding_id):
            logger.warning(
                f"User {current_user.email} attempted to access forms for "
                f"wedding {wedding_id} without access"
            )
            raise HTTPException(
                status_code=403, 
                detail="Access denied. You don't have access to this wedding."
            )
    
    try:
        forms = form_service.get_forms(current_user.email, wedding_id, current_user.is_root_admin)
        
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
def get_form(
    form_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Get a specific form with authorization validation"""
    # Enhanced authorization check
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        logger.warning(
            f"Unauthorized form access attempt by {current_user.email} for form {form_id}"
        )
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Wedding planner role required."
        )
    
    # Validate form_id
    if not form_id or not isinstance(form_id, str):
        raise HTTPException(status_code=400, detail="Invalid form ID")
    
    form_id = InputSanitizer.sanitize_text(form_id, 100)
    if not form_id:
        raise HTTPException(status_code=400, detail="Invalid form ID")
    
    try:
        form = form_service.get_form(form_id, current_user.email)
        
        # Additional wedding access check if form has wedding_id
        if form.get('wedding_id') and not check_wedding_access(current_user, form['wedding_id']):
            logger.warning(
                f"User {current_user.email} attempted to access form {form_id} "
                f"for wedding {form['wedding_id']} without access"
            )
            raise HTTPException(
                status_code=403, 
                detail="Access denied. You don't have access to this wedding."
            )
        
        # Log access
        logger.info(
            f"Form accessed: id={form_id}, user={current_user.email}"
        )
        
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
def update_form(
    form_id: str,
    form_data: UpdateFormRequest,
    request: Request,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Update a form with enhanced security validation"""
    # Enhanced authorization check
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        logger.warning(
            f"Unauthorized form update attempt by {current_user.email} for form {form_id}"
        )
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Wedding planner role required."
        )
    
    # Validate form_id
    if not form_id or not isinstance(form_id, str):
        raise HTTPException(status_code=400, detail="Invalid form ID")
    
    form_id = InputSanitizer.sanitize_text(form_id, 100)
    if not form_id:
        raise HTTPException(status_code=400, detail="Invalid form ID")
    
    # Get existing form to check wedding access
    try:
        existing_form = form_service.get_form(form_id, current_user.email)
        
        # Check wedding access if form has wedding_id
        if existing_form.get('wedding_id'):
            if not check_wedding_access(current_user, existing_form['wedding_id']):
                logger.warning(
                    f"User {current_user.email} attempted to update form {form_id} "
                    f"for wedding {existing_form['wedding_id']} without access"
                )
                raise HTTPException(
                    status_code=403, 
                    detail="Access denied. You don't have access to this wedding."
                )
        
        # Log update attempt
        client_ip = getattr(request.client, 'host', None) if request.client else None
        logger.info(
            f"Form update attempt: id={form_id}, user={current_user.email}, "
            f"ip={client_ip}"
        )
        
        result = form_service.update_form(form_id, form_data, current_user.email)
        
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
def delete_form(
    form_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Delete a form with enhanced security validation"""
    logger.info(f"DELETE /forms/{form_id} called by {current_user.email}, is_root_admin={current_user.is_root_admin}")
    
    # Enhanced authorization check
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        logger.warning(
            f"Unauthorized form deletion attempt by {current_user.email} for form {form_id}"
        )
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Wedding planner role required."
        )
    
    # Validate form_id
    if not form_id or not isinstance(form_id, str):
        logger.error(f"Invalid form_id type: {type(form_id)}, value: {form_id}")
        raise HTTPException(status_code=400, detail="Invalid form ID")
    
    form_id = InputSanitizer.sanitize_text(form_id, 100)
    if not form_id:
        logger.error(f"Form ID sanitization failed")
        raise HTTPException(status_code=400, detail="Invalid form ID")
    
    logger.info(f"Form ID after sanitization: {form_id}")
    
    try:
        logger.info(f"About to get existing form for access check...")
        
        # For ROOT_ADMIN, get form without created_by constraint
        if current_user.is_root_admin:
            existing_form = form_service.get_form(form_id)  # No created_by for ROOT_ADMIN
            logger.info(f"ROOT_ADMIN form retrieval successful")
        else:
            existing_form = form_service.get_form(form_id, current_user.email)
            logger.info(f"Regular user form retrieval successful")
        
        # Check wedding access if form has wedding_id
        if existing_form.get('wedding_id'):
            logger.info(f"Checking wedding access for wedding_id: {existing_form['wedding_id']}")
            if not check_wedding_access(current_user, existing_form['wedding_id']):
                logger.warning(
                    f"User {current_user.email} attempted to delete form {form_id} "
                    f"for wedding {existing_form['wedding_id']} without access"
                )
                raise HTTPException(
                    status_code=403, 
                    detail="Access denied. You don't have access to this wedding."
                )
        
        # Log deletion attempt
        client_ip = getattr(request.client, 'host', None) if request.client else None
        logger.warning(
            f"Form deletion attempt: id={form_id}, user={current_user.email}, "
            f"ip={client_ip}"
        )
        
        logger.info(f"About to call form_service.delete_form...")
        result = form_service.delete_form(form_id, current_user.email, current_user.is_root_admin)
        
        # Log successful deletion
        logger.warning(
            f"Form deleted: id={form_id}, user={current_user.email}"
        )
        
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
def send_form(
    form_id: str,
    send_data: SendFormRequest,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Send form to recipients via email"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    return form_service.send_form(form_id, send_data, current_user.email)

@router.get("/forms/{form_id}/responses", tags=["Forms"])
def get_form_responses(
    form_id: str,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Get all responses for a form"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")

    return form_service.get_form_responses(form_id, current_user.email)


@router.post("/forms/{form_id}/views", tags=["Forms"])
def mark_form_view(
    form_id: str,
    payload: FormViewUpdateRequest,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
):
    """Update the planner's last viewed timestamp for a form scope."""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")

    return form_service.mark_form_viewed(
        form_id,
        current_user.email,
        payload.scope,
        submission_count=payload.submission_count,
    )

@router.get("/forms/{form_id}/analytics", tags=["Forms"])
def get_form_analytics(
    form_id: str,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Get analytics for a form"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    return form_service.get_form_analytics(form_id, current_user.email)

@router.get("/forms/{form_id}/export/csv", tags=["Forms"])
def export_form_responses_csv(
    form_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    date_from: Optional[str] = Query(None, description="Start date filter (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"),
    date_to: Optional[str] = Query(None, description="End date filter (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"),
    include_metadata: bool = Query(True, description="Include submission metadata (date, IP, etc.)")
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
        # Enhanced authorization check
        if not (current_user.is_wedding_planner or current_user.is_root_admin):
            # Log unauthorized access attempt
            client_ip = getattr(request.client, 'host', None) if request.client else None
            security_audit.log_security_event(
                event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
                severity=SecuritySeverity.HIGH,
                user_email=current_user.email,
                ip_address=client_ip,
                user_agent=request.headers.get('user-agent'),
                resource="forms",
                action="csv_export",
                details={
                    "form_id": form_id,
                    "user_role": current_user.role,
                    "required_role": "wedding_planner"
                },
                success=False,
                error_message="Insufficient privileges for CSV export"
            )
            
            logger.warning(
                f"Unauthorized CSV export attempt by {current_user.email} "
                f"with role {current_user.role} for form {form_id}"
            )
            raise HTTPException(
                status_code=403, 
                detail="Access denied. Wedding planner role required for CSV export."
            )
        
        # Validate form_id format
        if not form_id or not isinstance(form_id, str):
            raise HTTPException(status_code=400, detail="Invalid form ID")
        
        form_id = InputSanitizer.sanitize_text(form_id, 100)
        if not form_id:
            raise HTTPException(status_code=400, detail="Invalid form ID")
        
        # Get form to check wedding access before export
        try:
            form = form_service.get_form(form_id, current_user.email)
            
            # Additional wedding access check if form has wedding_id
            if form.get('wedding_id') and not check_wedding_access(current_user, form['wedding_id']):
                logger.warning(
                    f"User {current_user.email} attempted to export CSV for form {form_id} "
                    f"for wedding {form['wedding_id']} without access"
                )
                raise HTTPException(
                    status_code=403, 
                    detail="Access denied. You don't have access to this wedding's forms."
                )
        except HTTPException as e:
            if e.status_code == 404:
                logger.info(f"CSV export attempted for non-existent form {form_id} by {current_user.email}")
            raise
        
        # Log CSV export attempt for security audit
        client_ip = getattr(request.client, 'host', None) if request.client else None
        logger.info(
            f"CSV export attempt: form_id={form_id}, user={current_user.email}, "
            f"ip={client_ip}, date_from={date_from}, date_to={date_to}, "
            f"include_metadata={include_metadata}"
        )
        
        # Call the form service to generate CSV
        export_result = form_service.export_form_responses_csv(
            form_id=form_id,
            created_by=current_user.email,
            date_from=date_from,
            date_to=date_to,
            include_metadata=include_metadata
        )
        
        # Log successful export for audit
        security_audit.log_security_event(
            event_type=SecurityEventType.DATA_EXPORT,
            severity=SecuritySeverity.MEDIUM,
            user_email=current_user.email,
            ip_address=client_ip,
            user_agent=request.headers.get('user-agent'),
            resource="forms",
            action="csv_export",
            details={
                "form_id": form_id,
                "form_name": export_result.get('form_name'),
                "exported_count": export_result.get('exported_count', 0),
                "file_size": export_result.get('size', 0),
                "filters": {
                    "date_from": date_from,
                    "date_to": date_to,
                    "include_metadata": include_metadata
                }
            },
            success=True,
            form_id=form_id,
            wedding_id=form.get('wedding_id')
        )
        
        logger.info(
            f"CSV export successful: form_id={form_id}, user={current_user.email}, "
            f"exported_count={export_result.get('exported_count', 0)}, "
            f"file_size={export_result.get('size', 0)} bytes"
        )
        
        # Return CSV file as download
        return FastAPIResponse(
            content=export_result['content'],
            media_type=export_result['content_type'],
            headers={
                "Content-Disposition": f"attachment; filename=\"{export_result['filename']}\"",
                "Content-Length": str(export_result['size']),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
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
            detail="Failed to export form responses. Please try again later."
        )

# Public endpoints (no authentication required) - Enhanced security
@router.get("/public/forms/{form_id}", tags=["Public Forms"])
def get_public_form(form_id: str, request: Request, response: Response):
    """Get a form for public submission with security validation"""
    try:
        # Rate limiting for public form access
        client_ip = getattr(request.client, 'host', None) if request.client else 'unknown'
        if not rate_limiter.check_rate_limit(
            f"public_form_access_{client_ip}", 
            limit=50, 
            window_seconds=3600
        ):
            logger.warning(f"Rate limit exceeded for public form access from IP: {client_ip}")
            raise HTTPException(
                status_code=429, 
                detail="Too many requests. Please try again later."
            )
        
        # Validate form_id
        if not form_id or not isinstance(form_id, str):
            logger.warning(f"Invalid form ID in public access: {form_id} from IP: {client_ip}")
            raise HTTPException(status_code=400, detail="Invalid form ID")
        
        form_id = InputSanitizer.sanitize_text(form_id, 100)
        if not form_id:
            raise HTTPException(status_code=400, detail="Invalid form ID")
        
        # Get form with public access (no creator email)
        form = form_service.get_form(form_id)
        
        # Verify form is public
        if not form.get("settings", {}).get("is_public", False):
            logger.warning(
                f"Attempt to access non-public form {form_id} from IP: {client_ip}"
            )
            raise HTTPException(status_code=403, detail="Form is not publicly accessible")
        
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
                )
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
                    "order": field.get("order", 0)
                }
                for field in form["fields"]
            ],
            "is_active": form["is_active"]
        }
        
        # Add security headers
        for header_name, header_value in SecurityHeaders.get_form_security_headers().items():
            response.headers[header_name] = header_value
        
        # Log public access
        logger.info(
            f"Public form accessed: id={form_id}, ip={client_ip}"
        )
        
        return public_form
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching public form {form_id}: {str(e)}")
        raise HTTPException(status_code=404, detail="Form not found")

@router.post("/public/forms/{form_id}/submit", tags=["Public Forms"])
def submit_form(
    form_id: str,
    response_data: SubmitFormRequest,
    request: Request,
    response: Response
):
    """Submit a form response with enhanced security validation"""
    try:
        # Get client information
        client_ip = getattr(request.client, 'host', None) if request.client else 'unknown'
        user_agent = request.headers.get('user-agent', '')
        
        # Enhanced rate limiting for form submissions
        if not rate_limiter.check_rate_limit(
            f"form_submission_{client_ip}", 
            limit=20, 
            window_seconds=3600
        ):
            logger.warning(
                f"Rate limit exceeded for form submission from IP: {client_ip}"
            )
            raise HTTPException(
                status_code=429, 
                detail="Too many form submissions. Please try again later."
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
            form = form_service.get_form(form_id)
            if not form.get("settings", {}).get("is_public", False):
                logger.warning(
                    f"Attempt to submit to non-public form {form_id} from IP: {client_ip}"
                )
                raise HTTPException(
                    status_code=403, 
                    detail="Form is not publicly accessible"
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
        result = form_service.submit_form_response(
            form_id, 
            response_data, 
            client_ip, 
            user_agent
        )
        
        # Add security headers
        for header_name, header_value in SecurityHeaders.get_form_security_headers().items():
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
        logger.error(
            f"Error submitting form {form_id}: {str(e)}, ip={client_ip}"
        )
        raise HTTPException(status_code=500, detail="Failed to submit form")

# Form template endpoints
@router.get("/form-templates", tags=["Form Templates"])
def get_form_templates(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Get available form templates"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    templates = [
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
                    "order": 1
                },
                {
                    "id": "planning_satisfaction",
                    "label": "Planning Process Satisfaction",
                    "type": "scale",
                    "required": True,
                    "description": "How satisfied were you with the planning process? (1-10 scale)",
                    "order": 2
                },
                {
                    "id": "communication_rating",
                    "label": "Communication Quality",
                    "type": "rating",
                    "required": True,
                    "description": "Rate the quality of communication throughout the process",
                    "order": 3
                },
                {
                    "id": "venue_satisfaction",
                    "label": "Venue Satisfaction",
                    "type": "rating",
                    "required": False,
                    "description": "How satisfied were you with the venue?",
                    "order": 4
                },
                {
                    "id": "vendor_satisfaction",
                    "label": "Vendor Performance",
                    "type": "rating",
                    "required": False,
                    "description": "Rate the overall performance of vendors",
                    "order": 5
                },
                {
                    "id": "timeline_satisfaction",
                    "label": "Timeline Management",
                    "type": "rating",
                    "required": False,
                    "description": "How well was the wedding timeline managed?",
                    "order": 6
                },
                {
                    "id": "budget_satisfaction",
                    "label": "Budget Management",
                    "type": "rating",
                    "required": False,
                    "description": "Rate how well the budget was managed",
                    "order": 7
                },
                {
                    "id": "favorite_moment",
                    "label": "Favorite Moment",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "Tell us about your favorite moment from the wedding...",
                    "description": "Share your most memorable moment",
                    "order": 8
                },
                {
                    "id": "improvements",
                    "label": "Suggestions for Improvement",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "How could we improve our services?",
                    "description": "Any suggestions for how we could improve",
                    "order": 9
                },
                {
                    "id": "recommendation",
                    "label": "Would you recommend our services?",
                    "type": "radio",
                    "required": True,
                    "options": ["Definitely", "Probably", "Maybe", "Probably not", "Definitely not"],
                    "order": 10
                },
                {
                    "id": "additional_comments",
                    "label": "Additional Comments",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "Any other thoughts or comments...",
                    "description": "Share any additional feedback",
                    "order": 11
                }
            ]
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
                    "order": 1
                },
                {
                    "id": "guest_email",
                    "label": "Email Address",
                    "type": "email",
                    "required": True,
                    "order": 2
                },
                {
                    "id": "event_rating",
                    "label": "Overall Event Rating",
                    "type": "rating",
                    "required": True,
                    "description": "Rate your overall experience at the wedding",
                    "order": 3
                },
                {
                    "id": "venue_rating",
                    "label": "Venue Rating",
                    "type": "rating",
                    "required": False,
                    "description": "How did you like the venue?",
                    "order": 4
                },
                {
                    "id": "food_rating",
                    "label": "Food & Beverage Rating",
                    "type": "rating",
                    "required": False,
                    "description": "Rate the food and drinks",
                    "order": 5
                },
                {
                    "id": "music_rating",
                    "label": "Music & Entertainment",
                    "type": "rating",
                    "required": False,
                    "description": "Rate the music and entertainment",
                    "order": 6
                },
                {
                    "id": "favorite_part",
                    "label": "Favorite Part of the Wedding",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "What was your favorite moment?",
                    "order": 7
                },
                {
                    "id": "guest_comments",
                    "label": "Additional Comments",
                    "type": "textarea",
                    "required": False,
                    "placeholder": "Any other feedback for the couple...",
                    "order": 8
                }
            ]
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
                    "order": 1
                },
                {
                    "id": "contact_name",
                    "label": "Primary Contact Name",
                    "type": "text",
                    "required": True,
                    "order": 2
                },
                {
                    "id": "contact_email",
                    "label": "Contact Email",
                    "type": "email",
                    "required": True,
                    "order": 3
                },
                {
                    "id": "contact_phone",
                    "label": "Phone Number",
                    "type": "phone",
                    "required": True,
                    "order": 4
                },
                {
                    "id": "service_type",
                    "label": "Service Type",
                    "type": "select",
                    "required": True,
                    "options": ["Photography", "Videography", "Catering", "Florist", "Music/DJ", "Transportation", "Other"],
                    "order": 5
                },
                {
                    "id": "years_experience",
                    "label": "Years in Business",
                    "type": "number",
                    "required": True,
                    "order": 6
                },
                {
                    "id": "service_description",
                    "label": "Service Description",
                    "type": "textarea",
                    "required": True,
                    "placeholder": "Describe your services in detail...",
                    "order": 7
                },
                {
                    "id": "portfolio_url",
                    "label": "Portfolio/Website URL",
                    "type": "text",
                    "required": False,
                    "order": 8
                },
                {
                    "id": "pricing_range",
                    "label": "Typical Pricing Range",
                    "type": "select",
                    "required": True,
                    "options": ["$500-$1,000", "$1,000-$2,500", "$2,500-$5,000", "$5,000-$10,000", "$10,000+"],
                    "order": 9
                },
                {
                    "id": "availability",
                    "label": "Availability",
                    "type": "textarea",
                    "required": True,
                    "placeholder": "Describe your availability for events...",
                    "order": 10
                }
            ]
        }
    ]
    
    return {"templates": templates}

@router.post("/forms/from-template/{template_id}", tags=["Form Templates"])
def create_form_from_template(
    template_id: str,
    form_name: str,
    wedding_id: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Create a form from a template"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    # Get templates
    templates_response = get_form_templates(current_user)
    templates = templates_response["templates"]
    
    # Find the template
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create form from template
    form_data = CreateFormRequest(
        name=form_name,
        settings={
            "title": template["name"],
            "description": template["description"],
            "submit_button_text": "Submit",
            "success_message": "Thank you for your feedback!",
            "allow_multiple_submissions": False,
            "collect_email": True,
            "is_public": True,
            "requires_auth": False
        },
        fields=template["fields"],
        wedding_id=wedding_id,
        template_type=template_id
    )

    return form_service.create_form(form_data, current_user.email)


@router.post("/forms/{form_id}/duplicate", tags=["Forms"])
def duplicate_form(
    form_id: str,
    duplicate_request: DuplicateFormRequest,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
):
    """Duplicate an existing form for the authenticated planner."""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")

    return form_service.duplicate_form(form_id, duplicate_request, current_user.email)