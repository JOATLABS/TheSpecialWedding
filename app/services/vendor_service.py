"""
Vendor Management Service

Comprehensive service for managing vendors, contracts, and payments.
Handles all business logic for the vendor management feature.
"""

import os
import secrets
import string
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from bson import ObjectId
from fastapi import HTTPException, UploadFile
import boto3
from botocore.exceptions import ClientError

from app.core.database import mongo
from app.services.email_service_resend import ResendEmailService
from app.models.vendor import (
    VendorProfile, VendorCategory, ContractStatus, ContractType,
    PaymentMilestoneStatus, QuoteStatus, VendorContract,
    VendorPaymentMilestone, VendorAssignment, ContractTemplate,
    VendorCommunication, PaymentLink, PaymentLinkStatus,
    PayerType, RecipientType
)

logger = logging.getLogger(__name__)


class VendorService:
    """
    Service for managing all vendor-related operations.
    """

    def __init__(self):
        # Collections
        self.vendor_profiles = mongo.db["vendor_profiles"]
        self.contract_templates = mongo.db["contract_templates"]
        self.vendor_contracts = mongo.db["vendor_contracts"]
        self.payment_milestones = mongo.db["vendor_payment_milestones"]
        self.vendor_assignments = mongo.db["vendor_assignments"]
        self.vendor_communications = mongo.db["vendor_communications"]
        self.vendor_quotes = mongo.db["vendor_quotes"]
        self.budget_categories = mongo.db["budget_categories"]
        self.weddings = mongo.db["weddings"]
        self.users = mongo.get_users_collection()
        self.payment_links = mongo.db["payment_links"]
        self.vendor_forms = mongo.db["vendor_forms"]
        self.form_responses = mongo.db["form_responses"]

        # Services
        self.email_service = ResendEmailService()

        # S3 Client for document storage
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        )
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.media_domain = "https://media.thespecialwedding.com"

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _generate_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

    def _generate_contract_number(self) -> str:
        """Generate a unique contract number"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        return f"CON-{timestamp}-{random_suffix}"

    async def _get_wedding(self, wedding_id: str) -> dict:
        """Get wedding by ID"""
        wedding = await self.weddings.find_one({"_id": wedding_id})
        if not wedding:
            # Try with ObjectId
            try:
                wedding = await self.weddings.find_one({"_id": ObjectId(wedding_id)})
            except:
                pass
        return wedding

    async def _log_communication(
        self,
        vendor_profile_id: str,
        type: str,
        content: str,
        created_by: str,
        wedding_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        subject: Optional[str] = None,
        direction: str = "outgoing",
        sent_to: Optional[str] = None,
        attachments: List[Dict] = None
    ):
        """Log a communication with a vendor"""
        comm = {
            "vendor_profile_id": vendor_profile_id,
            "wedding_id": wedding_id,
            "contract_id": contract_id,
            "type": type,
            "subject": subject,
            "content": content,
            "direction": direction,
            "sent_to": sent_to,
            "attachments": attachments or [],
            "created_by": created_by,
            "created_at": datetime.utcnow()
        }
        await self.vendor_communications.insert_one(comm)

    # =========================================================================
    # VENDOR DIRECTORY (Master List)
    # =========================================================================

    async def create_vendor_profile(self, data: dict, created_by: str) -> dict:
        """Create a new vendor in the directory"""
        try:
            vendor = {
                **data,
                "created_by": created_by,
                "weddings_count": 0,
                "total_revenue": 0.0,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await self.vendor_profiles.insert_one(vendor)
            vendor["_id"] = str(result.inserted_id)

            logger.info(f"Created vendor profile: {vendor['business_name']} by {created_by}")
            return vendor

        except Exception as e:
            logger.error(f"Error creating vendor profile: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create vendor: {str(e)}")

    async def get_vendor_profiles(
        self,
        created_by: str,
        category: Optional[str] = None,
        is_preferred: Optional[bool] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[dict]:
        """Get vendor profiles for a planner with filtering"""
        try:
            query = {"created_by": created_by, "is_active": True}

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
                    {"service_description": {"$regex": search, "$options": "i"}}
                ]

            cursor = self.vendor_profiles.find(query).skip(skip).limit(limit).sort("business_name", 1)
            vendors = await cursor.to_list(length=limit)

            for v in vendors:
                v["_id"] = str(v["_id"])

            return vendors

        except Exception as e:
            logger.error(f"Error fetching vendor profiles: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch vendors")

    async def get_vendor_profile(self, vendor_id: str, created_by: str) -> dict:
        """Get a single vendor profile"""
        try:
            vendor = await self.vendor_profiles.find_one({
                "_id": ObjectId(vendor_id),
                "created_by": created_by
            })

            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")

            vendor["_id"] = str(vendor["_id"])
            return vendor

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching vendor profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch vendor")

    async def update_vendor_profile(self, vendor_id: str, data: dict, created_by: str) -> dict:
        """Update a vendor profile"""
        try:
            # Remove None values
            update_data = {k: v for k, v in data.items() if v is not None}
            update_data["updated_at"] = datetime.utcnow()

            result = await self.vendor_profiles.find_one_and_update(
                {"_id": ObjectId(vendor_id), "created_by": created_by},
                {"$set": update_data},
                return_document=True
            )

            if not result:
                raise HTTPException(status_code=404, detail="Vendor not found")

            result["_id"] = str(result["_id"])
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating vendor profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update vendor")

    async def delete_vendor_profile(self, vendor_id: str, created_by: str) -> dict:
        """Soft delete a vendor profile"""
        try:
            result = await self.vendor_profiles.find_one_and_update(
                {"_id": ObjectId(vendor_id), "created_by": created_by},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
                return_document=True
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
                {"$sort": {"_id": 1}}
            ]
            result = await self.vendor_profiles.aggregate(pipeline).to_list(length=100)
            return [r["_id"] for r in result if r["_id"]]

        except Exception as e:
            logger.error(f"Error getting vendor categories: {str(e)}")
            return []

    # =========================================================================
    # VENDOR ASSIGNMENT (Link to Wedding)
    # =========================================================================

    async def assign_vendor_to_wedding(
        self,
        vendor_profile_id: str,
        wedding_id: str,
        created_by: str,
        budget_category_id: Optional[str] = None,
        service_notes: Optional[str] = None
    ) -> dict:
        """Assign a vendor from directory to a wedding"""
        try:
            # Get vendor profile
            vendor = await self.vendor_profiles.find_one({"_id": ObjectId(vendor_profile_id)})
            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")

            # Check if already assigned
            existing = await self.vendor_assignments.find_one({
                "vendor_profile_id": vendor_profile_id,
                "wedding_id": wedding_id
            })
            if existing:
                raise HTTPException(status_code=400, detail="Vendor already assigned to this wedding")

            assignment = {
                "wedding_id": wedding_id,
                "vendor_profile_id": vendor_profile_id,
                "budget_category_id": budget_category_id,
                "status": "inquiry",
                "vendor_name": vendor["business_name"],
                "vendor_email": vendor["email"],
                "service_category": vendor["service_category"],
                "quote_ids": [],
                "contract_id": None,
                "service_notes": service_notes,
                "quoted_amount": None,
                "contracted_amount": None,
                "paid_amount": 0.0,
                "created_by": created_by,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await self.vendor_assignments.insert_one(assignment)
            assignment["_id"] = str(result.inserted_id)

            # Update vendor's wedding count
            await self.vendor_profiles.update_one(
                {"_id": ObjectId(vendor_profile_id)},
                {
                    "$inc": {"weddings_count": 1},
                    "$set": {"last_used_at": datetime.utcnow()}
                }
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
            raise HTTPException(status_code=500, detail="Failed to fetch wedding vendors")

    async def update_assignment_status(
        self,
        assignment_id: str,
        status: str,
        created_by: str
    ) -> dict:
        """Update vendor assignment status"""
        valid_statuses = ["inquiry", "quoted", "contracted", "confirmed", "completed", "cancelled"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

        try:
            result = await self.vendor_assignments.find_one_and_update(
                {"_id": ObjectId(assignment_id)},
                {"$set": {"status": status, "updated_at": datetime.utcnow()}},
                return_document=True
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
                **data,
                "created_by": created_by,
                "is_system_template": False,
                "is_public": False,
                "is_active": True,
                "usage_count": 0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
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
        include_system: bool = True
    ) -> List[dict]:
        """Get contract templates available to planner"""
        try:
            or_conditions: List[Dict[str, Any]] = [{"created_by": created_by}]
            if include_system:
                or_conditions.append({"is_system_template": True})

            query = {
                "$or": or_conditions,
                "is_active": True
            }

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
            template = await self.contract_templates.find_one({"_id": ObjectId(template_id)})
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
            "{{contract_date}}": datetime.utcnow().strftime("%B %d, %Y"),
            "{{contract_number}}": data.get("contract_number", ""),
        }

        for placeholder, value in placeholders.items():
            content = content.replace(placeholder, str(value) if value else "")

        return content

    async def create_contract(
        self,
        wedding_id: str,
        vendor_profile_id: str,
        created_by: str,
        template_id: Optional[str] = None,
        quote_id: Optional[str] = None,
        total_amount: float = 0,
        custom_sections: Optional[List[Dict]] = None,
        deposit_percentage: Optional[float] = None,
        service_date: Optional[datetime] = None,
        service_location: Optional[str] = None
    ) -> dict:
        """Create a new vendor contract"""
        try:
            # Get vendor profile
            vendor = await self.vendor_profiles.find_one({"_id": ObjectId(vendor_profile_id)})
            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")

            # Get wedding
            wedding = await self._get_wedding(wedding_id)
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
                "service_category": vendor["service_category"],
                "total_amount": total_amount,
                "deposit_amount": (total_amount * deposit_percentage / 100) if deposit_percentage else 0,
                "planner_name": f"{planner.get('first_name', '')} {planner.get('last_name', '')}".strip() if planner else "",
                "planner_email": created_by,
                "planner_company": planner.get("company_name", "") if planner else "",
                "contract_number": self._generate_contract_number()
            }

            # Build contract sections
            sections = []
            terms_and_conditions = None
            cancellation_policy = None

            if template_id:
                template = await self.get_contract_template(template_id)
                for section in template.get("sections", []):
                    sections.append({
                        "id": section.get("id", str(ObjectId())),
                        "title": section["title"],
                        "content": self._populate_placeholders(section["content"], placeholder_data),
                        "order": section.get("order", 0)
                    })
                terms_and_conditions = self._populate_placeholders(
                    template.get("terms_and_conditions", ""), placeholder_data
                )
                cancellation_policy = self._populate_placeholders(
                    template.get("cancellation_policy", ""), placeholder_data
                )

                # Increment template usage
                await self.contract_templates.update_one(
                    {"_id": ObjectId(template_id)},
                    {"$inc": {"usage_count": 1}}
                )

            # Add custom sections
            if custom_sections:
                for cs in custom_sections:
                    sections.append({
                        "id": str(ObjectId()),
                        "title": cs.get("title", "Additional Terms"),
                        "content": self._populate_placeholders(cs.get("content", ""), placeholder_data),
                        "order": cs.get("order", len(sections))
                    })

            # Calculate deposit
            deposit_amount = None
            deposit_due_date = None
            if deposit_percentage and total_amount:
                deposit_amount = total_amount * deposit_percentage / 100
                # Deposit due in 7 days
                deposit_due_date = datetime.utcnow() + timedelta(days=7)

            contract = {
                "wedding_id": wedding_id,
                "vendor_profile_id": vendor_profile_id,
                "vendor_quote_id": quote_id,
                "budget_category_id": None,
                "template_id": template_id,
                "vendor_name": vendor["business_name"],
                "vendor_email": vendor["email"],
                "vendor_phone": vendor.get("phone"),
                "vendor_address": vendor.get("address"),
                "service_category": vendor["service_category"],
                "contract_title": f"{vendor['service_category'].replace('_', ' ').title()} Services Contract",
                "contract_number": placeholder_data["contract_number"],
                "sections": sections,
                "terms_and_conditions": terms_and_conditions,
                "cancellation_policy": cancellation_policy,
                "total_amount": total_amount,
                "currency": "USD",
                "deposit_amount": deposit_amount,
                "deposit_due_date": deposit_due_date,
                "status": ContractStatus.DRAFT.value,
                "access_token": self._generate_token(),
                "token_expires_at": datetime.utcnow() + timedelta(days=30),
                "service_date": service_date,
                "service_location": service_location,
                "created_by": created_by,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await self.vendor_contracts.insert_one(contract)
            contract["_id"] = str(result.inserted_id)

            # Update quote if converting from quote
            if quote_id:
                await self.vendor_quotes.update_one(
                    {"_id": ObjectId(quote_id)},
                    {"$set": {"status": QuoteStatus.CONVERTED.value, "updated_at": datetime.utcnow()}}
                )

            logger.info(f"Created contract {contract['contract_number']} for vendor {vendor['business_name']}")
            return contract

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating contract: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create contract: {str(e)}")

    async def get_contracts(
        self,
        created_by: str,
        wedding_id: Optional[str] = None,
        vendor_profile_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[dict]:
        """Get contracts for a planner"""
        try:
            query = {"created_by": created_by}

            if wedding_id:
                query["wedding_id"] = wedding_id
            if vendor_profile_id:
                query["vendor_profile_id"] = vendor_profile_id
            if status:
                query["status"] = status

            cursor = self.vendor_contracts.find(query).skip(skip).limit(limit).sort("created_at", -1)
            contracts = await cursor.to_list(length=limit)

            for c in contracts:
                c["_id"] = str(c["_id"])

            return contracts

        except Exception as e:
            logger.error(f"Error fetching contracts: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch contracts")

    async def get_contract(self, contract_id: str) -> dict:
        """Get a specific contract"""
        try:
            contract = await self.vendor_contracts.find_one({"_id": ObjectId(contract_id)})
            if not contract:
                raise HTTPException(status_code=404, detail="Contract not found")

            contract["_id"] = str(contract["_id"])
            return contract

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching contract: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch contract")

    async def get_contract_by_token(self, contract_id: str, token: str) -> dict:
        """Get contract for vendor access (public endpoint)"""
        try:
            contract = await self.vendor_contracts.find_one({
                "_id": ObjectId(contract_id),
                "access_token": token
            })

            if not contract:
                raise HTTPException(status_code=404, detail="Contract not found or invalid token")

            # Check expiration
            if contract.get("token_expires_at") and contract["token_expires_at"] < datetime.utcnow():
                raise HTTPException(status_code=403, detail="Contract link has expired")

            # Mark as viewed if first time
            if not contract.get("viewed_at"):
                await self.vendor_contracts.update_one(
                    {"_id": ObjectId(contract_id)},
                    {"$set": {"viewed_at": datetime.utcnow(), "status": ContractStatus.VIEWED.value}}
                )
                contract["viewed_at"] = datetime.utcnow()
                contract["status"] = ContractStatus.VIEWED.value

            contract["_id"] = str(contract["_id"])

            # Remove sensitive fields for vendor view
            contract.pop("access_token", None)
            contract.pop("internal_notes", None)

            return contract

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching contract by token: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch contract")

    async def send_contract(
        self,
        contract_id: str,
        created_by: str,
        message: Optional[str] = None,
        cc_emails: Optional[List[str]] = None
    ) -> dict:
        """Send contract to vendor via email"""
        try:
            contract = await self.get_contract(contract_id)

            if contract["status"] not in [ContractStatus.DRAFT.value, ContractStatus.PENDING_REVIEW.value]:
                raise HTTPException(status_code=400, detail="Contract has already been sent")

            # Get wedding info
            wedding = await self._get_wedding(contract["wedding_id"])

            # Generate contract link
            base_url = os.getenv("FRONTEND_URL", "http://localhost:3001")
            contract_link = f"{base_url}/vendor-contract/{contract_id}?token={contract['access_token']}"

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
                        <p>Dear {contract['vendor_name']},</p>

                        <p>A contract has been prepared for your services for the wedding of <strong>{wedding.get('couple_names', 'our clients')}</strong>.</p>

                        {f'<p>{message}</p>' if message else ''}

                        <div class="details">
                            <h3>Contract Details:</h3>
                            <p><strong>Contract:</strong> {contract['contract_title']}</p>
                            <p><strong>Contract #:</strong> {contract.get('contract_number', 'N/A')}</p>
                            <p><strong>Service:</strong> {contract['service_category'].replace('_', ' ').title()}</p>
                            <p><strong>Total Amount:</strong> ${contract['total_amount']:,.2f}</p>
                            {f"<p><strong>Deposit Required:</strong> ${contract['deposit_amount']:,.2f}</p>" if contract.get('deposit_amount') else ''}
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

            # Send email
            recipients = [contract["vendor_email"]]
            if cc_emails:
                recipients.extend(cc_emails)

            email_result = await self.email_service.send_email(
                to_email=contract["vendor_email"],
                subject=subject,
                html_content=html_content,
                from_name="Wedding Planning Team"
            )

            if email_result.get("success"):
                # Update contract status
                await self.vendor_contracts.update_one(
                    {"_id": ObjectId(contract_id)},
                    {
                        "$set": {
                            "status": ContractStatus.SENT.value,
                            "sent_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                # Log communication
                await self._log_communication(
                    vendor_profile_id=contract["vendor_profile_id"],
                    type="contract_sent",
                    content=f"Contract sent: {contract['contract_title']}",
                    created_by=created_by,
                    wedding_id=contract["wedding_id"],
                    contract_id=contract_id,
                    subject=subject,
                    sent_to=contract["vendor_email"]
                )

                return {"message": "Contract sent successfully", "sent_to": contract["vendor_email"]}
            else:
                raise HTTPException(status_code=500, detail="Failed to send email")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending contract: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to send contract: {str(e)}")

    async def sign_contract(
        self,
        contract_id: str,
        token: str,
        signer_name: str,
        signer_email: str,
        signature_ip: Optional[str] = None
    ) -> dict:
        """Sign a contract (vendor action)"""
        try:
            contract = await self.vendor_contracts.find_one({
                "_id": ObjectId(contract_id),
                "access_token": token
            })

            if not contract:
                raise HTTPException(status_code=404, detail="Contract not found or invalid token")

            if contract["status"] == ContractStatus.SIGNED.value:
                raise HTTPException(status_code=400, detail="Contract has already been signed")

            if contract["status"] not in [ContractStatus.SENT.value, ContractStatus.VIEWED.value]:
                raise HTTPException(status_code=400, detail="Contract cannot be signed in current state")

            # Update contract
            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "status": ContractStatus.SIGNED.value,
                        "signed_at": datetime.utcnow(),
                        "signed_by_name": signer_name,
                        "signed_by_email": signer_email,
                        "signature_ip": signature_ip,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # Update assignment status
            if contract.get("vendor_profile_id"):
                await self.vendor_assignments.update_one(
                    {
                        "vendor_profile_id": contract["vendor_profile_id"],
                        "wedding_id": contract["wedding_id"]
                    },
                    {
                        "$set": {
                            "status": "contracted",
                            "contract_id": contract_id,
                            "contracted_amount": contract["total_amount"],
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

            # Send notification to planner
            planner_email = contract["created_by"]
            subject = f"Contract Signed: {contract['vendor_name']}"
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Contract Signed!</h2>
                <p>Great news! {contract['vendor_name']} has signed the contract.</p>
                <div style="background: #f3f4f6; padding: 15px; border-radius: 6px;">
                    <p><strong>Contract:</strong> {contract['contract_title']}</p>
                    <p><strong>Signed by:</strong> {signer_name}</p>
                    <p><strong>Signed at:</strong> {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}</p>
                </div>
                <p>Log in to your dashboard to view the signed contract.</p>
            </body>
            </html>
            """

            await self.email_service.send_email(
                to_email=planner_email,
                subject=subject,
                html_content=html_content,
                from_name="Wedding Platform"
            )

            return {
                "message": "Contract signed successfully",
                "signed_at": datetime.utcnow().isoformat()
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
        self,
        contract_id: str,
        data: dict,
        updated_by: str
    ) -> dict:
        """Update a contract (only draft contracts can be modified)"""
        try:
            contract = await self.get_contract(contract_id)

            if contract["status"] not in [ContractStatus.DRAFT.value, ContractStatus.PENDING_REVIEW.value]:
                raise HTTPException(
                    status_code=400,
                    detail="Contract cannot be modified after it has been sent"
                )

            # Fields that can be updated
            allowed_fields = [
                "contract_title", "total_amount", "deposit_amount", "deposit_due_date",
                "terms_and_conditions", "cancellation_policy", "custom_clauses",
                "service_date", "service_start_time", "service_end_time", "service_location",
                "internal_notes", "sections"
            ]

            update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
            update_data["updated_at"] = datetime.utcnow()

            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": update_data}
            )

            return await self.get_contract(contract_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating contract: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update contract")

    async def update_contract_sections(
        self,
        contract_id: str,
        sections: List[Dict],
        updated_by: str
    ) -> dict:
        """Update contract sections - add, modify, or remove sections"""
        try:
            contract = await self.get_contract(contract_id)

            if contract["status"] not in [ContractStatus.DRAFT.value, ContractStatus.PENDING_REVIEW.value]:
                raise HTTPException(
                    status_code=400,
                    detail="Contract sections cannot be modified after it has been sent"
                )

            # Validate sections
            processed_sections = []
            for i, section in enumerate(sections):
                processed_sections.append({
                    "id": section.get("id", str(ObjectId())),
                    "title": section.get("title", f"Section {i + 1}"),
                    "content": section.get("content", ""),
                    "order": section.get("order", i)
                })

            # Sort by order
            processed_sections.sort(key=lambda x: x["order"])

            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": {"sections": processed_sections, "updated_at": datetime.utcnow()}}
            )

            return await self.get_contract(contract_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating contract sections: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update contract sections")

    # =========================================================================
    # FORM DATA INTEGRATION
    # =========================================================================

    async def get_form_data_for_contract(self, contract_id: str) -> dict:
        """
        Get vendor form submissions that can be used to populate contract fields.
        Looks for form submissions from the same vendor email.
        """
        try:
            contract = await self.get_contract(contract_id)
            vendor_email = contract.get("vendor_email")
            wedding_id = contract.get("wedding_id")

            if not vendor_email:
                return {"submissions": [], "message": "No vendor email in contract"}

            # Find vendor form submissions for this vendor
            vendor_submissions = await mongo.db["vendor_submissions"].find({
                "vendor_email": vendor_email
            }).to_list(length=20)

            # Also check vendor_forms that have been submitted
            vendor_forms = await mongo.db["vendor_forms"].find({
                "vendor_email": vendor_email,
                "status": "submitted"
            }).to_list(length=20)

            submissions = []
            for sub in vendor_submissions:
                sub["_id"] = str(sub["_id"])
                sub["source"] = "vendor_submission"
                submissions.append(sub)

            for form in vendor_forms:
                if form.get("submission_data"):
                    form["_id"] = str(form["_id"])
                    form["source"] = "vendor_form"
                    submissions.append(form)

            # Extract available fields that could populate contract
            available_fields = {}
            for sub in submissions:
                data = sub.get("submission_data", {})
                if isinstance(data, dict):
                    for key, value in data.items():
                        if value and isinstance(value, (str, int, float)):
                            available_fields[key] = {
                                "value": value,
                                "source_id": sub["_id"],
                                "source_type": sub.get("source", "unknown")
                            }

            return {
                "submissions": submissions,
                "available_fields": available_fields,
                "vendor_email": vendor_email,
                "suggested_mappings": self._suggest_field_mappings(available_fields)
            }

        except Exception as e:
            logger.error(f"Error getting form data for contract: {str(e)}")
            return {"submissions": [], "available_fields": {}, "error": str(e)}

    def _suggest_field_mappings(self, available_fields: dict) -> dict:
        """Suggest mappings from form fields to contract placeholders"""
        mappings = {}

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
                if pattern in field_lower:
                    mappings[field_name] = placeholder
                    break

        return mappings

    async def apply_form_data_to_contract(
        self,
        contract_id: str,
        form_submission_id: str,
        field_mappings: Optional[Dict] = None,
        applied_by: Optional[str] = None
    ) -> dict:
        """Apply data from a vendor form submission to populate contract sections"""
        try:
            contract = await self.get_contract(contract_id)

            if contract["status"] not in [ContractStatus.DRAFT.value, ContractStatus.PENDING_REVIEW.value]:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot apply form data to a contract that has been sent"
                )

            # Try to find the submission in vendor_submissions first
            submission = await mongo.db["vendor_submissions"].find_one(
                {"_id": ObjectId(form_submission_id)}
            )

            if not submission:
                # Try vendor_forms
                submission = await mongo.db["vendor_forms"].find_one(
                    {"_id": ObjectId(form_submission_id)}
                )

            if not submission:
                raise HTTPException(status_code=404, detail="Form submission not found")

            submission_data = submission.get("submission_data", {})
            if not isinstance(submission_data, dict):
                raise HTTPException(status_code=400, detail="Invalid submission data format")

            # Build placeholder replacements
            replacements = {}

            # Default mappings from submission data
            for key, value in submission_data.items():
                if value and isinstance(value, (str, int, float)):
                    placeholder = f"{{{{{key}}}}}"
                    replacements[placeholder] = str(value)

            # Apply custom field mappings if provided
            if field_mappings:
                for field_name, placeholder in field_mappings.items():
                    if field_name in submission_data:
                        replacements[placeholder] = str(submission_data[field_name])

            # Apply replacements to contract sections
            updated_sections = []
            for section in contract.get("sections", []):
                new_content = section.get("content", "")
                for placeholder, value in replacements.items():
                    new_content = new_content.replace(placeholder, value)
                updated_sections.append({
                    **section,
                    "content": new_content
                })

            # Also apply to terms and conditions
            terms = contract.get("terms_and_conditions", "")
            for placeholder, value in replacements.items():
                terms = terms.replace(placeholder, value)

            # Update contract
            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "sections": updated_sections,
                        "terms_and_conditions": terms,
                        "form_data_applied": True,
                        "form_submission_id": form_submission_id,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            return {
                "message": "Form data applied to contract successfully",
                "fields_applied": list(replacements.keys()),
                "contract_id": contract_id
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error applying form data to contract: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to apply form data")

    # =========================================================================
    # PAYMENT MILESTONES
    # =========================================================================

    async def create_payment_milestones(
        self,
        contract_id: str,
        milestones: List[Dict],
        created_by: str
    ) -> List[dict]:
        """Create payment milestones for a contract"""
        try:
            contract = await self.get_contract(contract_id)

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
                    "due_date": m["due_date"] if isinstance(m["due_date"], datetime) else datetime.fromisoformat(m["due_date"]),
                    "days_before_event": m.get("days_before_event"),
                    "status": PaymentMilestoneStatus.PENDING.value,
                    "paid_amount": 0.0,
                    "vendor_name": contract["vendor_name"],
                    "vendor_email": contract["vendor_email"],
                    "created_by": created_by,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }

                result = await self.payment_milestones.insert_one(milestone)
                milestone["_id"] = str(result.inserted_id)
                created_milestones.append(milestone)

            return created_milestones

        except Exception as e:
            logger.error(f"Error creating milestones: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create payment milestones")

    async def get_payment_milestones(
        self,
        contract_id: Optional[str] = None,
        wedding_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[dict]:
        """Get payment milestones"""
        try:
            query = {}
            if contract_id:
                query["contract_id"] = contract_id
            if wedding_id:
                query["wedding_id"] = wedding_id
            if status:
                query["status"] = status

            cursor = self.payment_milestones.find(query).sort("due_date", 1)
            milestones = await cursor.to_list(length=100)

            for m in milestones:
                m["_id"] = str(m["_id"])
                # Check if overdue
                if m["status"] == PaymentMilestoneStatus.PENDING.value:
                    if m["due_date"] < datetime.utcnow():
                        m["status"] = PaymentMilestoneStatus.OVERDUE.value

            return milestones

        except Exception as e:
            logger.error(f"Error fetching milestones: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch milestones")

    async def record_payment(
        self,
        milestone_id: str,
        amount: float,
        payment_method: str,
        created_by: str,
        payment_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        receipt_url: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None
    ) -> dict:
        """Record a payment against a milestone"""
        try:
            milestone = await self.payment_milestones.find_one({"_id": ObjectId(milestone_id)})
            if not milestone:
                raise HTTPException(status_code=404, detail="Milestone not found")

            new_paid_amount = milestone.get("paid_amount", 0) + amount

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
                "paid_at": payment_date or datetime.utcnow(),
                "notes": notes,
                "receipt_url": receipt_url,
                "updated_at": datetime.utcnow()
            }

            if stripe_payment_intent_id:
                update_data["stripe_payment_intent_id"] = stripe_payment_intent_id

            await self.payment_milestones.update_one(
                {"_id": ObjectId(milestone_id)},
                {"$set": update_data}
            )

            # Update assignment paid amount
            if milestone.get("vendor_profile_id") and milestone.get("wedding_id"):
                await self.vendor_assignments.update_one(
                    {
                        "vendor_profile_id": milestone["vendor_profile_id"],
                        "wedding_id": milestone["wedding_id"]
                    },
                    {"$inc": {"paid_amount": amount}}
                )

            # Update vendor profile total revenue
            if milestone.get("vendor_profile_id"):
                await self.vendor_profiles.update_one(
                    {"_id": ObjectId(milestone["vendor_profile_id"])},
                    {"$inc": {"total_revenue": amount}}
                )

            # Update budget category if linked
            if milestone.get("budget_category_id"):
                await self.budget_categories.update_one(
                    {"_id": ObjectId(milestone["budget_category_id"])},
                    {"$inc": {"actual_spent": amount}}
                )

            updated = await self.payment_milestones.find_one({"_id": ObjectId(milestone_id)})
            updated["_id"] = str(updated["_id"])

            return updated

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error recording payment: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to record payment")

    # =========================================================================
    # FILE STORAGE
    # =========================================================================

    async def upload_contract_document(
        self,
        contract_id: str,
        file: UploadFile,
        document_type: str = "signed"
    ) -> dict:
        """Upload a contract document to S3"""
        try:
            # Generate unique key
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"contracts/{contract_id}/{document_type}_{timestamp}_{file.filename}"

            # Upload to S3
            file_content = await file.read()
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=file_content,
                ContentType=file.content_type
            )

            file_url = f"{self.media_domain}/{filename}"

            # Update contract with document URL
            field = f"{document_type}_document_url"
            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": {field: file_url, "updated_at": datetime.utcnow()}}
            )

            return {"url": file_url, "key": filename}

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
        self,
        vendor_profile_id: str,
        wedding_id: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        """Get communication history with a vendor"""
        try:
            query = {"vendor_profile_id": vendor_profile_id}
            if wedding_id:
                query["wedding_id"] = wedding_id

            cursor = self.vendor_communications.find(query).sort("created_at", -1).limit(limit)
            communications = await cursor.to_list(length=limit)

            for c in communications:
                c["_id"] = str(c["_id"])

            return communications

        except Exception as e:
            logger.error(f"Error fetching communications: {str(e)}")
            return []

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
        created_by: str,
        deposit_amount: Optional[float] = None,
        service_date: Optional[datetime] = None,
        service_location: Optional[str] = None,
        notes: Optional[str] = None
    ) -> dict:
        """
        Create a contract by uploading an existing PDF.
        The planner uploads their own contract PDF instead of using templates.
        """
        try:
            # Get vendor profile
            vendor = await self.get_vendor_profile(vendor_profile_id, created_by)
            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")

            # Get wedding
            wedding = await self._get_wedding(wedding_id)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Validate file is PDF
            if not file.content_type or 'pdf' not in file.content_type.lower():
                raise HTTPException(status_code=400, detail="File must be a PDF")

            # Read file content
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:  # 10MB limit
                raise HTTPException(status_code=400, detail="File too large. Maximum 10MB")

            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            safe_filename = f"contracts/{wedding_id}/{timestamp}_{file.filename}"

            # Upload to S3
            try:
                self.s3.put_object(
                    Bucket=self.bucket_name,
                    Key=safe_filename,
                    Body=content,
                    ContentType="application/pdf"
                )
                pdf_url = f"{self.media_domain}/{safe_filename}"
            except ClientError as e:
                logger.error(f"S3 upload error: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to upload contract PDF")

            # Create contract record
            contract_doc = {
                "wedding_id": wedding_id,
                "vendor_profile_id": vendor_profile_id,
                "vendor_name": vendor["business_name"],
                "vendor_email": vendor["email"],
                "vendor_phone": vendor.get("phone"),
                "vendor_address": vendor.get("address"),
                "service_category": vendor["service_category"],
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
                "access_token": self._generate_token(),
                "token_expires_at": datetime.utcnow() + timedelta(days=30),
                "service_date": service_date,
                "service_location": service_location,
                "internal_notes": notes,
                "created_by": created_by,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "form_submission_ids": [],
                "form_data_mappings": {}
            }

            result = await self.vendor_contracts.insert_one(contract_doc)
            contract_doc["_id"] = str(result.inserted_id)

            logger.info(f"Created PDF contract {contract_doc['_id']} for vendor {vendor_profile_id}")
            return contract_doc

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading contract PDF: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload contract: {str(e)}")

    # =========================================================================
    # FORM DATA INTEGRATION
    # =========================================================================

    async def get_form_data_for_contract(
        self,
        vendor_email: str,
        wedding_id: str,
        planner_email: str
    ) -> dict:
        """
        Get form submissions from a vendor that can be used to populate contract fields.
        Returns structured data from vendor forms and generic forms.
        """
        try:
            # Find form submissions by this vendor email for this wedding
            vendor_form_submissions = await self.vendor_forms.find({
                "wedding_id": wedding_id,
                "vendor_email": {"$regex": vendor_email, "$options": "i"},
                "submitted_at": {"$ne": None}
            }).to_list(length=100)

            # Also check form_responses for generic forms sent to this email
            form_responses = await self.form_responses.find({
                "recipient_email": {"$regex": vendor_email, "$options": "i"},
                "wedding_id": wedding_id
            }).to_list(length=100)

            # Extract useful fields from submissions
            extracted_data = {
                "vendor_submissions": [],
                "available_fields": {},
                "suggested_contract_fields": {}
            }

            # Process vendor form submissions
            for submission in vendor_form_submissions:
                sub_data = submission.get("submission_data", {})
                extracted_data["vendor_submissions"].append({
                    "_id": str(submission["_id"]),
                    "form_name": submission.get("form_name", "Vendor Form"),
                    "submitted_at": submission.get("submitted_at"),
                    "data": sub_data
                })

                # Extract common useful fields
                for key, value in sub_data.items():
                    if value and isinstance(value, (str, int, float)):
                        field_key = key.lower().replace(" ", "_")
                        extracted_data["available_fields"][field_key] = {
                            "value": value,
                            "source": "vendor_form",
                            "source_id": str(submission["_id"]),
                            "original_key": key
                        }

            # Process generic form responses
            for response in form_responses:
                resp_data = response.get("responses", {})
                extracted_data["vendor_submissions"].append({
                    "_id": str(response["_id"]),
                    "form_name": response.get("form_name", "Form Response"),
                    "submitted_at": response.get("submitted_at"),
                    "data": resp_data
                })

                for key, value in resp_data.items():
                    if value and isinstance(value, (str, int, float)):
                        field_key = key.lower().replace(" ", "_")
                        if field_key not in extracted_data["available_fields"]:
                            extracted_data["available_fields"][field_key] = {
                                "value": value,
                                "source": "form_response",
                                "source_id": str(response["_id"]),
                                "original_key": key
                            }

            # Suggest mappings for common contract placeholders
            placeholder_mappings = {
                "package_name": ["package", "package_name", "service_package", "selected_package"],
                "package_price": ["price", "package_price", "total_price", "quoted_price", "rate"],
                "services_included": ["services", "included_services", "deliverables", "what_is_included"],
                "hours_of_coverage": ["hours", "coverage_hours", "service_hours", "time"],
                "equipment": ["equipment", "equipment_list", "gear", "tools"],
                "availability": ["availability", "available_dates", "is_available"],
                "portfolio": ["portfolio", "portfolio_link", "website", "samples"],
                "special_requirements": ["requirements", "special_requirements", "notes", "additional_info"],
                "cancellation_policy": ["cancellation", "cancellation_policy", "refund_policy"],
            }

            for placeholder, possible_keys in placeholder_mappings.items():
                for key in possible_keys:
                    if key in extracted_data["available_fields"]:
                        extracted_data["suggested_contract_fields"][placeholder] = {
                            "value": extracted_data["available_fields"][key]["value"],
                            "source_field": key
                        }
                        break

            return extracted_data

        except Exception as e:
            logger.error(f"Error getting form data for contract: {str(e)}")
            return {"vendor_submissions": [], "available_fields": {}, "suggested_contract_fields": {}}

    async def apply_form_data_to_contract(
        self,
        contract_id: str,
        form_data_mappings: Dict[str, Any],
        planner_email: str
    ) -> dict:
        """
        Apply form data to a contract's sections.
        Replaces placeholders with actual values from form submissions.
        """
        try:
            contract = await self.vendor_contracts.find_one({"_id": ObjectId(contract_id)})
            if not contract:
                raise HTTPException(status_code=404, detail="Contract not found")

            # Update sections with mapped values
            updated_sections = []
            for section in contract.get("sections", []):
                content = section.get("content", "")

                # Replace placeholders with form data
                for placeholder, data in form_data_mappings.items():
                    value = data.get("value", "") if isinstance(data, dict) else str(data)
                    content = content.replace(f"{{{{{placeholder}}}}}", str(value))

                updated_sections.append({
                    **section,
                    "content": content
                })

            # Update contract
            await self.vendor_contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "sections": updated_sections,
                        "form_data_mappings": form_data_mappings,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            contract["_id"] = str(contract["_id"])
            contract["sections"] = updated_sections
            contract["form_data_mappings"] = form_data_mappings

            return contract

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error applying form data to contract: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to apply form data: {str(e)}")

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
        payer_phone: Optional[str] = None
    ) -> dict:
        """
        Create a payment link that can be sent to vendors or couples.
        Integrates with Stripe for payment processing.
        """
        try:
            import stripe
            from app.core.settings import settings

            if not settings.stripe_enabled:
                raise HTTPException(status_code=503, detail="Payment processing not available")

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
                        "created_by": created_by
                    },
                    after_completion={
                        "type": "redirect",
                        "redirect": {"url": f"{settings.frontend_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"}
                    }
                )

                stripe_payment_link_id = payment_link.id
                stripe_payment_link_url = payment_link.url

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error creating payment link: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Payment link creation failed: {str(e)}")

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
                "stripe_payment_link_id": stripe_payment_link_id,
                "stripe_payment_link_url": stripe_payment_link_url,
                "status": PaymentLinkStatus.DRAFT.value,
                "email_subject": email_subject,
                "email_message": email_message,
                "access_token": self._generate_token(),
                "created_by": created_by,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "reminder_sent_count": 0
            }

            result = await self.payment_links.insert_one(payment_link_doc)
            payment_link_doc["_id"] = str(result.inserted_id)

            logger.info(f"Created payment link {payment_link_doc['_id']} for {amount} {currency}")
            return payment_link_doc

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating payment link: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create payment link: {str(e)}")

    async def send_payment_link(
        self,
        payment_link_id: str,
        planner_email: str,
        custom_message: Optional[str] = None
    ) -> dict:
        """
        Send a payment link to the payer via email.
        """
        try:
            # Get payment link
            payment_link = await self.payment_links.find_one({"_id": ObjectId(payment_link_id)})
            if not payment_link:
                raise HTTPException(status_code=404, detail="Payment link not found")

            # Get planner info for from name
            planner = await self.users.find_one({"email": planner_email})
            planner_name = planner.get("name", "Your Wedding Planner") if planner else "Your Wedding Planner"

            # Build email
            subject = payment_link.get("email_subject") or f"Payment Request: {payment_link['description']}"
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
                        <p>Dear {payment_link['payer_name']},</p>
                        {message}
                        <p>You have a payment request for:</p>
                        <p><strong>{payment_link['description']}</strong></p>
                        <div class="amount">${payment_link['amount']:,.2f} {payment_link['currency']}</div>
                        <p>Payment to: <strong>{payment_link['recipient_name']}</strong></p>
                        {"<p><strong>Due Date:</strong> " + payment_link['due_date'].strftime('%B %d, %Y') + "</p>" if payment_link.get('due_date') else ""}
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
                html_content=email_html
            )

            # Update payment link status
            await self.payment_links.update_one(
                {"_id": ObjectId(payment_link_id)},
                {
                    "$set": {
                        "status": PaymentLinkStatus.SENT.value,
                        "sent_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Sent payment link {payment_link_id} to {payment_link['payer_email']}")
            return {"message": "Payment link sent", "sent_to": payment_link["payer_email"]}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending payment link: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to send payment link: {str(e)}")

    async def get_payment_links(
        self,
        planner_email: str,
        wedding_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[dict]:
        """Get payment links created by a planner"""
        try:
            query = {"created_by": planner_email}
            if wedding_id:
                query["wedding_id"] = wedding_id
            if status:
                query["status"] = status

            cursor = self.payment_links.find(query).sort("created_at", -1).skip(skip).limit(limit)
            links = await cursor.to_list(length=limit)

            for link in links:
                link["_id"] = str(link["_id"])

            return links

        except Exception as e:
            logger.error(f"Error fetching payment links: {str(e)}")
            return []

    async def handle_payment_link_webhook(
        self,
        stripe_event: dict
    ) -> dict:
        """
        Handle Stripe webhook for payment link completion.
        Updates payment link status and records payment.
        """
        try:
            event_type = stripe_event.get("type")
            data = stripe_event.get("data", {}).get("object", {})

            if event_type == "checkout.session.completed":
                # Find payment link by checkout session
                payment_link_id = data.get("metadata", {}).get("payment_link_id")
                if not payment_link_id:
                    # Try to find by Stripe payment link ID
                    stripe_pl_id = data.get("payment_link")
                    if stripe_pl_id:
                        payment_link = await self.payment_links.find_one({
                            "stripe_payment_link_id": stripe_pl_id
                        })
                        if payment_link:
                            payment_link_id = str(payment_link["_id"])

                if payment_link_id:
                    await self.payment_links.update_one(
                        {"_id": ObjectId(payment_link_id)},
                        {
                            "$set": {
                                "status": PaymentLinkStatus.PAID.value,
                                "paid_at": datetime.utcnow(),
                                "stripe_checkout_session_id": data.get("id"),
                                "stripe_payment_intent_id": data.get("payment_intent"),
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )

                    # Update related milestone if exists
                    payment_link = await self.payment_links.find_one({"_id": ObjectId(payment_link_id)})
                    if payment_link and payment_link.get("milestone_id"):
                        await self.payment_milestones.update_one(
                            {"_id": ObjectId(payment_link["milestone_id"])},
                            {
                                "$set": {
                                    "status": PaymentMilestoneStatus.PAID.value,
                                    "paid_amount": payment_link["amount"],
                                    "paid_at": datetime.utcnow(),
                                    "payment_method": "stripe",
                                    "updated_at": datetime.utcnow()
                                }
                            }
                        )

                    logger.info(f"Payment link {payment_link_id} marked as paid")

            return {"processed": True}

        except Exception as e:
            logger.error(f"Error handling payment webhook: {str(e)}")
            return {"processed": False, "error": str(e)}


# Singleton instance
vendor_service = VendorService()
