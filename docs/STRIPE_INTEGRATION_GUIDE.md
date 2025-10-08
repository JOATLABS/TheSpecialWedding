# Stripe Payment Integration Guide

This guide covers the complete Stripe payment integration for subscription billing and payment collection in the Wedding WebApp platform.

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [API Endpoints](#api-endpoints)
4. [Webhook Setup](#webhook-setup)
5. [Frontend Integration](#frontend-integration)
6. [Testing](#testing)
7. [Production Deployment](#production-deployment)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Stripe integration provides two key payment capabilities:

### 1. Platform Subscriptions
Wedding planners subscribe to service tiers (Starter, Professional, Enterprise) with recurring monthly or yearly billing.

### 2. Payment Collection for Couples
Wedding planners can collect payments from their clients (couples) for services, deposits, and final payments.

### Architecture
- **Backend**: FastAPI service layer (`app/services/stripe_service.py`)
- **API**: RESTful endpoints (`app/api/stripe_payment.py`)
- **Frontend**: React/Next.js components (`app/admin/billing/`)
- **Database**: MongoDB for subscription and customer tracking

---

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```bash
# Stripe Configuration
STRIPE_ENABLED=true
STRIPE_SECRET_KEY=sk_test_51SFZP3Q2Ad2DZVbaX5UXSd47vPqpgDMr9blpKpJjzuq3z0lQ3mADeOqZXITTuDbR3TvBW4xBY8BfEYMcpbu0MjKF008xIiay7T
STRIPE_PUBLISHABLE_KEY=pk_test_51SFZP3Q2Ad2DZVbapzahZ24Wjs6CWWMXMeg0XoB5VxCLMmcdF0xtJPm6GRWpsnhtNm3znrFJw2mEHYuuGWBZRTTf00PT0zcxrO
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_51SFZP3Q2Ad2DZVbapzahZ24Wjs6CWWMXMeg0XoB5VxCLMmcdF0xtJPm6GRWpsnhtNm3znrFJw2mEHYuuGWBZRTTf00PT0zcxrO
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

### Key Locations

| Purpose | Key Type | Location |
|---------|----------|----------|
| Backend API calls | Secret Key | `STRIPE_SECRET_KEY` (server-side only) |
| Frontend Stripe.js | Publishable Key | `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` |
| Webhook verification | Webhook Secret | `STRIPE_WEBHOOK_SECRET` |

**⚠️ SECURITY NOTE:**
- Never expose `STRIPE_SECRET_KEY` in frontend code
- Only use test keys (`sk_test_*`, `pk_test_*`) in development
- Rotate keys if accidentally exposed

---

## API Endpoints

### Base URL
- Development: `http://localhost:8000/admin/stripe`
- Production: `https://your-domain.com/admin/stripe`

### Authentication
All endpoints (except webhooks) require Bearer token authentication:
```bash
Authorization: Bearer <your_jwt_token>
```

### Endpoints

#### 1. Get Stripe Config
```http
GET /admin/stripe/config
```
Returns the publishable key for frontend initialization.

**Response:**
```json
{
  "publishable_key": "pk_test_...",
  "currency": "usd"
}
```

#### 2. Create Checkout Session
```http
POST /admin/stripe/create-checkout-session
```

**Request Body:**
```json
{
  "plan_id": "plan_professional",
  "billing_interval": "monthly",
  "success_url": "https://yourdomain.com/admin/billing/success?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://yourdomain.com/admin/billing",
  "trial_days": 0
}
```

**Response:**
```json
{
  "status": "success",
  "checkout_session": {
    "session_id": "cs_test_...",
    "url": "https://checkout.stripe.com/pay/cs_test_...",
    "customer_id": "cus_...",
    "expires_at": 1234567890
  }
}
```

#### 3. Get Checkout Session
```http
GET /admin/stripe/checkout-session/{session_id}
```

**Response:**
```json
{
  "status": "success",
  "session": {
    "id": "cs_test_...",
    "payment_status": "paid",
    "customer": "cus_...",
    "subscription": "sub_...",
    "amount_total": 4999,
    "currency": "usd"
  }
}
```

#### 4. Create Customer Portal Session
```http
POST /admin/stripe/create-portal-session
```

**Request Body:**
```json
{
  "return_url": "https://yourdomain.com/admin/billing"
}
```

**Response:**
```json
{
  "status": "success",
  "portal_url": "https://billing.stripe.com/session/..."
}
```

#### 5. Create Payment Intent (for Couple Payments)
```http
POST /admin/stripe/create-payment-intent
```

**Request Body:**
```json
{
  "amount": 500.00,
  "currency": "usd",
  "wedding_id": "wedding_123",
  "description": "Final payment for wedding services",
  "metadata": {
    "payment_type": "final_payment",
    "invoice_id": "INV-001"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "payment_intent": {
    "payment_intent_id": "pi_...",
    "client_secret": "pi_..._secret_...",
    "amount": 500.00,
    "currency": "usd",
    "status": "requires_payment_method"
  }
}
```

#### 6. Webhook Endpoint
```http
POST /admin/stripe/webhook
```

**Headers:**
```
stripe-signature: t=1234567890,v1=abcdef...
```

This endpoint is called by Stripe for events like:
- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

---

## Webhook Setup

### Step 1: Configure Webhook in Stripe Dashboard

1. Go to [Stripe Dashboard → Developers → Webhooks](https://dashboard.stripe.com/webhooks)
2. Click "Add endpoint"
3. Enter your webhook URL:
   - Development: `http://localhost:8000/admin/stripe/webhook`
   - Production: `https://your-domain.com/admin/stripe/webhook`

### Step 2: Select Events

Select these events to listen for:

#### Subscription Events
- ✅ `checkout.session.completed` - Payment successful, subscription created
- ✅ `customer.subscription.created` - Subscription activated
- ✅ `customer.subscription.updated` - Subscription changed (upgrade/downgrade)
- ✅ `customer.subscription.deleted` - Subscription cancelled
- ✅ `invoice.paid` - Recurring payment successful
- ✅ `invoice.payment_failed` - Payment failed, retry needed

### Step 3: Get Webhook Secret

After creating the webhook:
1. Click on the webhook endpoint
2. Click "Reveal" next to "Signing secret"
3. Copy the secret (starts with `whsec_`)
4. Add to `.env`:
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_your_secret_here
   ```

### Step 4: Test Webhook (Development)

Use Stripe CLI for local testing:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/admin/stripe/webhook

# Trigger test events
stripe trigger checkout.session.completed
stripe trigger invoice.paid
```

---

## Frontend Integration

### 1. Billing Page

Navigate to `/admin/billing` to see:
- Current subscription status
- Available plans
- Subscribe button (redirects to Stripe Checkout)
- Manage billing button (opens Customer Portal)

### 2. Success Page

After successful payment, users are redirected to `/admin/billing/success?session_id=XXX`

This page:
- Verifies the payment
- Shows payment confirmation
- Provides next steps
- Links to dashboard and billing

### 3. Customer Portal

The Customer Portal allows users to:
- Update payment methods
- View billing history
- Download invoices
- Cancel subscriptions
- Update billing address

---

## Testing

### Test Card Numbers

Use these test cards in Stripe Checkout:

| Card Number | Description |
|-------------|-------------|
| `4242 4242 4242 4242` | Succeeds immediately |
| `4000 0025 0000 3155` | Requires authentication (3D Secure) |
| `4000 0000 0000 9995` | Declines with insufficient_funds |
| `4000 0000 0000 0341` | Attaches and immediately expires |

- Use any future expiry date (e.g., `12/34`)
- Use any 3-digit CVC
- Use any valid ZIP code

### Test Workflow

1. **Subscription Signup**
   ```bash
   # Navigate to billing page
   http://localhost:3000/admin/billing

   # Select a plan and billing interval
   # Click "Subscribe"
   # Complete checkout with test card: 4242 4242 4242 4242
   # Verify redirect to success page
   ```

2. **Webhook Verification**
   ```bash
   # Check backend logs for webhook events
   docker logs wedding-api | grep "Processing webhook event"

   # Verify subscription in database
   mongo
   use wedding
   db.user_subscriptions.find({user_id: "your_user_id"})
   ```

3. **Customer Portal**
   ```bash
   # From billing page, click "Manage Billing"
   # Verify portal opens
   # Update payment method
   # Cancel subscription (test mode only)
   ```

4. **Payment Collection**
   ```bash
   # Use API to create payment intent
   curl -X POST http://localhost:8000/admin/stripe/create-payment-intent \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "amount": 100.00,
       "wedding_id": "wedding_123",
       "description": "Test payment"
     }'
   ```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] Replace test keys with live keys in `.env`
- [ ] Update `STRIPE_SECRET_KEY` to `sk_live_...`
- [ ] Update `STRIPE_PUBLISHABLE_KEY` to `pk_live_...`
- [ ] Configure production webhook endpoint
- [ ] Test webhook with live events
- [ ] Enable HTTPS (required for Stripe)
- [ ] Review Stripe account activation requirements
- [ ] Set up proper error monitoring
- [ ] Configure email notifications for failed payments

### Live Key Management

1. Go to [Stripe Dashboard → Developers → API Keys](https://dashboard.stripe.com/apikeys)
2. Toggle to "Live mode"
3. Copy live keys (they start with `sk_live_` and `pk_live_`)
4. Update production environment variables
5. **Never commit live keys to Git**

### Production Webhook Setup

1. Create webhook in live mode: `https://your-domain.com/admin/stripe/webhook`
2. Select same events as test mode
3. Get live webhook secret (`whsec_...`)
4. Update `STRIPE_WEBHOOK_SECRET` in production

### Monitoring

Monitor these metrics in production:

- Successful subscription signups
- Failed payment attempts
- Subscription churn rate
- Webhook delivery failures
- API error rates

Use Stripe Dashboard → Developers → Logs to debug issues.

---

## Troubleshooting

### Common Issues

#### 1. "Invalid API Key"
**Cause**: Wrong key or key not set
**Solution**:
```bash
# Verify key is set
echo $STRIPE_SECRET_KEY

# Restart backend after updating .env
docker restart wedding-api
```

#### 2. "No such customer"
**Cause**: Customer record not found
**Solution**: Check `stripe_customers` collection in MongoDB. Re-create customer if missing.

#### 3. "Webhook signature verification failed"
**Cause**: Wrong webhook secret or payload tampering
**Solution**:
```bash
# Get correct webhook secret from Stripe Dashboard
# Update STRIPE_WEBHOOK_SECRET in .env
# Restart backend
```

#### 4. Checkout redirects to error page
**Cause**: Checkout session creation failed
**Solution**: Check backend logs:
```bash
docker logs wedding-api | grep "Stripe error"
```

#### 5. "Cannot create subscription"
**Cause**: User already has active subscription
**Solution**: Cancel existing subscription first via Customer Portal

### Debug Mode

Enable detailed Stripe logging:

```python
# Add to app/services/stripe_service.py (development only)
import stripe
stripe.log = 'debug'
```

### Support Resources

- [Stripe Documentation](https://stripe.com/docs)
- [Stripe API Reference](https://stripe.com/docs/api)
- [Stripe Support](https://support.stripe.com)
- [Stripe Status Page](https://status.stripe.com)

---

## Security Best Practices

1. **Never expose secret keys** in frontend code or public repositories
2. **Always validate webhook signatures** to prevent fake events
3. **Use HTTPS in production** (required by Stripe)
4. **Implement rate limiting** on payment endpoints
5. **Log all payment events** for audit trails
6. **Monitor for suspicious activity** (rapid failed attempts, etc.)
7. **Keep Stripe library updated** to latest stable version
8. **Test error scenarios** (declined cards, expired cards, etc.)

---

## Next Steps

After completing the integration:

1. **Create Stripe Products in Dashboard**
   - Go to Products and manually create products
   - Copy product/price IDs to your subscription plans

2. **Configure Customer Portal**
   - Go to Settings → Billing → Customer Portal
   - Enable features (update payment, cancel subscription)
   - Customize branding

3. **Set Up Email Notifications**
   - Configure receipt emails
   - Set up payment failed notifications
   - Enable subscription renewal reminders

4. **Add Analytics**
   - Track conversion rates
   - Monitor MRR (Monthly Recurring Revenue)
   - Analyze churn patterns

5. **Implement Usage-Based Billing** (if needed)
   - For AI credits or other metered features
   - Use Stripe metering API

---

## Code Examples

### Backend: Create Checkout Session

```python
from app.services.stripe_service import stripe_service

# Create checkout session
session = stripe_service.create_checkout_session(
    user_id="user_123",
    plan_id="plan_professional",
    billing_interval="monthly",
    success_url="https://app.com/success",
    cancel_url="https://app.com/billing",
    trial_days=14
)

# Redirect user to session.url
```

### Frontend: Redirect to Checkout

```typescript
const handleSubscribe = async (planId: string) => {
  const response = await fetch('/admin/stripe/create-checkout-session', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      plan_id: planId,
      billing_interval: 'monthly'
    })
  });

  const data = await response.json();

  // Redirect to Stripe Checkout
  window.location.href = data.checkout_session.url;
};
```

### Handle Webhook Event

```python
@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    result = stripe_service.handle_webhook_event(payload, sig_header)
    return {"status": "success", "result": result}
```

---

## Changelog

### Version 1.0.0 (January 2025)
- ✅ Initial Stripe integration
- ✅ Subscription checkout flow
- ✅ Customer portal
- ✅ Webhook handling
- ✅ Payment collection for couples
- ✅ Frontend billing page
- ✅ Test mode support

---

## Support

For questions or issues with the Stripe integration:

1. Check this documentation first
2. Review Stripe Dashboard logs
3. Check backend application logs
4. Contact development team

**Emergency Contacts:**
- Backend: backend-team@thespecialwedding.com
- DevOps: devops@thespecialwedding.com
- Stripe Support: https://support.stripe.com
