from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.services.stripe_service import stripe_service
from app.services.ai_service import AIService
from app.core.database import mongo

router = APIRouter()

@router.post("/credits/purchase-session")
async def create_credit_purchase_session(
    request: Dict[str, Any] = Body(...),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Creates a Stripe Checkout Session for a one-time AI Credit purchase.
    Body: { "credits": 50, "amount_usd": 5, "wedding_id": "..." }
    """
    credits = request.get("credits", 50)
    amount_usd = request.get("amount_usd", 5.0)
    wedding_id = request.get("wedding_id")

    if not wedding_id:
        raise HTTPException(status_code=400, detail="Missing wedding_id")

    try:
        # Create a one-time price session
        import stripe
        from app.core.settings import settings
        stripe.api_key = settings.stripe_secret_key

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{credits} AI Credits',
                        'description': 'One-time purchase of AI credits',
                    },
                    'unit_amount': int(amount_usd * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{settings.frontend_url}/admin/weddings/{wedding_id}/settings?credits_added=true",
            cancel_url=f"{settings.frontend_url}/admin/weddings/{wedding_id}/settings?credits_cancelled=true",
            metadata={
                "type": "ai_credit_topup",
                "wedding_id": wedding_id,
                "credits": str(credits),
                "user_id": str(current_user.user_data.get("_id"))
            }
        )

        return {"url": session.url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/credits/webhook-handler")
async def handle_credit_webhook(event: Dict[str, Any] = Body(...)):
    """
    Internal handler called by the main Stripe webhook for credit top-ups.
    This logic should ideally be inside StripeService, but for now we put it here
    or call it from the main webhook.
    """
    # This might be redundant if we modify StripeService.
    # Let's modify StripeService instead to handle the metadata.
    pass
