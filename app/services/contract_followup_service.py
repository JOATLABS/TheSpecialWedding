"""
Contract Follow-up Service

Handles AI-drafted follow-up emails for unsigned contracts.
Integrates with cron jobs to check for stale contracts.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import logging
from bson import ObjectId
from app.core.database import mongo
from app.core.settings import settings

logger = logging.getLogger(__name__)


class ContractFollowupService:
    """
    Service for generating and managing contract follow-up drafts.

    Checks for unsigned contracts older than the threshold and
    uses AI to draft personalized follow-up emails for planners.
    """

    def __init__(self):
        self.contracts = mongo.db["contracts"]
        self.followup_drafts = mongo.db["contract_followup_drafts"]
        self.users = mongo.db["users"]
        self.weddings = mongo.db["weddings"]

    async def check_unsigned_contracts(
        self,
        days_threshold: int = 3
    ) -> List[Dict]:
        """
        Find contracts that have been sent but not signed after threshold days.

        Args:
            days_threshold: Number of days after which to flag as stale

        Returns:
            List of unsigned contracts that need follow-up
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)

            # Find contracts sent before cutoff that are still in sent/viewed status
            query = {
                "status": {"$in": ["sent", "viewed"]},
                "sent_at": {"$lte": cutoff_date},
                # Exclude contracts that already have a pending follow-up draft
                "_id": {
                    "$nin": await self._get_contracts_with_pending_drafts()
                }
            }

            cursor = self.contracts.find(query).limit(50)
            contracts = await cursor.to_list(length=50)

            logger.info(f"Found {len(contracts)} unsigned contracts older than {days_threshold} days")
            return contracts

        except Exception as e:
            logger.error(f"Failed to check unsigned contracts: {str(e)}")
            return []

    async def _get_contracts_with_pending_drafts(self) -> List[ObjectId]:
        """Get contract IDs that already have pending follow-up drafts."""
        try:
            cursor = self.followup_drafts.find(
                {"status": "pending"},
                {"contract_id": 1}
            )
            drafts = await cursor.to_list(length=None)
            return [ObjectId(d["contract_id"]) for d in drafts if d.get("contract_id")]
        except Exception as e:
            logger.error(f"Failed to get pending drafts: {str(e)}")
            return []

    async def generate_followup_draft(
        self,
        contract: Dict,
        prefetched_wedding: Optional[Dict] = None,
        prefetched_planner: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Generate an AI-drafted follow-up email for an unsigned contract.

        Args:
            contract: The unsigned contract data
            prefetched_wedding: Pre-loaded wedding data (for batch processing)
            prefetched_planner: Pre-loaded planner data (for batch processing)

        Returns:
            The created draft dict or None if generation failed
        """
        try:
            from app.services.ai_service import ai_service, InsufficientCreditsError

            planner_id = contract.get("planner_id")
            if not planner_id:
                logger.warning(f"No planner_id for contract {contract.get('_id')}")
                return None

            # Use prefetched planner or fetch if not provided
            planner = prefetched_planner
            if not planner:
                planner = await self.users.find_one({"_id": ObjectId(planner_id)})
            if not planner:
                logger.warning(f"Planner not found: {planner_id}")
                return None

            couple = contract.get("couple", {})
            package = contract.get("package_snapshot", {})

            # Use prefetched wedding or fetch if not provided
            wedding = prefetched_wedding
            wedding_id = contract.get("wedding_id")
            if not wedding and wedding_id:
                wedding = await self.weddings.find_one({"_id": ObjectId(wedding_id)})

            # Calculate days since sent for urgency context
            sent_at = contract.get("sent_at")
            days_since_sent = (datetime.now(timezone.utc) - sent_at).days if sent_at else 0

            context = {
                "couple_name": couple.get("name", ""),
                "partner_name": couple.get("partner_name"),
                "package_name": package.get("name", "Wedding Package"),
                "total_amount": package.get("total_amount", 0),
                "sent_date": contract.get("sent_at"),
                "days_since_sent": days_since_sent,
                "viewed": contract.get("status") == "viewed",
                "viewed_at": contract.get("viewed_at"),
                "wedding_date": contract.get("wedding_date") or (wedding.get("wedding_date") if wedding else None),
                "planner_name": planner.get("business_name") or planner.get("name", "Your Wedding Planner"),
                # Enhanced wedding context
                "venue_name": wedding.get("venue", {}).get("name") if wedding else None,
                "venue_location": wedding.get("venue", {}).get("location") if wedding else None,
                "cultural_style": wedding.get("cultural_style") if wedding else None,
                "guest_count": wedding.get("guest_count") if wedding else None,
                "wedding_title": wedding.get("title") if wedding else None,
            }

            prompt = """
            Draft a friendly, professional follow-up email for a wedding planning contract that hasn't been signed yet.

            The tone should be:
            - Warm and understanding (not pushy)
            - Professional but personal
            - Offer to answer questions
            - Create gentle urgency without pressure

            Include:
            1. A friendly greeting using the couple's names
            2. Reference to the contract/package by name
            3. If wedding details are available (venue, date, cultural style), subtly reference to show you remember their special day
            4. Offer to clarify any concerns or adjust the package
            5. A soft call-to-action
            6. Professional closing

            Cultural considerations:
            - If cultural_style indicates a specific tradition (Nigerian, Indian, Jewish, etc.), be culturally aware in your tone
            - Reference the wedding date if it's approaching to create appropriate urgency

            Keep it concise (2-3 short paragraphs).
            """

            try:
                result = await ai_service.generate(
                    user_id=planner_id,
                    tenant_id=str(contract.get("_id")),
                    feature="email_draft",
                    prompt=prompt,
                    context=context
                )

                email_content = result.get("response", {})
                if isinstance(email_content, dict) and email_content.get("raw"):
                    email_text = email_content.get("text", "")
                else:
                    email_text = str(email_content)

            except InsufficientCreditsError:
                logger.warning(f"Insufficient credits for planner {planner_id}")
                # Generate fallback template
                couple_display = couple.get("name", "")
                if couple.get("partner_name"):
                    couple_display += f" & {couple.get('partner_name')}"

                email_text = f"""Hi {couple_display},

I hope this message finds you well! I wanted to follow up on the wedding planning agreement I sent over for {package.get('name', 'your wedding package')}.

I understand you might have questions or want to discuss some details before signing. Please don't hesitate to reach out - I'm here to help make this process as smooth as possible for you.

Looking forward to hearing from you!

Warm regards,
{planner.get('business_name') or planner.get('name', 'Your Wedding Planner')}"""

            # Create draft record
            draft = {
                "contract_id": str(contract.get("_id")),
                "planner_id": planner_id,
                "couple_email": couple.get("email"),
                "couple_name": couple.get("name"),
                "subject": f"Following up on your {package.get('name', 'wedding package')} agreement",
                "body": email_text,
                "status": "pending",  # pending, sent, dismissed
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "ai_generated": True,
                "credits_used": result.get("credits_used", 0) if 'result' in dir() else 0
            }

            result = await self.followup_drafts.insert_one(draft)
            draft["_id"] = str(result.inserted_id)
            draft["id"] = draft["_id"]

            logger.info(f"Created follow-up draft for contract {contract.get('_id')}")
            return draft

        except Exception as e:
            logger.error(f"Failed to generate follow-up draft: {str(e)}")
            return None

    async def process_stale_contracts(self, days_threshold: int = 3) -> Dict[str, Any]:
        """
        Process all stale unsigned contracts and generate follow-up drafts.

        This is the main entry point for the cron job.
        Uses batch lookups to avoid N+1 query patterns.

        Args:
            days_threshold: Days after which contracts are considered stale

        Returns:
            Summary of processing results
        """
        try:
            contracts = await self.check_unsigned_contracts(days_threshold)

            results = {
                "total_found": len(contracts),
                "drafts_created": 0,
                "errors": 0,
                "processed_at": datetime.now(timezone.utc).isoformat()
            }

            if not contracts:
                return results

            # Batch fetch all weddings and planners to avoid N+1 queries
            wedding_ids = [
                ObjectId(c.get("wedding_id"))
                for c in contracts
                if c.get("wedding_id")
            ]
            planner_ids = [
                ObjectId(c.get("planner_id"))
                for c in contracts
                if c.get("planner_id")
            ]

            # Fetch all weddings in one query
            weddings_map = {}
            if wedding_ids:
                cursor = self.weddings.find({"_id": {"$in": wedding_ids}})
                weddings = await cursor.to_list(length=None)
                weddings_map = {str(w["_id"]): w for w in weddings}

            # Fetch all planners in one query
            planners_map = {}
            if planner_ids:
                cursor = self.users.find({"_id": {"$in": planner_ids}})
                planners = await cursor.to_list(length=None)
                planners_map = {str(p["_id"]): p for p in planners}

            logger.info(f"Batch loaded {len(weddings_map)} weddings, {len(planners_map)} planners")

            for contract in contracts:
                try:
                    # Pass pre-fetched data to avoid individual lookups
                    wedding = weddings_map.get(contract.get("wedding_id"))
                    planner = planners_map.get(contract.get("planner_id"))

                    draft = await self.generate_followup_draft(
                        contract,
                        prefetched_wedding=wedding,
                        prefetched_planner=planner
                    )
                    if draft:
                        results["drafts_created"] += 1

                        # Notify planner (optional - could be email or in-app notification)
                        await self._notify_planner_of_draft(contract, draft)
                except Exception as e:
                    logger.error(f"Error processing contract {contract.get('_id')}: {str(e)}")
                    results["errors"] += 1

            logger.info(f"Follow-up processing complete: {results}")
            return results

        except Exception as e:
            logger.error(f"Failed to process stale contracts: {str(e)}")
            return {"error": str(e)}

    async def _notify_planner_of_draft(self, contract: Dict, draft: Dict):
        """Send notification to planner about pending follow-up draft."""
        try:
            # For now, just log. Could integrate with notification system.
            planner_id = contract.get("planner_id")
            logger.info(f"Follow-up draft ready for planner {planner_id}, contract {contract.get('_id')}")

            # Optionally send email notification
            # from app.services.contract_email_service import contract_email_service
            # await contract_email_service.send_draft_notification(...)

        except Exception as e:
            logger.error(f"Failed to notify planner: {str(e)}")

    async def get_pending_drafts(self, planner_id: str) -> List[Dict]:
        """
        Get all pending follow-up drafts for a planner.

        Args:
            planner_id: The planner's user ID

        Returns:
            List of pending draft dicts
        """
        try:
            cursor = self.followup_drafts.find({
                "planner_id": planner_id,
                "status": "pending"
            }).sort("created_at", -1)

            drafts = await cursor.to_list(length=50)

            # Serialize ObjectIds
            for draft in drafts:
                draft["id"] = str(draft["_id"])
                draft["_id"] = str(draft["_id"])

            return drafts

        except Exception as e:
            logger.error(f"Failed to get pending drafts: {str(e)}")
            return []

    async def update_draft(
        self,
        draft_id: str,
        planner_id: str,
        updates: Dict
    ) -> Optional[Dict]:
        """
        Update a follow-up draft (edit content, mark as sent/dismissed).

        Args:
            draft_id: The draft ID
            planner_id: The planner's user ID (for authorization)
            updates: Fields to update (body, subject, status)

        Returns:
            Updated draft or None
        """
        try:
            allowed_fields = ["body", "subject", "status"]
            update_data = {
                k: v for k, v in updates.items()
                if k in allowed_fields
            }
            update_data["updated_at"] = datetime.now(timezone.utc)

            result = await self.followup_drafts.find_one_and_update(
                {
                    "_id": ObjectId(draft_id),
                    "planner_id": planner_id
                },
                {"$set": update_data},
                return_document=True
            )

            if result:
                result["id"] = str(result["_id"])
                result["_id"] = str(result["_id"])

            return result

        except Exception as e:
            logger.error(f"Failed to update draft: {str(e)}")
            return None

    async def send_draft(
        self,
        draft_id: str,
        planner_id: str
    ) -> bool:
        """
        Send a follow-up draft as an actual email.

        Args:
            draft_id: The draft ID
            planner_id: The planner's user ID

        Returns:
            True if sent successfully
        """
        try:
            import resend
            resend.api_key = settings.resend_api_key

            # Get draft
            draft = await self.followup_drafts.find_one({
                "_id": ObjectId(draft_id),
                "planner_id": planner_id,
                "status": "pending"
            })

            if not draft:
                logger.error(f"Draft not found or not pending: {draft_id}")
                return False

            # Get planner for from name
            planner = await self.users.find_one({"_id": ObjectId(planner_id)})
            planner_name = planner.get("business_name") or planner.get("name", "Wedding Planner") if planner else "Wedding Planner"

            # Send email
            response = resend.Emails.send({
                "from": f"{planner_name} via The Special Wedding <{settings.resend_from_email}>",
                "to": [draft.get("couple_email")],
                "subject": draft.get("subject"),
                "text": draft.get("body"),
                "reply_to": planner.get("email") if planner else None
            })

            # Mark as sent
            await self.followup_drafts.update_one(
                {"_id": ObjectId(draft_id)},
                {
                    "$set": {
                        "status": "sent",
                        "sent_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            logger.info(f"Follow-up email sent for draft {draft_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send follow-up: {str(e)}")
            return False


# Singleton instance
contract_followup_service = ContractFollowupService()
