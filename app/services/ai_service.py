"""
AI Service

Centralized AI gateway with credit management, caching, and logging.
Uses Google Gemini API via the new google-genai SDK.

SDK Reference (Context7 validated - https://ai.google.dev/gemini-api/docs):
- Package: google-genai (pip install google-genai)
- Import: from google import genai
- Client: client = genai.Client(api_key=...) or uses GEMINI_API_KEY env var
- Async: await client.aio.models.generate_content(model='gemini-2.0-flash', contents='...')

Model Strategy:
- Default: gemini-2.5-flash (best price-performance)
- Low credits (<10%): gemini-2.0-flash (faster, more economical)
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json
import logging
from fastapi import HTTPException
from app.core.settings import settings
from app.core.database import mongo
from app.services.ai_cache_service import ai_cache_service
from app.services.subscription_service import SubscriptionService
from app.services.notification_service import NotificationService
from app.utils.id_utils import to_object_id

logger = logging.getLogger(__name__)


# ============================================================================
# AI FEATURE DEFINITIONS
# ============================================================================

AI_FEATURES = {
    "budget_insights": {
        "credits": 3,
        "ttl_hours": 48,
        "cacheable": True,
        "description": "Generate budget insights and recommendations",
        "system_prompt": """You are an expert wedding budget advisor with deep knowledge of global wedding traditions and regional pricing.

IMPORTANT CONTEXT FACTORS:
1. **Cultural Style** - Different cultures have different wedding traditions:
   - Nigerian weddings: Traditional ceremony (engagement/introduction), church wedding, reception often as separate multi-day events. Aso-oke fabrics, live bands, owambe style. Typically higher food/entertainment costs.
   - Indian weddings: Multi-day events (Sangeet, Mehndi, Ceremony, Reception). Heavy decor, elaborate catering. Can be 2-3x Western wedding costs.
   - Jewish weddings: Chuppah, Rabbi, ketubah, specific ceremony elements. Kosher catering requirements can increase food costs 30-50%.
   - Mexican weddings: Madrinas/padrinos system (sponsors), mariachi, traditional elements. Often larger guest counts.
   - Western/American: Typically single-day ceremony + reception.
   - Each culture has unique vendor needs (cultural DJs, specific caterers, traditional attire makers).

2. **Geographic Region** - Pricing varies dramatically:
   - NYC/LA/SF: 2-3x national average
   - Oklahoma City: ~80% of national average
   - Lagos, Nigeria: Different currency, but similar % allocations
   - Rural areas: Often 40-60% of urban costs
   - Destination weddings: Add 20-30% for logistics

3. **Season** - Peak vs off-season:
   - Peak (May-October, December holidays): Premium pricing
   - Off-peak (January-March, November): 15-30% savings possible

4. **Guest Count** - Scale affects costs:
   - Per-person costs for catering/rentals
   - Venue minimums/maximums
   - Nigerian/Indian weddings often have 300-500+ guests

Analyze the budget considering these cultural, regional, and seasonal factors. A $15K planner fee is normal for Nigerian weddings in the US. A $5K photography budget might be appropriate in Oklahoma but inadequate in LA.

Return ONLY valid JSON in this exact format:
{"insights": [
  {"category": "Category Name", "insight": "The main observation", "recommendation": "Actionable advice", "priority": "high"},
  {"category": "Category Name", "insight": "The main observation", "recommendation": "Actionable advice", "priority": "medium"},
  {"category": "Category Name", "insight": "The main observation", "recommendation": "Actionable advice", "priority": "low"}
]}

Priority levels: "high" for urgent budget issues or missing essentials, "medium" for optimization suggestions, "low" for nice-to-know tips.
Category should match one of the budget categories when applicable, or be "Overall" for general insights.
Be specific about cultural considerations in your recommendations.""",
    },
    "chat": {
        "credits": 1,
        "ttl_hours": 0,
        "cacheable": False,
        "description": "Interactive AI chat assistant for wedding planning",
        "system_prompt": """You are an expert wedding planning assistant with deep knowledge of:
- Wedding budgets and vendor pricing across different regions
- Cultural wedding traditions (Nigerian, Indian, Jewish, Mexican, Western, etc.)
- Timeline planning and task management
- Vendor selection and negotiation
- Guest management and seating
- Wedding etiquette and customs

You are conversational and helpful. Answer questions directly and concisely.
When discussing budgets, consider the cultural context and regional pricing.
When you don't know something specific, say so rather than making up information.
Keep responses focused and actionable - wedding planners are busy!

If the user provides wedding context (cultural style, location, guest count, budget), use it to give more tailored advice.""",
    },
    "seating_small": {
        "credits": 2,
        "ttl_hours": 72,
        "cacheable": True,
        "description": "Seating optimization for small weddings (<=50 guests)",
        "system_prompt": """You are a wedding seating optimizer. Given guests and tables,
create an optimal seating arrangement that:
1. Keeps family groups together
2. Respects "keep apart" constraints
3. Balances table sizes

Return JSON: {"tables": [{"table_id": "...", "guests": ["guest_id", ...]}]}""",
    },
    "seating_medium": {
        "credits": 5,
        "ttl_hours": 72,
        "cacheable": True,
        "description": "Seating optimization for medium weddings (51-150 guests)",
        "system_prompt": """You are an expert wedding seating optimizer for medium-sized weddings (51-150 guests).

Create an optimal seating arrangement considering:
1. **Family Groups** - Keep immediate family together, extend to cousins/aunts/uncles at adjacent tables
2. **Social Dynamics** - Group friends who know each other, separate any known conflicts
3. **Age Considerations** - Elderly guests near exits/restrooms, young families near each other
4. **Singles/Couples** - Mix singles tables strategically for networking, keep couples together
5. **VIP Placement** - Parents, wedding party, and honored guests at prominent tables
6. **Table Balance** - Even distribution, no tables with just 2-3 guests

For each table assignment, briefly note why guests are grouped together.

Return ONLY valid JSON:
{"tables": [
  {"table_id": "...", "table_name": "...", "guests": [
    {"guest_id": "...", "guest_name": "...", "reason": "Brief reason for placement"}
  ]}
]}""",
    },
    "seating_large": {
        "credits": 10,
        "ttl_hours": 72,
        "cacheable": True,
        "description": "Seating optimization for large weddings (150+ guests)",
        "system_prompt": """You are an expert wedding seating optimizer for large-scale weddings (150+ guests).

For large weddings, seating strategy requires careful zone planning:

1. **Zone Strategy**:
   - Zone A (Near head table): Immediate family, wedding party, VIPs
   - Zone B (Center): Extended family, close friends
   - Zone C (Perimeter): Work colleagues, acquaintances, plus-ones

2. **Cultural Considerations**:
   - Respect cultural seating norms (e.g., elders at honored positions)
   - Group guests by language if multilingual wedding
   - Consider cultural dynamics between families

3. **Logistics**:
   - Even table distribution (aim for 8-10 per table)
   - Special needs guests near accessible routes
   - Children's tables near parents but with supervision space

4. **Social Optimization**:
   - Create conversation clusters (shared interests, professions)
   - Strategic mixing of bride/groom sides to encourage mingling
   - Avoid seating conflicts (exes, family feuds, business rivals)

5. **Flow Considerations**:
   - Place frequently moving guests (vendors, photographers' families) at aisle seats
   - Consider buffet/bar proximity for larger parties

Return ONLY valid JSON with strategic reasoning:
{"tables": [
  {"table_id": "...", "table_name": "...", "zone": "A|B|C", "guests": [
    {"guest_id": "...", "guest_name": "...", "reason": "Placement rationale"}
  ]}
]}""",
    },
    "email_draft": {
        "credits": 1,
        "ttl_hours": 0,
        "cacheable": False,
        "description": "Draft communication emails",
        "system_prompt": """You are a professional wedding planner writing to clients.
Draft a warm, professional message based on the context provided.
Match the tone to the situation (reminder, thank you, follow-up, etc.).
Keep it concise (2-3 short paragraphs max).""",
    },
    "progress_report": {
        "credits": 2,
        "ttl_hours": 6,
        "cacheable": True,
        "description": "Generate wedding progress report",
        "system_prompt": """Generate a wedding progress summary for the couple.
Include:
1. RSVP status (accepted, pending, declined)
2. Budget status (spent vs remaining)
3. Upcoming milestones
4. Action items for the couple

Return a warm, encouraging summary.""",
    },
    "package_pricing": {
        "credits": 3,
        "ttl_hours": 24,
        "cacheable": True,
        "description": "Suggest package pricing based on market data",
        "system_prompt": """You are a wedding industry pricing consultant.
Based on the services, location, and market data, suggest:
1. A competitive price range
2. Recommended payment schedule
3. How this compares to market average

Return JSON: {"min_price": X, "max_price": Y, "recommended": Z,
"market_comparison": "above|at|below", "schedule_suggestion": [...]}""",
    },
    "payment_retry_timing": {
        "credits": 0,  # Internal feature - no cost
        "ttl_hours": 0,
        "cacheable": False,
        "description": "Suggest optimal retry timing for failed payments",
        "system_prompt": """You are a payment optimization expert. Analyze the failed payment data and suggest the optimal retry timing.

Consider:
1. Day of week patterns (payday cycles - 1st, 15th of month)
2. Decline reason (insufficient funds vs card expired vs generic)
3. Previous payment history success rate
4. Time since last attempt

Return JSON: {
  "suggested_retry_date": "YYYY-MM-DD",
  "suggested_retry_time": "HH:MM",
  "confidence": 0-100,
  "reasoning": "brief explanation",
  "override_backoff": true/false
}""",
    },
    "payment_success_prediction": {
        "credits": 0,  # Internal feature - no cost
        "ttl_hours": 1,
        "cacheable": True,
        "description": "Predict likelihood of payment success",
        "system_prompt": """You are a payment analytics expert. Predict the likelihood of this payment succeeding.

Consider:
1. Days since card was added (fresh cards more likely to work)
2. Previous payment history on this card
3. Card type (debit vs credit)
4. Payment amount relative to previous successful amounts
5. Time since last successful payment

Return JSON: {
  "success_probability": 0-100,
  "risk_level": "low|medium|high",
  "risk_factors": ["factor1", "factor2"],
  "recommendations": ["recommendation1", "recommendation2"]
}""",
    },
    "dashboard_insights": {
        "credits": 2,
        "ttl_hours": 4,
        "cacheable": True,
        "description": "Generate actionable dashboard insights for a wedding",
        "system_prompt": """You are an expert wedding planning assistant analyzing a wedding's status.

Review the provided data about this wedding and generate 3-5 actionable insights for the planner.

Each insight should:
1. Identify something that needs attention or is going well
2. Provide specific, actionable advice
3. Be prioritized based on urgency

Categories to analyze:
- RSVP status (pending responses, response rate)
- Budget health (overspending, underspending, missing categories)
- Upcoming deadlines and tasks
- Vendor payments due
- Timeline concerns based on wedding date

Return ONLY valid JSON in this exact format:
{
  "insights": [
    {
      "title": "Short descriptive title",
      "description": "Detailed explanation with specific numbers/dates",
      "priority": "high|medium|low",
      "action_url": "/admin/guests or /admin/budget or /admin/money etc",
      "icon": "users|dollar-sign|calendar|clock|alert-triangle|check-circle"
    }
  ]
}

Priority guide:
- high: Urgent action needed (due within 7 days, critical issues)
- medium: Should address soon (due within 14-30 days)
- low: Good to know, optional improvements

Icon guide:
- users: Guest/RSVP related
- dollar-sign: Budget/payment related
- calendar: Timeline/date related
- clock: Deadline/timing related
- alert-triangle: Warning/issue
- check-circle: Positive update""",
    },
    "contract_section": {
        "credits": 1,
        "ttl_hours": 0,
        "cacheable": False,
        "description": "Generate contract section content",
        "system_prompt": """You are a legal writing assistant specializing in wedding vendor contracts.

Generate professional, legally-appropriate contract clause content based on the section type and vendor type.

Be specific and thorough. Include:
- Clear terms and conditions
- Industry-standard practices
- Appropriate legal language (but readable)
- Consideration for wedding-specific needs

Section types you may generate:
- payment_terms: Payment schedule, accepted methods, late fees
- cancellation_policy: Cancellation terms, refund policies, notice periods
- scope_of_work: Detailed deliverables and services included
- liability: Liability limitations, insurance requirements
- force_majeure: Force majeure/act of god clauses
- custom: Based on user's specific request

Format the output as markdown-compatible text that can be directly inserted into a contract.""",
    },
    # =========================================================================
    # PHASE 2C: Vendor & Calendar AI
    # =========================================================================
    "vendor_recommendations": {
        "credits": 2,
        "ttl_hours": 24,
        "cacheable": True,
        "description": "Generate vendor selection criteria and recommendations",
        "system_prompt": """You are an expert wedding vendor consultant with deep knowledge of the wedding industry.

Based on the vendor type, budget range, wedding style, and region, provide:
1. Key selection criteria for this vendor type
2. Questions to ask during consultations
3. Red flags to watch for
4. Budget assessment (is their budget reasonable for the region/style?)
5. Typical pricing expectations for this vendor type in their region

Return ONLY valid JSON in this exact format:
{
  "vendor_type": "the vendor type",
  "selection_criteria": [
    {"criterion": "What to look for", "importance": "high|medium|low", "why": "explanation"}
  ],
  "questions_to_ask": [
    {"question": "Question text", "why_important": "Reason"}
  ],
  "red_flags": [
    {"flag": "Warning sign", "severity": "critical|moderate|minor"}
  ],
  "budget_assessment": {
    "verdict": "adequate|low|high",
    "typical_range_min": 0,
    "typical_range_max": 0,
    "explanation": "Context about pricing for this region/style"
  },
  "pro_tips": ["Tip 1", "Tip 2"]
}

Consider cultural wedding styles (Nigerian, Indian, Jewish, Mexican, Western, etc.) and their specific vendor needs.
Regional pricing varies significantly - NYC/LA are 2-3x more expensive than smaller markets.""",
    },
    "task_prioritization": {
        "credits": 2,
        "ttl_hours": 6,
        "cacheable": True,
        "description": "Prioritize wedding planning tasks based on urgency and wedding date",
        "system_prompt": """You are an expert wedding planner helping prioritize tasks.

Analyze the wedding date, pending tasks, and vendor deadlines to create a prioritized action plan.

Consider:
1. Days until wedding - urgency increases as date approaches
2. Dependencies - some tasks must be done before others
3. Vendor booking windows - popular vendors book 12-18 months ahead
4. Cultural traditions - some cultures have multi-day events requiring more planning
5. Seasonal factors - peak season requires earlier booking

Return ONLY valid JSON in this exact format:
{
  "priority_tasks": [
    {
      "task": "Task title or description",
      "urgency": "critical|high|medium|low",
      "due_by": "YYYY-MM-DD or 'this week' or 'this month'",
      "reason": "Why this is the priority level",
      "category": "venue|catering|photography|attire|decor|music|invitations|other"
    }
  ],
  "weekly_focus": "What to focus on this week",
  "warnings": ["Things that are overdue or at risk"],
  "upcoming_milestones": [
    {"milestone": "Description", "date": "YYYY-MM-DD", "importance": "Why it matters"}
  ]
}

Be specific about deadlines based on the wedding date. A wedding 6 months away has different priorities than one 2 months away.""",
    },
    "timeline_generator": {
        "credits": 2,
        "ttl_hours": 48,
        "cacheable": True,
        "description": "Generate a wedding planning timeline from now to the wedding date",
        "system_prompt": """You are an expert wedding planner creating a comprehensive planning timeline.

Generate a milestone-based timeline from the current date to the wedding date, considering:
1. Wedding date distance (adjust timeline accordingly)
2. Cultural style (Nigerian, Indian, Jewish, Mexican, Western, etc.)
3. Guest count (larger weddings need more lead time)
4. Budget level (impacts vendor booking strategy)

Return ONLY valid JSON in this exact format:
{
  "timeline": [
    {
      "phase": "Phase name (e.g., '12-18 months out', '6-8 months out')",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "milestones": [
        {
          "task": "What to do",
          "category": "venue|catering|photography|attire|decor|music|invitations|guests|budget|other",
          "deadline": "YYYY-MM-DD",
          "priority": "critical|high|medium|low",
          "notes": "Cultural or style-specific considerations"
        }
      ]
    }
  ],
  "key_dates": [
    {"date": "YYYY-MM-DD", "event": "Description", "importance": "Why it matters"}
  ],
  "cultural_considerations": ["Specific traditions or requirements for this wedding style"],
  "budget_tips": ["Timing-based budget advice"]
}

Adjust the timeline based on how much time is available. If wedding is 3 months away, compress appropriately.""",
    },
    # =========================================================================
    # PHASE 2D: Financial AI
    # =========================================================================
    "payment_forecast": {
        "credits": 2,
        "ttl_hours": 12,
        "cacheable": True,
        "description": "Forecast upcoming vendor payments and cash flow",
        "system_prompt": """You are a financial planning expert for weddings analyzing payment schedules.

Review the scheduled payments, historical patterns, and wedding timeline to provide:
1. Cash flow forecast for next 30/60/90 days
2. Payment peaks (when multiple large payments are due)
3. Risk assessment for cash flow issues
4. Recommendations for payment timing

Return ONLY valid JSON in this exact format:
{
  "forecast_periods": [
    {
      "period": "Next 30 days",
      "total_due": 0,
      "payments": [
        {"vendor": "Name", "amount": 0, "due_date": "YYYY-MM-DD", "status": "scheduled|pending|overdue"}
      ],
      "risk_level": "low|medium|high"
    }
  ],
  "cash_flow_warning": "Warning message if issues detected, null otherwise",
  "peak_payment_dates": [
    {"date": "YYYY-MM-DD", "total": 0, "vendors": ["list"]}
  ],
  "recommendations": [
    {"recommendation": "Advice", "priority": "high|medium|low", "potential_savings": 0}
  ],
  "summary": {
    "total_remaining": 0,
    "total_paid": 0,
    "next_payment_date": "YYYY-MM-DD",
    "largest_upcoming": {"vendor": "Name", "amount": 0, "date": "YYYY-MM-DD"}
  }
}

Flag any cash flow concerns (multiple large payments in short window, overdue payments, etc.).""",
    },
    "vendor_price_analysis": {
        "credits": 1,
        "ttl_hours": 24,
        "cacheable": True,
        "description": "Analyze if a vendor quote is fair for the region and service type",
        "system_prompt": """You are a wedding industry pricing expert analyzing vendor quotes.

Compare the provided quote to typical market rates for the vendor type, region, and service level.

Consider:
1. Vendor type (photographer, caterer, DJ, florist, etc.)
2. Region (NYC/LA are 2-3x more expensive than smaller markets)
3. Service level/package inclusions
4. Wedding size/guest count
5. Cultural style requirements (some traditions require specialized vendors)

Return ONLY valid JSON in this exact format:
{
  "verdict": "below_market|at_market|above_market|significantly_above",
  "confidence": "high|medium|low",
  "typical_range": {
    "min": 0,
    "max": 0,
    "average": 0
  },
  "analysis": "Detailed explanation of the assessment",
  "factors_considered": [
    {"factor": "Factor name", "impact": "raises_price|lowers_price|neutral", "explanation": "Why"}
  ],
  "recommendations": [
    "Negotiation tips or alternatives"
  ],
  "value_assessment": "Is this good value for what's included? Explanation."
}

Be specific about regional pricing differences. A $5K photographer in Oklahoma is different from $5K in Manhattan.""",
    },
    # =========================================================================
    # PHASE 2B: Communication & Forms AI
    # =========================================================================
    "message_generator": {
        "credits": 1,
        "ttl_hours": 0,
        "cacheable": False,
        "description": "Generate personalized wedding communication messages",
        "system_prompt": """You are an expert wedding communications specialist helping planners draft messages.

Generate a warm, professional message based on the context provided.

Message types you may generate:
- rsvp_reminder: Friendly RSVP follow-up to guests who haven't responded
- save_the_date: Excited announcement about an upcoming wedding
- thank_you: Grateful post-wedding thank you note
- vendor_reminder: Professional reminder to vendor about deadlines/payments
- event_reminder: Reminder about upcoming wedding events
- custom: Based on user's specific request

Tones:
- formal: Professional and traditional
- friendly: Warm and personable
- casual: Relaxed and fun

Consider the recipient context (family, friend, vendor, etc.) when crafting the message.

Return ONLY valid JSON in this exact format:
{
  "subject": "Email subject line",
  "body": "The full message body with proper formatting and line breaks",
  "sms_version": "A shorter version suitable for SMS (under 160 chars if possible)"
}

Keep messages concise but heartfelt. Include [Name] placeholder for personalization.""",
    },
    "form_questions": {
        "credits": 1,
        "ttl_hours": 24,
        "cacheable": True,
        "description": "Generate smart form questions based on form type and wedding context",
        "system_prompt": """You are a wedding planning expert helping create form questions.

Generate relevant, thoughtful questions based on the form type and wedding context.

Form types:
- rsvp: Standard RSVP form questions
- dietary: Dietary preferences and restrictions
- song_requests: Music and song preferences
- accommodation: Hotel/lodging needs
- transportation: Shuttle/transport preferences
- custom: Based on specific needs

Consider cultural context when generating questions:
- Nigerian weddings: Traditional ceremony attendance, aso-oke preferences
- Indian weddings: Multi-day event attendance, dietary restrictions (vegetarian common)
- Jewish weddings: Kosher dietary needs, ceremony participation
- Western weddings: Standard single-day event questions

Return ONLY valid JSON in this exact format:
{
  "questions": [
    {
      "text": "The question text",
      "type": "text|yes_no|multiple_choice|checkbox|number",
      "required": true,
      "options": ["Option 1", "Option 2"],
      "placeholder": "Placeholder text for text inputs",
      "help_text": "Optional help text explaining the question"
    }
  ],
  "form_intro": "Suggested introduction text for the form",
  "form_title": "Suggested form title"
}

Generate 4-8 relevant questions. Make yes_no and multiple_choice the default when appropriate.""",
    },
    # =========================================================================
    # ADVERTISING PLATFORM: AI Quote Draft
    # =========================================================================
    "ad_quote_draft": {
        "credits": 1,
        "ttl_hours": 0,
        "cacheable": False,
        "description": "Draft a personalized quote request for an advertising vendor",
        "system_prompt": """You are a professional wedding planner drafting a quote request to a vendor you discovered through an advertising platform.

Write a warm, professional, and specific message that:
1. Introduces yourself briefly as a wedding planner
2. References the vendor's specific category/services
3. Includes relevant wedding details (date, location, guest count, budget range) when provided
4. Asks clear questions about pricing, availability, and packages
5. Keeps a professional but friendly tone

CONTEXT PROVIDED:
- vendor_name: The vendor's business name
- vendor_category: Their service category (photographer, florist, caterer, etc.)
- service_area: Where they operate
- planner_name: Your name (the planner writing the message)
- wedding_date: Wedding date (if available)
- wedding_location: Wedding location (if available)
- guest_count: Expected guest count (if available)
- venue: Venue name (if available)
- budget_range: Budget range for this vendor type (if available)

Return ONLY valid JSON in this exact format:
{
  "subject": "Quote Request — [Vendor Category] for [Date/Event]",
  "body": "The full quote request message (use \\n for line breaks)",
  "tone": "professional|friendly|formal"
}

Guidelines:
- Keep the message to 3-4 short paragraphs (150-250 words)
- Be specific about what information you need from the vendor
- If wedding details are sparse, still write a compelling message but note you'll share details soon
- Never fabricate wedding details that were not provided
- Use the vendor's actual name and category in the message
- End with a clear call to action (e.g., "Could you share your availability and pricing?")""",
    },
}

# Model configuration
# gemini-2.5-flash: Best price-performance, used when credits are healthy
# gemini-2.0-flash: Faster and more economical, used when credits are low
MODEL_PRIMARY = "gemini-2.5-flash"
MODEL_ECONOMY = "gemini-2.0-flash"
LOW_CREDIT_THRESHOLD = 0.10  # Switch to economy model when <10% credits remain


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough AI credits."""

    def __init__(self, message: str, required: int, available: int):
        self.message = message
        self.required = required
        self.available = available
        super().__init__(message)


class AIGenerationError(Exception):
    """Base class for AI generation failures."""

    def __init__(
        self,
        message: str,
        error_code: str = "ai_error",
        retry_after: Optional[int] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.retry_after = (
            retry_after  # Seconds until retry is allowed (for rate limits)
        )
        super().__init__(message)


class AIRateLimitError(AIGenerationError):
    """Raised when hitting Gemini API rate limits."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="AI service is temporarily busy. Please wait a moment and try again.",
            error_code="rate_limit",
            retry_after=retry_after,
        )


class AIContentBlockedError(AIGenerationError):
    """Raised when Gemini safety filters block the content."""

    def __init__(self, reason: str = "content policy"):
        super().__init__(
            message=f"The request was blocked due to {reason}. Please modify your request and try again.",
            error_code="content_blocked",
        )


class AIServiceUnavailableError(AIGenerationError):
    """Raised when Gemini service is unavailable."""

    def __init__(self):
        super().__init__(
            message="AI service is temporarily unavailable. Please try again in a few minutes.",
            error_code="service_unavailable",
            retry_after=300,
        )


class AIQuotaExceededError(AIGenerationError):
    """Raised when API quota is exceeded."""

    def __init__(self):
        super().__init__(
            message="AI service quota has been reached. Please contact support or try again tomorrow.",
            error_code="quota_exceeded",
        )


class AIInvalidResponseError(AIGenerationError):
    """Raised when AI returns an invalid/unparseable response."""

    def __init__(self):
        super().__init__(
            message="AI returned an unexpected response. Please try again.",
            error_code="invalid_response",
        )


class AITimeoutError(AIGenerationError):
    """Raised when AI request times out."""

    def __init__(self):
        super().__init__(
            message="AI request timed out. Please try again with a simpler request.",
            error_code="timeout",
            retry_after=10,
        )


class AIService:
    """
    Centralized AI service with:
    - Credit validation and deduction
    - Response caching
    - Usage logging
    - Error handling
    - Dynamic model selection based on credit levels

    Uses the new google-genai SDK with proper async support.
    Reference: https://ai.google.dev/gemini-api/docs/migrate
    """

    def __init__(self):
        self.usage_log = mongo.db["ai_usage_log"]
        self.low_credit_alerts = mongo.db["ai_low_credit_alerts"]  # Track sent alerts
        self.subscription_service = SubscriptionService()
        self.notification_service = NotificationService()
        self._client = None

        # Initialize Gemini client if API key is available
        if settings.ai_enabled:
            try:
                from google import genai
                from google.genai import types

                # New SDK: Use Client pattern with explicit API key
                # The client can also read from GEMINI_API_KEY or GOOGLE_API_KEY env vars
                api_key = settings.ai_api_key
                if api_key:
                    # Configure HTTP options with Referer header to satisfy API key restrictions
                    # The Referer must match what's configured in Google Cloud Console
                    http_options = types.HttpOptions(
                        headers={
                            "Referer": settings.frontend_url
                            or "https://thespecialwedding.io"
                        }
                    )
                    self._client = genai.Client(
                        api_key=api_key, http_options=http_options
                    )
                    logger.info(
                        f"Gemini client configured with Referer: {settings.frontend_url or 'https://thespecialwedding.io'}"
                    )
                else:
                    # Try to use environment variable automatically
                    self._client = genai.Client()

                logger.info(
                    f"Gemini AI initialized successfully. Primary: {MODEL_PRIMARY}, Economy: {MODEL_ECONOMY}"
                )
            except ImportError as e:
                logger.error(f"google-genai package not installed: {str(e)}")
                logger.error("Install with: pip install google-genai")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {str(e)}")
        else:
            logger.warning(
                "AI service disabled - GOOGLE_API_KEY or GEMINI_API_KEY not configured"
            )

    def _ensure_initialized(self):
        """Verify AI service is properly configured.

        Raises AIServiceUnavailableError (maps to HTTP 503) rather than
        AIGenerationError (500) so the frontend can show a clear
        'service not configured' message instead of a generic 500.
        """
        if not self._client:
            raise AIServiceUnavailableError()

    def get_feature_info(self, feature: str) -> Optional[Dict]:
        """Get feature configuration."""
        return AI_FEATURES.get(feature)

    def list_features(self) -> Dict[str, Dict]:
        """List all available AI features with their costs."""
        return {
            name: {
                "credits": config["credits"],
                "description": config["description"],
                "cacheable": config["cacheable"],
            }
            for name, config in AI_FEATURES.items()
        }

    async def _is_root_admin_user(self, user_id: str) -> bool:
        """Return True when the usage-tracked user belongs to the configured root admin."""
        try:
            user = await self.subscription_service.users_collection.find_one(
                {"_id": to_object_id(user_id, "user_id")}, {"role": 1, "email": 1}
            )
        except (HTTPException, ValueError, TypeError):
            return False
        except Exception as e:
            logger.warning(f"Failed to resolve AI user role for {user_id}: {e}")
            return False

        if not user:
            return False

        root_admin_email = (
            settings.root_admin_email or "thedeveloper@thespecialwedding.io"
        )
        return (
            user.get("role") == "ROOT_ADMIN" and user.get("email") == root_admin_email
        )

    async def _select_model_and_check_credits(
        self, user_id: str, bypass_limits: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Select the appropriate model based on user's credit level and return credit status.

        Returns dict with:
        - model: gemini-2.5-flash (normal) or gemini-2.0-flash (low credits)
        - credits_remaining: number of credits left
        - credits_limit: monthly limit
        - credits_percent: percentage remaining
        - low_credits_warning: alert message if below threshold (for planner to see)
        """
        result = {
            "model": MODEL_PRIMARY,
            "credits_remaining": None,
            "credits_limit": None,
            "credits_percent": None,
            "low_credits_warning": None,
        }

        try:
            if bypass_limits is None:
                bypass_limits = await self._is_root_admin_user(user_id)
            if bypass_limits:
                return result

            # Get user's subscription and usage stats
            subscription = await self.subscription_service.get_user_subscription(
                user_id
            )
            if not subscription:
                return result

            plan = await self.subscription_service.get_plan(subscription["plan_id"])
            usage = await self.subscription_service.get_usage_stats(user_id)

            if not plan or not usage:
                return result

            # Get AI credits limit and usage
            limit = plan.get("ai_credits_monthly", 100)
            used = usage.get("ai_credits_used_month", 0)
            remaining = limit - used

            result["credits_remaining"] = remaining
            result["credits_limit"] = limit

            if limit <= 0:
                return result

            remaining_ratio = remaining / limit
            result["credits_percent"] = round(remaining_ratio * 100, 1)

            if remaining_ratio <= LOW_CREDIT_THRESHOLD:
                result["model"] = MODEL_ECONOMY
                result["low_credits_warning"] = (
                    f"You have {remaining} AI credits remaining ({result['credits_percent']}% of your monthly limit). "
                    f"Consider upgrading your plan or waiting for credits to reset."
                )
                # Send in-app notification (only once per billing cycle)
                await self._send_low_credit_notification(user_id, remaining, limit)

            return result

        except Exception as e:
            logger.warning(f"Error checking credit level for model selection: {e}")
            return result

    async def check_credits(
        self, user_id: str, feature: str, bypass_limits: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Check if user has enough AI credits for a feature.

        Returns:
            Dict with allowed status, credits info, and message
        """
        if feature not in AI_FEATURES:
            raise ValueError(f"Unknown AI feature: {feature}")

        credits_needed = AI_FEATURES[feature]["credits"]

        if bypass_limits is None:
            bypass_limits = await self._is_root_admin_user(user_id)
        if bypass_limits:
            return {
                "allowed": True,
                "credits_needed": 0,
                "credits_remaining": None,
                "message": None,
            }

        # Use existing subscription service to check limits
        result = await self.subscription_service.check_usage_limits(
            user_id=user_id, resource_type="ai_credits", requested_amount=credits_needed
        )

        return {
            "allowed": result.get("allowed", False),
            "credits_needed": credits_needed,
            "credits_remaining": result.get("remaining", 0),
            "message": result.get("message", ""),
        }

    async def generate(
        self,
        user_id: str,
        tenant_id: str,
        feature: str,
        prompt: str,
        context: Dict[str, Any],
        force_refresh: bool = False,
        cache_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI response with caching and credit tracking.

        Args:
            user_id: The user's ID for credit tracking
            tenant_id: The wedding or planner ID for cache scoping
            feature: The AI feature being used (e.g., "budget_insights")
            prompt: The prompt to send to the AI
            context: Full context data sent to the AI model
            force_refresh: Bypass cache if True
            cache_context: Optional stable subset of context used for cache key generation.
                          If not provided, the full context is used.
                          Use this when context contains volatile data (e.g., computed timestamps,
                          dynamic task lists) that would cause unnecessary cache misses.

        Returns:
            Dict with response, cached status, credits_used, and model_used
        """
        self._ensure_initialized()

        if feature not in AI_FEATURES:
            raise ValueError(f"Unknown AI feature: {feature}")

        feature_config = AI_FEATURES[feature]
        start_time = datetime.now(timezone.utc)

        # Use cache_context for key generation if provided, otherwise use full context
        key_context = cache_context if cache_context is not None else context

        # Check cache first if feature is cacheable
        if feature_config["cacheable"] and not force_refresh:
            cached = await ai_cache_service.get_cached_response(
                feature=feature, tenant_id=tenant_id, context=key_context
            )
            if cached:
                # Log cache hit (no credits charged)
                await self._log_usage(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    feature=feature,
                    credits_used=0,
                    latency_ms=0,
                    status="cached",
                    model="cached",
                )
                return {
                    "response": cached["response"],
                    "cached": True,
                    "credits_used": 0,
                    "model_used": "cached",
                }

            # If exact cache miss, try the stable fallback lookup before making API call
            # This prevents unnecessary Gemini calls when only volatile context changed
            fallback = await ai_cache_service.get_latest_cached_response(
                feature=feature, tenant_id=tenant_id
            )
            if fallback:
                logger.info(
                    f"Using stable fallback cache for {feature}/{tenant_id} (context hash changed)"
                )
                await self._log_usage(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    feature=feature,
                    credits_used=0,
                    latency_ms=0,
                    status="cached_fallback",
                    model="cached",
                )
                return {
                    "response": fallback["response"],
                    "cached": True,
                    "credits_used": 0,
                    "model_used": "cached",
                }

        is_root_admin = await self._is_root_admin_user(user_id)

        # Check credits before making API call
        credits_check = await self.check_credits(
            user_id, feature, bypass_limits=is_root_admin
        )
        if not credits_check["allowed"]:
            raise InsufficientCreditsError(
                message=credits_check["message"] or "Insufficient AI credits",
                required=credits_check["credits_needed"],
                available=credits_check["credits_remaining"],
            )

        # Select model based on credit level and get credit status for warnings
        credit_status = await self._select_model_and_check_credits(
            user_id, bypass_limits=is_root_admin
        )
        model = credit_status["model"]

        # Make AI API call
        try:
            response = await self._call_gemini(feature, prompt, context, model)
            latency_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            # Root admin uses these tools operationally and should not consume planner credits.
            if not is_root_admin:
                await self.subscription_service.increment_usage(
                    user_id=user_id,
                    resource_type="ai_credits",
                    amount=feature_config["credits"],
                )

            # Cache response if cacheable (use key_context for stable cache keys)
            if feature_config["cacheable"] and feature_config["ttl_hours"] > 0:
                await ai_cache_service.cache_response(
                    feature=feature,
                    tenant_id=tenant_id,
                    context=key_context,
                    response=response,
                    ttl_hours=feature_config["ttl_hours"],
                )

            # Log successful usage
            await self._log_usage(
                user_id=user_id,
                tenant_id=tenant_id,
                feature=feature,
                credits_used=feature_config["credits"],
                latency_ms=latency_ms,
                status="success",
                model=model,
            )

            # Calculate updated credits after deduction
            updated_remaining = None
            if credit_status["credits_remaining"] is not None:
                updated_remaining = (
                    credit_status["credits_remaining"] - feature_config["credits"]
                )
            updated_percent = None
            if credit_status["credits_limit"] and credit_status["credits_limit"] > 0:
                updated_percent = round(
                    (updated_remaining / credit_status["credits_limit"]) * 100, 1
                )

            result = {
                "response": response,
                "cached": False,
                "credits_used": 0 if is_root_admin else feature_config["credits"],
                "model_used": model,
                "credits_remaining": None
                if credit_status["credits_remaining"] is None
                else max(0, updated_remaining),
                "credits_percent": updated_percent,
            }

            # Include warning for frontend to display if credits are low
            if credit_status["low_credits_warning"]:
                result["warning"] = credit_status["low_credits_warning"]

            return result

        except InsufficientCreditsError:
            # Before raising, try to return cached data as fallback
            # This handles the case where credits ran out but we have cached insights
            if feature_config["cacheable"]:
                fallback = await ai_cache_service.get_latest_cached_response(
                    feature=feature, tenant_id=tenant_id
                )
                if fallback:
                    logger.info(
                        f"Returning cached fallback for {feature} due to insufficient credits"
                    )
                    await self._log_usage(
                        user_id=user_id,
                        tenant_id=tenant_id,
                        feature=feature,
                        credits_used=0,
                        latency_ms=0,
                        status="cached_fallback",
                        model="cached",
                    )
                    return {
                        "response": fallback["response"],
                        "cached": True,
                        "credits_used": 0,
                        "model_used": "cached_fallback",
                        "warning": "Showing cached insights (credits exhausted). Upgrade your plan for fresh analysis.",
                    }
            raise
        except Exception as e:
            latency_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            # Log error (no credits charged)
            await self._log_usage(
                user_id=user_id,
                tenant_id=tenant_id,
                feature=feature,
                credits_used=0,
                latency_ms=latency_ms,
                status="error",
                model=locals().get("model", "unknown"),
                error=str(e),
            )

            logger.error(f"AI generation error for {feature}: {str(e)}")

            # Fallback: Try to return cached data instead of erroring out
            # This provides a much better UX - stale insights > no insights
            if feature_config["cacheable"]:
                fallback = await ai_cache_service.get_latest_cached_response(
                    feature=feature, tenant_id=tenant_id
                )
                if fallback:
                    logger.info(
                        f"Returning cached fallback for {feature} after API error: {str(e)}"
                    )
                    return {
                        "response": fallback["response"],
                        "cached": True,
                        "credits_used": 0,
                        "model_used": "cached_fallback",
                        "warning": "Showing cached insights (AI service temporarily unavailable). Try refreshing later.",
                    }

            raise AIGenerationError(f"AI generation failed: {str(e)}")

    async def _call_gemini(
        self, feature: str, prompt: str, context: Dict[str, Any], model: str
    ) -> Dict[str, Any]:
        """
        Make the actual Gemini API call using the new SDK with proper async.

        Uses: await client.aio.models.generate_content()
        Reference: https://ai.google.dev/gemini-api/docs/migrate

        Handles specific error types:
        - Rate limiting (429) → AIRateLimitError
        - Content blocked → AIContentBlockedError
        - Service unavailable (503) → AIServiceUnavailableError
        - Quota exceeded (429 with quota message) → AIQuotaExceededError
        - Timeout → AITimeoutError
        - Invalid response → AIInvalidResponseError
        """
        import asyncio

        try:
            from google.genai import types

            feature_config = AI_FEATURES.get(feature, {})
            system_prompt = feature_config.get("system_prompt", "")

            # Format context into prompt
            context_str = json.dumps(context, indent=2, default=str)
            full_prompt = (
                f"{system_prompt}\n\nContext:\n{context_str}\n\nRequest:\n{prompt}"
            )

            # Configure generation settings per official SDK docs
            # Reference: https://googleapis.github.io/python-genai/
            generation_config = types.GenerateContentConfig(
                temperature=0.7,  # Balanced creativity for wedding planning
                max_output_tokens=2048,  # Reasonable limit for responses
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_ONLY_HIGH",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_ONLY_HIGH",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_MEDIUM_AND_ABOVE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_ONLY_HIGH",
                    ),
                ],
            )

            # Use async client.aio.models.generate_content for proper async
            # This is the new SDK pattern that doesn't block the event loop
            # Add timeout protection (60 seconds)
            try:
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=model, contents=full_prompt, config=generation_config
                    ),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                logger.error(f"Gemini API timeout (model={model})")
                raise AITimeoutError()

            # Check if response was blocked by safety filters
            if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                feedback = response.prompt_feedback
                if hasattr(feedback, "block_reason") and feedback.block_reason:
                    reason = str(feedback.block_reason).lower().replace("_", " ")
                    logger.warning(f"Content blocked by Gemini: {reason}")
                    raise AIContentBlockedError(reason=reason)

            # Check if we got any candidates
            if not response.candidates or len(response.candidates) == 0:
                logger.error("Gemini returned no candidates")
                raise AIInvalidResponseError()

            # Check candidate finish reason
            candidate = response.candidates[0]
            if hasattr(candidate, "finish_reason"):
                finish_reason = str(candidate.finish_reason).upper()
                if finish_reason == "SAFETY":
                    raise AIContentBlockedError(reason="safety filters")
                elif finish_reason == "RECITATION":
                    raise AIContentBlockedError(reason="recitation policy")

            # Extract text from response
            try:
                response_text = response.text
            except (AttributeError, ValueError) as e:
                logger.error(f"Failed to extract text from Gemini response: {e}")
                raise AIInvalidResponseError()

            if not response_text or not response_text.strip():
                logger.error("Gemini returned empty response")
                raise AIInvalidResponseError()

            # Log the raw response for debugging
            logger.info(f"Gemini raw response (first 500 chars): {response_text[:500]}")

            # Try to parse as JSON if expected
            try:
                # Sometimes Gemini wraps JSON in markdown code blocks
                text_to_parse = response_text.strip()
                if text_to_parse.startswith("```json"):
                    text_to_parse = text_to_parse[7:]  # Remove ```json
                if text_to_parse.startswith("```"):
                    text_to_parse = text_to_parse[3:]  # Remove ```
                if text_to_parse.endswith("```"):
                    text_to_parse = text_to_parse[:-3]  # Remove trailing ```
                text_to_parse = text_to_parse.strip()

                parsed = json.loads(text_to_parse)
                logger.info(
                    f"Successfully parsed JSON with keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}"
                )
                return parsed
            except json.JSONDecodeError as e:
                # Raise error instead of returning raw text — this triggers the
                # cached fallback path in generate(), which is much better than
                # returning {"text": ..., "raw": True} that breaks downstream
                # code expecting structured JSON keys like "insights", "suggestions", etc.
                logger.warning(
                    f"Failed to parse as JSON for {feature}: {e}. Raising AIInvalidResponseError."
                )
                raise AIInvalidResponseError()

        except (
            AIRateLimitError,
            AIContentBlockedError,
            AIServiceUnavailableError,
            AIQuotaExceededError,
            AITimeoutError,
            AIInvalidResponseError,
        ):
            # Re-raise our custom errors
            raise

        except Exception as e:
            # Try to import and handle SDK-specific errors
            # Reference: https://github.com/googleapis/python-genai - errors.APIError
            try:
                from google.genai import errors as genai_errors

                if isinstance(e, genai_errors.APIError):
                    error_code = getattr(e, "code", None)
                    error_message = getattr(e, "message", str(e))
                    logger.error(
                        f"Gemini APIError (code={error_code}): {error_message}"
                    )

                    # Handle specific error codes per Context7 docs
                    if error_code == 429:
                        if "quota" in error_message.lower():
                            raise AIQuotaExceededError()
                        raise AIRateLimitError()
                    elif error_code == 503:
                        raise AIServiceUnavailableError()
                    elif error_code in (401, 403):
                        raise AIGenerationError(
                            message="AI service authentication failed. Please contact support.",
                            error_code="auth_error",
                        )
                    elif error_code == 400:
                        if (
                            "safety" in error_message.lower()
                            or "blocked" in error_message.lower()
                        ):
                            raise AIContentBlockedError()
                        raise AIGenerationError(
                            message=f"Invalid AI request: {error_message}",
                            error_code="invalid_request",
                        )
                    elif error_code == 404:
                        raise AIGenerationError(
                            message="AI model not available. Please try again later.",
                            error_code="model_not_found",
                        )
            except ImportError:
                pass  # SDK not installed, fall through to generic handling

            # Fallback: Parse error string for common patterns
            error_str = str(e).lower()
            logger.error(f"Gemini API error (model={model}): {str(e)}")

            if (
                "429" in error_str
                or "rate limit" in error_str
                or "resource exhausted" in error_str
            ):
                if "quota" in error_str:
                    raise AIQuotaExceededError()
                raise AIRateLimitError()

            if (
                "503" in error_str
                or "service unavailable" in error_str
                or "overloaded" in error_str
            ):
                raise AIServiceUnavailableError()

            if (
                "401" in error_str
                or "403" in error_str
                or "invalid api key" in error_str
            ):
                raise AIGenerationError(
                    message="AI service authentication failed. Please contact support.",
                    error_code="auth_error",
                )

            if "timeout" in error_str:
                raise AITimeoutError()

            if "safety" in error_str or "blocked" in error_str:
                raise AIContentBlockedError()

            # Generic error for unhandled cases
            raise AIGenerationError(
                message="AI service encountered an unexpected error. Please try again.",
                error_code="unknown_error",
            )

    async def _log_usage(
        self,
        user_id: str,
        tenant_id: str,
        feature: str,
        credits_used: int,
        latency_ms: float,
        status: str,
        model: str,
        error: Optional[str] = None,
    ):
        """Log AI usage for analytics and auditing."""
        try:
            log_entry = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "feature": feature,
                "credits_used": credits_used,
                "latency_ms": latency_ms,
                "status": status,
                "model": model,
                "error": error,
                "created_at": datetime.now(timezone.utc),
            }
            await self.usage_log.insert_one(log_entry)
        except Exception as e:
            logger.error(f"Failed to log AI usage: {str(e)}")

    async def _send_low_credit_notification(
        self, user_id: str, credits_remaining: int, credits_limit: int
    ):
        """
        Send in-app notification when AI credits are running low.
        Only sends once per billing cycle to avoid spamming the planner.
        """
        try:
            # Get current billing period (first of the month)
            now = datetime.now(timezone.utc)
            billing_period = now.strftime("%Y-%m")

            # Check if we already sent a notification this billing cycle
            existing_alert = await self.low_credit_alerts.find_one(
                {"user_id": user_id, "billing_period": billing_period}
            )

            if existing_alert:
                # Already notified this billing cycle
                return

            # Record that we're sending this notification
            await self.low_credit_alerts.insert_one(
                {
                    "user_id": user_id,
                    "billing_period": billing_period,
                    "credits_remaining": credits_remaining,
                    "credits_limit": credits_limit,
                    "created_at": now,
                }
            )

            # Create in-app notification for the planner
            percent_remaining = round((credits_remaining / credits_limit) * 100, 1)
            await self.notification_service.create_notification(
                notification_data={
                    "title": "AI Credits Running Low",
                    "message": (
                        f"You have {credits_remaining} AI credits remaining ({percent_remaining}% of your {credits_limit} monthly limit). "
                        f"To continue using AI features without interruption, consider upgrading your plan. "
                        f"Your credits will reset at the start of your next billing cycle."
                    ),
                    "type": "warning",
                    "target_audience": "wedding_planners",
                    "user_id": user_id,  # Target this specific planner
                    "is_dismissible": True,
                    "priority": "high",
                },
                created_by="system",
            )

            logger.info(
                f"Sent low credit notification to user {user_id}: {credits_remaining}/{credits_limit} credits remaining"
            )

        except Exception as e:
            # Don't fail the AI request if notification fails
            logger.error(f"Failed to send low credit notification: {str(e)}")

    async def get_usage_metrics(
        self, period_days: int = 7, tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get AI usage metrics for admin dashboard.

        Args:
            period_days: Number of days to look back
            tenant_id: Optional tenant filter

        Returns:
            Dict with usage metrics and breakdowns
        """
        from datetime import timedelta

        start_date = datetime.now(timezone.utc) - timedelta(days=period_days)

        query = {"created_at": {"$gte": start_date}}
        if tenant_id:
            query["tenant_id"] = tenant_id

        # Aggregate daily usage
        daily_pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": {
                        "date": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$created_at",
                            }
                        },
                        "feature": "$feature",
                    },
                    "total_credits": {"$sum": "$credits_used"},
                    "total_requests": {"$sum": 1},
                    "cached_requests": {
                        "$sum": {"$cond": [{"$eq": ["$status", "cached"]}, 1, 0]}
                    },
                    "avg_latency": {"$avg": "$latency_ms"},
                }
            },
            {"$sort": {"_id.date": -1}},
        ]

        daily_usage = await self.usage_log.aggregate(daily_pipeline).to_list(
            length=None
        )

        # Top users by credits
        user_pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$tenant_id",
                    "total_credits": {"$sum": "$credits_used"},
                    "total_requests": {"$sum": 1},
                }
            },
            {"$sort": {"total_credits": -1}},
            {"$limit": 10},
        ]

        top_tenants = await self.usage_log.aggregate(user_pipeline).to_list(length=None)

        # Feature breakdown
        feature_pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$feature",
                    "total_credits": {"$sum": "$credits_used"},
                    "total_requests": {"$sum": 1},
                    "cache_hit_rate": {
                        "$avg": {"$cond": [{"$eq": ["$status", "cached"]}, 1, 0]}
                    },
                    "error_rate": {
                        "$avg": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}
                    },
                }
            },
        ]

        feature_breakdown = await self.usage_log.aggregate(feature_pipeline).to_list(
            length=None
        )

        # Model usage breakdown
        model_pipeline = [
            {"$match": {**query, "model": {"$ne": "cached"}}},
            {
                "$group": {
                    "_id": "$model",
                    "total_requests": {"$sum": 1},
                    "avg_latency": {"$avg": "$latency_ms"},
                }
            },
        ]

        model_breakdown = await self.usage_log.aggregate(model_pipeline).to_list(
            length=None
        )

        # Total summary
        total_credits = sum(f.get("total_credits", 0) for f in feature_breakdown)
        total_requests = sum(f.get("total_requests", 0) for f in feature_breakdown)

        return {
            "period_days": period_days,
            "models": {
                "primary": MODEL_PRIMARY,
                "economy": MODEL_ECONOMY,
                "low_credit_threshold": f"{LOW_CREDIT_THRESHOLD * 100:.0f}%",
            },
            "summary": {
                "total_credits_used": total_credits,
                "total_requests": total_requests,
                "unique_features": len(feature_breakdown),
            },
            "daily_usage": daily_usage,
            "top_tenants": top_tenants,
            "feature_breakdown": feature_breakdown,
            "model_breakdown": model_breakdown,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Singleton instance
ai_service = AIService()
