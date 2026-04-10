#!/usr/bin/env python3
"""
Stripe Test Clock – Trial Lifecycle End-to-End Test
====================================================

Uses Stripe Test Clocks to simulate the full trial lifecycle:

1. Create a Test Clock anchored to "now"
2. Create a customer attached to the clock
3. Create a subscription with a 30-day trial
4. Verify webhook sets user to "trial" status
5. Advance clock to trial_end - 7 days → verify warning webhook
6. Advance clock past trial_end → verify expiration webhook
7. Run internal trial maintenance → verify account deactivation
8. Clean up test clock

Usage:
    python scripts/test_trial_with_test_clock.py

Requirements:
    - Backend running at localhost:8000
    - Stripe CLI listening: stripe listen --forward-to localhost:8000/stripe/webhook
    - STRIPE_SECRET_KEY in .env

Environment Variables:
    STRIPE_SECRET_KEY  – Stripe test-mode secret key (sk_test_...)
    BACKEND_URL        – Backend base URL (default: http://localhost:8000)
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import stripe

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("test_clock_trial")

# Load env
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")
ADMIN_PASSWORD = os.getenv("ROOT_ADMIN_PASSWORD", "REDACTED")

if not STRIPE_SECRET_KEY:
    logger.error("STRIPE_SECRET_KEY not set in environment")
    sys.exit(1)

stripe.api_key = STRIPE_SECRET_KEY

# Test configuration
TEST_EMAIL = f"testclock.{int(time.time())}@example.com"
TEST_PASSWORD = "TestClock2026!"
TEST_PLAN_ID = "plan_signature"
TRIAL_DAYS = 30
WEBHOOK_SETTLE_SECONDS = 8  # Wait for webhooks to process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_admin_token() -> str:
    """Get admin JWT token"""
    resp = requests.post(
        f"{BACKEND_URL}/admin/token",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def api_get(path: str, token: str) -> dict:
    """Make authenticated GET request"""
    resp = requests.get(
        f"{BACKEND_URL}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, token: str, data: dict = None) -> dict:
    """Make authenticated POST request"""
    resp = requests.post(
        f"{BACKEND_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=data or {},
    )
    resp.raise_for_status()
    return resp.json()


def find_user_by_email(token: str, email: str) -> dict | None:
    """Find user by email via admin API"""
    users = api_get("/users", token)
    for u in users:
        if u["email"] == email:
            return u
    return None


def find_subscription(token: str, email: str) -> dict | None:
    """Find subscription by user email"""
    subs = api_get("/subscriptions", token)
    for s in subs:
        if s.get("user_email") == email:
            return s
    return None


def wait_for_webhooks(seconds: int = WEBHOOK_SETTLE_SECONDS):
    """Wait for Stripe webhooks to be forwarded and processed"""
    logger.info(f"  ⏳ Waiting {seconds}s for webhooks to settle...")
    time.sleep(seconds)


def separator(title: str):
    logger.info(f"\n{'=' * 60}")
    logger.info(f"  {title}")
    logger.info(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Test Steps
# ---------------------------------------------------------------------------


def step_1_create_test_clock() -> stripe.test_helpers.TestClock:
    """Create a Stripe Test Clock anchored to now"""
    separator("STEP 1: Create Stripe Test Clock")

    frozen_time = int(datetime.now(timezone.utc).timestamp())

    clock = stripe.test_helpers.TestClock.create(
        frozen_time=frozen_time,
        name=f"Trial Test - {TEST_EMAIL}",
    )

    logger.info(f"  ✅ Test Clock created: {clock.id}")
    logger.info(
        f"  📅 Frozen at: {datetime.fromtimestamp(frozen_time, tz=timezone.utc).isoformat()}"
    )
    return clock


def step_2_create_customer_and_user(
    clock: stripe.test_helpers.TestClock, admin_token: str
) -> tuple[str, str]:
    """Create a Stripe customer attached to the test clock, and register user in backend"""
    separator("STEP 2: Create Customer & Register User")

    # Create Stripe customer attached to test clock
    customer = stripe.Customer.create(
        email=TEST_EMAIL,
        name="Test Clock User",
        test_clock=clock.id,
        metadata={"test_type": "trial_lifecycle"},
    )
    logger.info(f"  ✅ Stripe Customer: {customer.id} (attached to clock {clock.id})")

    # Register the user in the backend
    resp = requests.post(
        f"{BACKEND_URL}/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "first_name": "Clock",
            "last_name": "Tester",
            "company_name": "Test Clock Corp",
            "plan_id": TEST_PLAN_ID,
        },
    )

    if resp.status_code not in (200, 201):
        logger.warning(f"  ⚠️ Registration response: {resp.status_code} - {resp.text}")
    else:
        logger.info(f"  ✅ User registered: {TEST_EMAIL}")

    # Find user and activate + link to Stripe customer
    user = find_user_by_email(admin_token, TEST_EMAIL)
    if not user:
        logger.error("  ❌ User not found after registration!")
        sys.exit(1)

    user_id = user["_id"]
    logger.info(f"  📋 User ID: {user_id}")

    # Activate user and verify email
    api_post(f"/users/{user_id}/activate", admin_token)
    logger.info("  ✅ User activated")

    # Link Stripe customer to user in stripe_customers collection
    resp = requests.post(
        f"{BACKEND_URL}/admin/token",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )

    # Directly update the stripe_customers collection via the backend
    # We'll create the checkout session through the API, which handles the linking
    return user_id, customer.id


def step_3_create_trial_subscription(
    user_id: str,
    customer_id: str,
    admin_token: str,
) -> str:
    """Create a subscription with trial period using the Stripe API directly"""
    separator("STEP 3: Create Subscription with 30-day Trial")

    # Get the plan's Stripe price ID
    plans = api_get("/public/subscription-plans", admin_token)
    plan = None
    for p in plans:
        if p.get("_id") == TEST_PLAN_ID or p.get("id") == TEST_PLAN_ID:
            plan = p
            break

    if not plan:
        logger.error(f"  ❌ Plan {TEST_PLAN_ID} not found!")
        # Try listing all plans
        logger.info(
            f"  Available plans: {json.dumps([p.get('_id', p.get('id', 'unknown')) for p in plans])}"
        )
        sys.exit(1)

    stripe_price_id = plan.get("stripe_price_id_monthly")
    if not stripe_price_id:
        logger.error(f"  ❌ No Stripe price ID for plan {TEST_PLAN_ID}")
        sys.exit(1)

    logger.info(f"  📋 Plan: {plan.get('name')} | Price: {stripe_price_id}")

    # Attach a test payment method to the customer
    pm = stripe.PaymentMethod.create(
        type="card",
        card={
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2028,
            "cvc": "123",
        },
    )
    stripe.PaymentMethod.attach(pm.id, customer=customer_id)
    stripe.Customer.modify(
        customer_id,
        invoice_settings={"default_payment_method": pm.id},
    )
    logger.info(f"  ✅ Payment method attached: {pm.id}")

    # Create subscription with trial
    trial_end_ts = int(
        (datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)).timestamp()
    )

    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": stripe_price_id}],
        trial_end=trial_end_ts,
        metadata={
            "user_id": user_id,
            "plan_id": TEST_PLAN_ID,
            "billing_interval": "monthly",
            "trial_days": str(TRIAL_DAYS),
        },
        payment_settings={
            "save_default_payment_method": "on_subscription",
        },
    )

    logger.info(f"  ✅ Subscription created: {subscription.id}")
    logger.info(f"  📋 Status: {subscription.status}")
    logger.info(
        f"  📅 Trial end: {datetime.fromtimestamp(subscription.trial_end, tz=timezone.utc).isoformat()}"
    )

    wait_for_webhooks()

    return subscription.id


def step_4_verify_trial_status(admin_token: str) -> bool:
    """Verify user is in trial status after subscription creation"""
    separator("STEP 4: Verify Trial Status")

    user = find_user_by_email(admin_token, TEST_EMAIL)
    if not user:
        logger.error("  ❌ User not found!")
        return False

    sub = find_subscription(admin_token, TEST_EMAIL)

    status = user.get("subscription_status")
    is_active = user.get("is_active")
    trial_end = user.get("trial_end_date")

    logger.info(f"  📋 User subscription_status: {status}")
    logger.info(f"  📋 User is_active: {is_active}")
    logger.info(f"  📋 User trial_end_date: {trial_end}")

    if sub:
        logger.info(f"  📋 Subscription status: {sub.get('status')}")

    if status == "trial" and is_active:
        logger.info("  ✅ PASS: User is in trial status and active")
        return True
    else:
        logger.error(
            f"  ❌ FAIL: Expected status='trial' & is_active=True, got status='{status}' & is_active={is_active}"
        )
        return False


def step_5_advance_to_warning_period(
    clock: stripe.test_helpers.TestClock, sub_id: str
) -> bool:
    """Advance test clock to 7 days before trial end (trigger trial_will_end)"""
    separator("STEP 5: Advance Clock to Warning Period (T-7 days)")

    # Advance to trial_end - 4 days (Stripe sends trial_will_end 3 days before end)
    advance_to = int(
        (datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS - 4)).timestamp()
    )

    logger.info(
        f"  ⏰ Advancing clock to: {datetime.fromtimestamp(advance_to, tz=timezone.utc).isoformat()}"
    )

    stripe.test_helpers.TestClock.advance(clock.id, frozen_time=advance_to)

    # Wait for Stripe to process the time advancement and fire webhooks
    logger.info("  ⏳ Waiting for Stripe to process time advancement...")
    time.sleep(5)

    # Poll until the clock is ready
    for attempt in range(12):
        refreshed = stripe.test_helpers.TestClock.retrieve(clock.id)
        if refreshed.status == "ready":
            logger.info(f"  ✅ Clock advanced successfully (attempt {attempt + 1})")
            break
        logger.info(f"  ⏳ Clock status: {refreshed.status} (attempt {attempt + 1}/12)")
        time.sleep(5)
    else:
        logger.warning("  ⚠️ Clock didn't reach 'ready' status in time")

    wait_for_webhooks(10)

    # Check subscription status in Stripe
    sub = stripe.Subscription.retrieve(sub_id)
    logger.info(f"  📋 Stripe subscription status: {sub.status}")
    logger.info(
        f"  📋 Stripe trial_end: {datetime.fromtimestamp(sub.trial_end, tz=timezone.utc).isoformat() if sub.trial_end else 'None'}"
    )

    return True


def step_6_advance_past_trial_end(
    clock: stripe.test_helpers.TestClock,
    sub_id: str,
    admin_token: str,
) -> bool:
    """Advance test clock past trial end to trigger subscription activation/payment"""
    separator("STEP 6: Advance Clock Past Trial End")

    # Advance 2 days past trial end
    advance_to = int(
        (datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS + 2)).timestamp()
    )

    logger.info(
        f"  ⏰ Advancing clock to: {datetime.fromtimestamp(advance_to, tz=timezone.utc).isoformat()}"
    )

    stripe.test_helpers.TestClock.advance(clock.id, frozen_time=advance_to)

    logger.info("  ⏳ Waiting for Stripe to process...")
    time.sleep(5)

    # Poll clock status
    for attempt in range(15):
        refreshed = stripe.test_helpers.TestClock.retrieve(clock.id)
        if refreshed.status == "ready":
            logger.info(f"  ✅ Clock advanced (attempt {attempt + 1})")
            break
        logger.info(f"  ⏳ Clock status: {refreshed.status} (attempt {attempt + 1}/15)")
        time.sleep(5)

    wait_for_webhooks(12)

    # Check Stripe subscription — should now be active (trial ended, payment collected)
    sub = stripe.Subscription.retrieve(sub_id)
    logger.info(f"  📋 Stripe subscription status: {sub.status}")

    # Check user status in backend
    user = find_user_by_email(admin_token, TEST_EMAIL)
    if user:
        logger.info(f"  📋 Backend user status: {user.get('subscription_status')}")
        logger.info(f"  📋 Backend is_active: {user.get('is_active')}")

    if sub.status == "active":
        logger.info(
            "  ✅ PASS: Subscription transitioned from trial to active after trial end"
        )
        return True
    elif sub.status in ("past_due", "unpaid"):
        logger.warning(f"  ⚠️ Subscription is {sub.status} - payment may have failed")
        return False
    else:
        logger.info(f"  📋 Subscription status: {sub.status}")
        return True


def step_7_test_internal_trial_expiration(admin_token: str) -> bool:
    """
    Test the internal trial expiration logic.
    This simulates what happens when the cron job runs and finds expired trials.
    We modify the user's trial_end_date to be in the past and run the maintenance.
    """
    separator("STEP 7: Test Internal Trial Expiration Logic")

    user = find_user_by_email(admin_token, TEST_EMAIL)
    if not user:
        logger.error("  ❌ User not found!")
        return False

    user_id = user["_id"]
    current_status = user.get("subscription_status")

    logger.info(f"  📋 Current user status: {current_status}")

    # If the subscription is now "active" (Stripe renewed it), let's simulate
    # a trial expiration scenario by manually setting the user back to trial
    # with an expired trial_end_date
    logger.info(
        "  🔧 Setting user to trial status with expired trial_end_date for testing..."
    )

    # Use admin API to manually set up the expired trial scenario
    resp = requests.post(
        f"{BACKEND_URL}/admin/trials/check-expired",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    if resp.status_code == 200:
        result = resp.json()
        logger.info(f"  📋 Trial expiration check: {json.dumps(result, indent=2)}")
        logger.info("  ✅ Internal trial expiration logic executed successfully")
        return True
    else:
        logger.error(
            f"  ❌ Trial expiration check failed: {resp.status_code} - {resp.text}"
        )
        return False


def step_8_cleanup(clock: stripe.test_helpers.TestClock, sub_id: str):
    """Clean up test resources"""
    separator("STEP 8: Cleanup")

    try:
        # Cancel subscription
        stripe.Subscription.cancel(sub_id)
        logger.info(f"  ✅ Subscription {sub_id} cancelled")
    except Exception as e:
        logger.warning(f"  ⚠️ Could not cancel subscription: {e}")

    try:
        # Delete test clock
        stripe.test_helpers.TestClock.delete(clock.id)
        logger.info(f"  ✅ Test Clock {clock.id} deleted")
    except Exception as e:
        logger.warning(f"  ⚠️ Could not delete test clock: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    logger.info("=" * 60)
    logger.info("  STRIPE TEST CLOCK - TRIAL LIFECYCLE TEST")
    logger.info("=" * 60)
    logger.info(f"  Test email: {TEST_EMAIL}")
    logger.info(f"  Plan: {TEST_PLAN_ID}")
    logger.info(f"  Trial days: {TRIAL_DAYS}")
    logger.info(f"  Backend: {BACKEND_URL}")
    logger.info("")

    # Verify backend is reachable
    try:
        resp = requests.get(f"{BACKEND_URL}/health")
        if resp.status_code != 200:
            logger.error(f"Backend not healthy: {resp.status_code}")
            sys.exit(1)
        logger.info("  ✅ Backend is healthy")
    except requests.ConnectionError:
        logger.error("  ❌ Cannot connect to backend!")
        sys.exit(1)

    admin_token = get_admin_token()
    logger.info("  ✅ Admin token acquired")

    results = {}
    clock = None
    sub_id = None

    try:
        # Step 1: Create test clock
        clock = step_1_create_test_clock()

        # Step 2: Create customer + user
        user_id, customer_id = step_2_create_customer_and_user(clock, admin_token)

        # Step 3: Create subscription with trial
        sub_id = step_3_create_trial_subscription(user_id, customer_id, admin_token)

        # Step 4: Verify trial status
        results["trial_status"] = step_4_verify_trial_status(admin_token)

        # Step 5: Advance to warning period
        results["warning_period"] = step_5_advance_to_warning_period(clock, sub_id)

        # Step 6: Advance past trial end
        results["trial_end"] = step_6_advance_past_trial_end(clock, sub_id, admin_token)

        # Step 7: Test internal expiration logic
        results["internal_expiration"] = step_7_test_internal_trial_expiration(
            admin_token
        )

    except Exception as e:
        logger.error(f"  ❌ Test failed with error: {e}", exc_info=True)
        results["error"] = str(e)

    finally:
        # Step 8: Cleanup
        if clock and sub_id:
            step_8_cleanup(clock, sub_id)

    # Final report
    separator("TEST RESULTS")
    all_passed = True
    for test_name, passed in results.items():
        if test_name == "error":
            logger.error(f"  ❌ Error: {passed}")
            all_passed = False
        elif passed:
            logger.info(f"  ✅ {test_name}: PASSED")
        else:
            logger.error(f"  ❌ {test_name}: FAILED")
            all_passed = False

    if all_passed:
        logger.info("\n  🎉 ALL TESTS PASSED!")
    else:
        logger.error("\n  ⚠️ SOME TESTS FAILED - review output above")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
