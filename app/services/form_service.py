from fastapi import HTTPException
from bson import ObjectId
from app.core.database import mongo
from app.models.form import (
    FormModel, FormResponse, FormDistribution, 
    CreateFormRequest, UpdateFormRequest, SendFormRequest, SubmitFormRequest
)
from app.services.email_service_resend import ResendEmailService
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import uuid

class FormService:
    def __init__(self):
        self.forms_collection = mongo.db["forms"]
        self.responses_collection = mongo.db["form_responses"] 
        self.distributions_collection = mongo.db["form_distributions"]
        self.email_service = ResendEmailService()

    def create_form(self, form_data: CreateFormRequest, created_by: str) -> Dict[str, Any]:
        """Create a new form"""
        try:
            # Generate unique form ID
            form_id = f"form_{int(datetime.now().timestamp() * 1000)}"
            
            # Validate field IDs are unique
            field_ids = [field.id for field in form_data.fields]
            if len(field_ids) != len(set(field_ids)):
                raise HTTPException(status_code=400, detail="Field IDs must be unique")
            
            # Create form document
            form_doc = {
                "_id": form_id,
                "name": form_data.name,
                "settings": form_data.settings.dict(),
                "fields": [field.dict() for field in form_data.fields],
                "created_by": created_by,
                "wedding_id": form_data.wedding_id,
                "template_type": form_data.template_type,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "submission_count": 0
            }
            
            # Insert form
            result = self.forms_collection.insert_one(form_doc)
            
            if result.inserted_id:
                return {"id": form_id, "message": "Form created successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to create form")
                
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error creating form: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create form: {str(e)}")

    def get_forms(self, created_by: str, wedding_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get forms for a user"""
        try:
            query = {"created_by": created_by, "is_active": True}
            if wedding_id:
                query["wedding_id"] = wedding_id
                
            forms = list(self.forms_collection.find(query).sort("created_at", -1))
            
            # Convert ObjectId to string and format response
            for form in forms:
                form["id"] = form["_id"]
                form.pop("_id", None)
                
            return forms
            
        except Exception as e:
            logging.error(f"Error fetching forms: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch forms: {str(e)}")

    def get_form(self, form_id: str, created_by: Optional[str] = None) -> Dict[str, Any]:
        """Get a specific form"""
        try:
            query = {"_id": form_id, "is_active": True}
            if created_by:
                query["created_by"] = created_by
                
            form = self.forms_collection.find_one(query)
            
            if not form:
                raise HTTPException(status_code=404, detail="Form not found")
                
            form["id"] = form["_id"]
            form.pop("_id", None)
            
            return form
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching form: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch form: {str(e)}")

    def update_form(self, form_id: str, form_data: UpdateFormRequest, created_by: str) -> Dict[str, Any]:
        """Update an existing form"""
        try:
            # Check if form exists and user owns it
            existing_form = self.forms_collection.find_one({
                "_id": form_id, 
                "created_by": created_by,
                "is_active": True
            })
            
            if not existing_form:
                raise HTTPException(status_code=404, detail="Form not found")
            
            # Build update document
            update_doc = {"updated_at": datetime.utcnow()}
            
            if form_data.name is not None:
                update_doc["name"] = form_data.name
            if form_data.settings is not None:
                update_doc["settings"] = form_data.settings.dict()
            if form_data.fields is not None:
                # Validate field IDs are unique
                field_ids = [field.id for field in form_data.fields]
                if len(field_ids) != len(set(field_ids)):
                    raise HTTPException(status_code=400, detail="Field IDs must be unique")
                update_doc["fields"] = [field.dict() for field in form_data.fields]
            if form_data.is_active is not None:
                update_doc["is_active"] = form_data.is_active
            
            # Update form
            result = self.forms_collection.update_one(
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

    def delete_form(self, form_id: str, created_by: str) -> Dict[str, Any]:
        """Soft delete a form"""
        try:
            result = self.forms_collection.update_one(
                {"_id": form_id, "created_by": created_by},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Form not found")
                
            return {"message": "Form deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error deleting form: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete form: {str(e)}")

    def send_form(self, form_id: str, send_data: SendFormRequest, created_by: str) -> Dict[str, Any]:
        """Send form to recipients via email"""
        try:
            # Get form
            form = self.get_form(form_id, created_by)
            
            # Generate form URL
            base_url = os.getenv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:3000")
            form_url = f"{base_url}/forms/{form_id}"
            
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
                        email_result = self.email_service.send_email(
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
                    self.distributions_collection.insert_one(distribution_doc)
                    
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

    def submit_form_response(self, form_id: str, response_data: SubmitFormRequest, 
                           ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
        """Submit a form response"""
        try:
            # Get form (public access)
            form = self.get_form(form_id)
            
            if not form["is_active"]:
                raise HTTPException(status_code=400, detail="Form is no longer accepting responses")
            
            # Validate required fields
            for field in form["fields"]:
                if field["required"] and field["id"] not in response_data.responses:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Required field '{field['label']}' is missing"
                    )
            
            # Check if multiple submissions are allowed
            if not form["settings"].get("allow_multiple_submissions", False):
                if response_data.submitted_by_email:
                    existing_response = self.responses_collection.find_one({
                        "form_id": form_id,
                        "submitted_by_email": response_data.submitted_by_email
                    })
                    if existing_response:
                        raise HTTPException(
                            status_code=400, 
                            detail="You have already submitted a response to this form"
                        )
            
            # Create response document
            response_id = str(uuid.uuid4())
            response_doc = {
                "_id": response_id,
                "form_id": form_id,
                "responses": response_data.responses,
                "submitted_by_email": response_data.submitted_by_email,
                "submitted_by_name": response_data.submitted_by_name,
                "wedding_id": form.get("wedding_id"),
                "ip_address": ip_address,
                "user_agent": user_agent,
                "submitted_at": datetime.utcnow(),
                "metadata": {}
            }
            
            # Save response
            result = self.responses_collection.insert_one(response_doc)
            
            if result.inserted_id:
                # Update form submission count
                self.forms_collection.update_one(
                    {"_id": form_id},
                    {"$inc": {"submission_count": 1}}
                )
                
                # Update distribution status if applicable
                if response_data.submitted_by_email:
                    self.distributions_collection.update_one(
                        {"form_id": form_id, "recipient_email": response_data.submitted_by_email},
                        {"$set": {"submitted_at": datetime.utcnow(), "status": "submitted"}}
                    )
                
                return {
                    "id": response_id,
                    "message": form["settings"].get("success_message", "Thank you for your submission!"),
                    "redirect_url": form["settings"].get("redirect_url")
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to save response")
                
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error submitting form response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to submit response: {str(e)}")

    def get_form_responses(self, form_id: str, created_by: str) -> List[Dict[str, Any]]:
        """Get all responses for a form"""
        try:
            # Verify user owns the form
            form = self.get_form(form_id, created_by)
            
            responses = list(self.responses_collection.find(
                {"form_id": form_id}
            ).sort("submitted_at", -1))
            
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

    def get_form_analytics(self, form_id: str, created_by: str) -> Dict[str, Any]:
        """Get analytics for a form"""
        try:
            # Verify user owns the form
            form = self.get_form(form_id, created_by)
            
            # Get response count
            response_count = self.responses_collection.count_documents({"form_id": form_id})
            
            # Get distribution stats
            distributions = list(self.distributions_collection.find({"form_id": form_id}))
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
                "last_response": self._get_last_response_time(form_id)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching form analytics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")

    def _get_last_response_time(self, form_id: str):
        """Get the timestamp of the most recent form response"""
        try:
            responses_collection = self.mongo.get_form_responses_collection()
            last_response = responses_collection.find_one(
                {"form_id": form_id},
                sort=[("submitted_at", -1)]
            )
            return last_response.get("submitted_at") if last_response else None
        except Exception:
            return None

    def _generate_form_email_html(self, form_title: str, form_description: str, 
                                 form_url: str, sender_name: str, custom_message: str) -> str:
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
                    <p>© 2025 Special Wedding. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """