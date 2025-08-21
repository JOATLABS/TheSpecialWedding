from fastapi import APIRouter, HTTPException, Depends, Request
from app.models.form import (
    CreateFormRequest, UpdateFormRequest, SendFormRequest, SubmitFormRequest,
    FormModel, FormResponse
)
from app.services.form_service import FormService
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from typing import List, Dict, Any, Optional
import logging

router = APIRouter()
form_service = FormService()

# Admin endpoints (require authentication)
@router.post("/forms", tags=["Forms"])
def create_form(
    form_data: CreateFormRequest,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Create a new form"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    return form_service.create_form(form_data, current_user.email)

@router.get("/forms", tags=["Forms"])
def get_forms(
    wedding_id: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Get all forms for the current user"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    return form_service.get_forms(current_user.email, wedding_id)

@router.get("/forms/{form_id}", tags=["Forms"])
def get_form(
    form_id: str,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Get a specific form"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    return form_service.get_form(form_id, current_user.email)

@router.put("/forms/{form_id}", tags=["Forms"])
def update_form(
    form_id: str,
    form_data: UpdateFormRequest,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Update a form"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    return form_service.update_form(form_id, form_data, current_user.email)

@router.delete("/forms/{form_id}", tags=["Forms"])
def delete_form(
    form_id: str,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Delete a form"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    return form_service.delete_form(form_id, current_user.email)

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

@router.get("/forms/{form_id}/analytics", tags=["Forms"])
def get_form_analytics(
    form_id: str,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """Get analytics for a form"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner role required.")
    
    return form_service.get_form_analytics(form_id, current_user.email)

# Public endpoints (no authentication required)
@router.get("/public/forms/{form_id}", tags=["Public Forms"])
def get_public_form(form_id: str):
    """Get a form for public submission (no auth required)"""
    try:
        form = form_service.get_form(form_id)
        
        # Only return necessary fields for public access
        public_form = {
            "id": form["id"],
            "settings": form["settings"],
            "fields": form["fields"],
            "is_active": form["is_active"]
        }
        
        return public_form
        
    except Exception as e:
        logging.error(f"Error fetching public form: {str(e)}")
        raise HTTPException(status_code=404, detail="Form not found")

@router.post("/public/forms/{form_id}/submit", tags=["Public Forms"])
def submit_form(
    form_id: str,
    response_data: SubmitFormRequest,
    request: Request
):
    """Submit a form response (no auth required)"""
    try:
        # Get client IP and user agent
        ip_address = getattr(request.client, 'host', None) if request.client else None
        user_agent = request.headers.get('user-agent')
        
        return form_service.submit_form_response(
            form_id, 
            response_data, 
            ip_address, 
            user_agent
        )
        
    except Exception as e:
        logging.error(f"Error submitting form: {str(e)}")
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