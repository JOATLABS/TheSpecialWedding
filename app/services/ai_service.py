import os
import google.generativeai as genai
from app.core.config import settings
from app.models.wedding import WeddingModel
from app.models.ai_usage import AIUsageLog, AIFeature
from app.core.database import mongo
from datetime import datetime
from bson import ObjectId

# Configure Gemini
# Assuming GOOGLE_API_KEY is in settings or env
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

class AIService:

    # Cost definition: 1 credit per X tokens (simplification)
    # Let's say 1 credit = 1000 tokens roughly, or fixed cost per feature
    FEATURE_COSTS = {
        AIFeature.SEATING_OPTIMIZATION: 10,
        AIFeature.BUDGET_ADVICE: 5,
        AIFeature.REPORT_GENERATION: 5,
        AIFeature.OTHER: 1
    }

    @staticmethod
    async def generate_content(tenant_id: str, prompt: str, feature: AIFeature, system_instruction: str = None) -> str:
        """
        Generates content using Gemini, deducts credits, and logs usage.
        Raises ValueError if insufficient credits.
        """
        if not GOOGLE_API_KEY:
             raise ValueError("GOOGLE_API_KEY is not set")

        # 1. Check Credits
        wedding = await mongo.db.weddings.find_one({"_id": tenant_id})
        if not wedding:
            raise ValueError("Wedding not found")

        current_credits = wedding.get("ai_credits_balance", 0)
        cost = AIService.FEATURE_COSTS.get(feature, 1)

        if current_credits < cost:
            raise ValueError(f"Insufficient AI credits. Required: {cost}, Available: {current_credits}")

        # 2. Call Gemini
        try:
            model = genai.GenerativeModel('gemini-1.5-flash') # Using Flash for speed/cost

            full_prompt = prompt
            if system_instruction:
                full_prompt = f"System: {system_instruction}\nUser: {prompt}"

            response = model.generate_content(full_prompt)
            content = response.text

            # 3. Calculate usage (approximate if token count not available in simple response)
            # Gemini response object usually has usage_metadata
            usage = response.usage_metadata
            total_tokens = usage.total_token_count if usage else len(full_prompt) // 4 + len(content) // 4

            # 4. Deduct Credits
            new_balance = current_credits - cost
            await mongo.db.weddings.update_one(
                {"_id": tenant_id},
                {"$set": {"ai_credits_balance": new_balance}}
            )

            # 5. Log Usage
            log_entry = AIUsageLog(
                _id=str(ObjectId()),
                tenant_id=tenant_id,
                feature=feature,
                prompt_tokens=usage.prompt_token_count if usage else 0,
                completion_tokens=usage.candidates_token_count if usage else 0,
                total_tokens=total_tokens,
                credits_cost=cost
            )
            await mongo.db.ai_usage_logs.insert_one(log_entry.model_dump(by_alias=True))

            return content

        except Exception as e:
            # Log error but don't deduct credits if API failed
            print(f"AI Generation Error: {e}")
            raise e

    @staticmethod
    async def add_credits(tenant_id: str, amount: int):
        await mongo.db.weddings.update_one(
            {"_id": tenant_id},
            {"$inc": {"ai_credits_balance": amount}}
        )
