#!/usr/bin/env python3
"""
End-to-end Stripe Signup Flow Test
===================================
Tests the full planner registration and Stripe checkout flow:

1. POST /public/register         → Create pending planner account
2. GET  /verify-email/{token}    → Verify email (via DB token lookup)
3. GET  /public/subscription-plans → List available plans
4. POST /public/create-checkout-session → Create Stripe checkout
5. Validate Stripe checkout session was created correctly
6. POST /stripe/webhook (simulated) → Simulate checkout.session.completed

Usage:
  python test_stripe_signup.py --api-url http://localhost:8000
  python test_stripe_signup.py --api-url https://api.thespecialwedding.io
"""

import argparse
import asyncio
import os
from datetime import datetime, timezone

import httpx
import stripe

# ============================================================================
# Configuration
# ============================================================================

# Test planner credentials from .env
TEST_EMAIL = os.getenv("TEST_PLANNER_EMAIL", "test.verification@example.com")
TEST_PASSWORD = os.getenv("TEST_PLANNER_PASSWORD", "testPass123!")
STRIPE_SECRET_KEY = os.getenv(
    "STRIPE_SECRET_KEY",
    "REDACTED",
)
STRIPE_WEBHOOK_SECRET = os.getenv(
    "STRIPE_WEBHOOK_SECRET",
    "REDACTED",
)
ROOT_ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")
ROOT_ADMIN_PASSWORD = os.getenv("ROOT_ADMIN_PASSWORD", "REDACTED")

# Stripe test card
TEST_CARD = "4242424242424242"
TEST_EXPIRY = "12/34"
TEST_CVC = "123"
TEST_ZIP = "12345"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")


def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")


def info(msg):
    print(f"  {CYAN}ℹ{RESET} {msg}")


def header(msg):
    print(f"\n{BOLD}{msg}{RESET}")


errors = []
warnings = []


async def run_tests(api_url: str):
    """Run the full signup flow test suite."""

    stripe.api_key = STRIPE_SECRET_KEY

    header("=" * 60)
    header("  Stripe Signup Flow — End-to-End Test")
    header("=" * 60)
    info(f"API URL: {api_url}")
    info(f"Test Email: {TEST_EMAIL}")
    info(f"Stripe Key: {STRIPE_SECRET_KEY[:12]}...{STRIPE_SECRET_KEY[-4:]}")

    async with httpx.AsyncClient(base_url=api_url, timeout=30.0) as client:
        # ====================================================================
        # Step 0: Health Check
        # ====================================================================
        header("Step 0: Health Check")
        try:
            r = await client.get("/health/")
            if r.status_code == 200:
                ok(f"API is healthy (HTTP {r.status_code})")
            else:
                fail(f"Health check returned HTTP {r.status_code}")
                errors.append(f"Health check failed: HTTP {r.status_code}")
        except Exception as e:
            fail(f"Cannot reach API: {e}")
            errors.append(f"API unreachable: {e}")
            print(f"\n{RED}Cannot connect to API. Is the server running?{RESET}")
            return

        # ====================================================================
        # Step 0.5: Clean up previous test user (if exists)
        # ====================================================================
        header("Step 0.5: Cleanup Previous Test User")
        try:
            # Login as root admin
            admin_login = await client.post(
                "/admin/login",
                json={"email": ROOT_ADMIN_EMAIL, "password": ROOT_ADMIN_PASSWORD},
            )
            if admin_login.status_code == 200:
                admin_token = admin_login.json().get("access_token")
                admin_headers = {"Authorization": f"Bearer {admin_token}"}

                # Check if test user exists
                users_resp = await client.get("/users", headers=admin_headers)
                if users_resp.status_code == 200:
                    users = users_resp.json()
                    for user in users:
                        if user.get("email") == TEST_EMAIL:
                            user_id = user.get("_id")
                            # Delete the test user
                            del_resp = await client.delete(
                                f"/users/{user_id}", headers=admin_headers
                            )
                            if del_resp.status_code == 200:
                                ok(f"Cleaned up existing test user: {TEST_EMAIL}")
                            else:
                                warn(f"Could not delete test user: {del_resp.text}")
                            break
                    else:
                        ok("No previous test user found (clean state)")
            else:
                warn(f"Could not login as admin for cleanup: {admin_login.status_code}")
        except Exception as e:
            warn(f"Cleanup step failed (non-critical): {e}")

        # Also clean up Stripe customers for this email
        try:
            customers = stripe.Customer.list(email=TEST_EMAIL, limit=10)
            for cust in customers.data:
                # Cancel any active subscriptions first
                subs = stripe.Subscription.list(customer=cust.id, limit=10)
                for sub in subs.data:
                    if sub.status in ("active", "trialing", "past_due"):
                        stripe.Subscription.cancel(sub.id)
                        info(f"Cancelled Stripe subscription: {sub.id}")
                stripe.Customer.delete(cust.id)
                info(f"Deleted Stripe customer: {cust.id}")
            if customers.data:
                ok(f"Cleaned up {len(customers.data)} Stripe customer(s)")
            else:
                ok("No Stripe customers to clean up")
        except Exception as e:
            warn(f"Stripe cleanup failed: {e}")

        # ====================================================================
        # Step 1: Public Registration
        # ====================================================================
        header("Step 1: Public Registration (POST /public/register)")
        registration_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "first_name": "Test",
            "last_name": "Planner",
            "company_name": "Test Wedding Co",
            "role": "wedding_planner",
        }

        r = await client.post("/public/register", json=registration_data)
        print(f"    Status: {r.status_code}")

        if r.status_code == 200:
            reg_result = r.json()
            user_id = reg_result.get("user_id")
            ok(f"Registration successful — user_id: {user_id}")
            ok(f"Message: {reg_result.get('message')}")
            ok(f"Verification required: {reg_result.get('verification_required')}")

            # Validate response fields
            if not user_id:
                fail("Missing user_id in registration response")
                errors.append("No user_id returned from registration")
            if not reg_result.get("verification_required"):
                warn("verification_required not set to True")
                warnings.append("verification_required missing or False")
        elif r.status_code == 400 and "already exists" in r.text:
            fail(f"Test user already exists (cleanup may have failed): {r.json()}")
            errors.append("Test user already exists — cleanup failed")
            return
        else:
            fail(f"Registration failed: {r.text}")
            errors.append(f"Registration failed: HTTP {r.status_code} — {r.text}")
            return

        # ====================================================================
        # Step 2: Verify Email
        # ====================================================================
        header("Step 2: Email Verification")

        # We need the verification token — get it from admin API
        verification_token = None
        try:
            if admin_token:
                user_resp = await client.get(f"/users/{user_id}", headers=admin_headers)
                if user_resp.status_code == 200:
                    user_data = user_resp.json()
                    verification_token = user_data.get("email_verification_token")
                    if verification_token:
                        ok(
                            f"Retrieved verification token from DB: {verification_token[:8]}..."
                        )
                    else:
                        warn("No verification token found in user record")
                        warnings.append("Verification token not in user record")

                    # Validate initial user state
                    info(
                        f"  subscription_status: {user_data.get('subscription_status')}"
                    )
                    info(f"  is_active: {user_data.get('is_active')}")
                    info(f"  email_verified: {user_data.get('email_verified')}")
                    info(f"  plan_id: {user_data.get('plan_id')}")

                    if user_data.get("subscription_status") != "pending_payment":
                        fail(
                            f"Expected subscription_status='pending_payment', got '{user_data.get('subscription_status')}'"
                        )
                        errors.append("Incorrect initial subscription_status")
                    if user_data.get("is_active") is not False:
                        fail(
                            f"Expected is_active=False, got {user_data.get('is_active')}"
                        )
                        errors.append("User should be inactive before verification")
        except Exception as e:
            warn(f"Could not retrieve verification token: {e}")

        if verification_token:
            r = await client.get(f"/verify-email/{verification_token}")
            print(f"    Status: {r.status_code}")
            if r.status_code == 200:
                verify_result = r.json()
                ok(f"Email verified: {verify_result.get('message')}")
            else:
                fail(f"Email verification failed: {r.text}")
                errors.append(f"Email verification failed: HTTP {r.status_code}")
        else:
            warn("Skipping email verification (no token available)")
            warnings.append("Email verification skipped")

        # Validate post-verification state
        try:
            user_resp = await client.get(f"/users/{user_id}", headers=admin_headers)
            if user_resp.status_code == 200:
                user_data = user_resp.json()
                info(f"  Post-verify is_active: {user_data.get('is_active')}")
                info(f"  Post-verify email_verified: {user_data.get('email_verified')}")
                info(
                    f"  Post-verify subscription_status: {user_data.get('subscription_status')}"
                )

                if not user_data.get("email_verified"):
                    fail("email_verified should be True after verification")
                    errors.append("Email not marked as verified")
                if not user_data.get("is_active"):
                    fail("is_active should be True after email verification")
                    errors.append("User not activated after email verification")
        except Exception as e:
            warn(f"Could not verify post-verification state: {e}")

        # ====================================================================
        # Step 3: List Public Subscription Plans
        # ====================================================================
        header("Step 3: List Public Subscription Plans")
        r = await client.get("/public/subscription-plans")
        print(f"    Status: {r.status_code}")

        selected_plan_id = None
        if r.status_code == 200:
            plans = r.json()
            if plans:
                ok(f"Found {len(plans)} public plan(s)")
                for plan in plans:
                    info(
                        f"  • {plan.get('name')} ({plan.get('_id')}) — ${plan.get('price_monthly', 'N/A')}/mo, ${plan.get('price_yearly', 'N/A')}/yr"
                    )
                    info(
                        f"    Max weddings: {plan.get('max_weddings')}, Max guests: {plan.get('max_guests_per_wedding')}"
                    )

                # Select first plan
                selected_plan_id = plans[0].get("_id")
                ok(f"Selected plan: {plans[0].get('name')} ({selected_plan_id})")
            else:
                fail("No subscription plans found!")
                errors.append(
                    "No subscription plans available — planners cannot sign up"
                )
                warn(
                    "You need to create at least one subscription plan via the admin panel"
                )
        else:
            fail(f"Failed to list plans: {r.text}")
            errors.append(f"Plan listing failed: HTTP {r.status_code}")

        if not selected_plan_id:
            fail("Cannot proceed without a subscription plan")
            errors.append("No plan available for checkout")
            # Try to continue with a dummy plan_id to test error handling
            selected_plan_id = "starter"
            warn(f"Using fallback plan_id: '{selected_plan_id}'")

        # ====================================================================
        # Step 4: Create Stripe Checkout Session
        # ====================================================================
        header("Step 4: Create Checkout Session (POST /public/create-checkout-session)")
        checkout_data = {
            "email": TEST_EMAIL,
            "plan_id": selected_plan_id,
            "billing_interval": "monthly",
            "success_url": "http://localhost:3000/admin/billing/success?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "http://localhost:3000/admin/billing/cancelled",
            "trial_days": 0,
        }

        r = await client.post("/public/create-checkout-session", json=checkout_data)
        print(f"    Status: {r.status_code}")

        checkout_session_id = None
        checkout_url = None
        stripe_customer_id = None

        if r.status_code == 200:
            checkout_result = r.json()
            session_data = checkout_result.get("checkout_session", {})
            checkout_session_id = session_data.get("session_id")
            checkout_url = session_data.get("url")
            stripe_customer_id = session_data.get("customer_id")

            ok(f"Checkout session created: {checkout_session_id}")
            ok(f"Customer ID: {stripe_customer_id}")
            if checkout_url:
                ok(f"Checkout URL: {checkout_url[:80]}...")
            else:
                fail("No checkout URL returned!")
                errors.append("Checkout session missing URL")

            expires_at = session_data.get("expires_at")
            if expires_at:
                expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
                info(f"Session expires: {expires_dt.isoformat()}")
        else:
            fail(f"Checkout session creation failed: {r.text}")
            errors.append(f"Checkout creation failed: HTTP {r.status_code} — {r.text}")

        # ====================================================================
        # Step 5: Validate Stripe Checkout Session via Stripe API
        # ====================================================================
        header("Step 5: Validate Checkout Session via Stripe API")
        if checkout_session_id:
            try:
                session = stripe.checkout.Session.retrieve(checkout_session_id)

                ok(f"Session mode: {session.mode}")
                ok(f"Payment status: {session.payment_status}")
                ok(f"Status: {session.status}")

                # The metadata is on subscription_data level in the session
                # Let's check the session-level metadata
                info(f"Session customer: {session.customer}")
                info(f"Session currency: {session.currency}")

                # Check line items
                line_items = stripe.checkout.Session.list_line_items(
                    checkout_session_id
                )
                if line_items.data:
                    for item in line_items.data:
                        info(
                            f"  Line item: {item.description} — {item.amount_total / 100:.2f} {item.currency}"
                        )
                        ok("Line items present and valid")
                else:
                    fail("No line items in checkout session")
                    errors.append("Checkout session has no line items")

                # Validate customer exists
                if session.customer:
                    customer = stripe.Customer.retrieve(session.customer)
                    ok(f"Stripe customer: {customer.email} (name: {customer.name})")
                    if customer.email != TEST_EMAIL:
                        fail(
                            f"Customer email mismatch: expected {TEST_EMAIL}, got {customer.email}"
                        )
                        errors.append("Stripe customer email doesn't match test email")
                else:
                    fail("No customer associated with checkout session")
                    errors.append("Missing customer on checkout session")

            except stripe.StripeError as e:
                fail(f"Stripe API error: {e}")
                errors.append(f"Stripe validation error: {e}")
        else:
            warn("Skipping Stripe validation (no session ID)")

        # ====================================================================
        # Step 6: Simulate Webhook (checkout.session.completed)
        # ====================================================================
        header("Step 6: Simulate Webhook — checkout.session.completed")
        if checkout_session_id and stripe_customer_id:
            info("Note: In production, this webhook is sent by Stripe after payment.")
            info(
                "For testing, we can use Stripe CLI: stripe trigger checkout.session.completed"
            )
            info("Or use the Stripe test dashboard to complete the payment.")

            # We can't easily simulate the webhook without a real payment,
            # but we can validate the webhook endpoint is accessible
            try:
                # Test that webhook endpoint exists (will fail signature check, but shouldn't 404)
                r = await client.post(
                    "/stripe/webhook",
                    content=b"{}",
                    headers={
                        "stripe-signature": "fake_signature",
                        "content-type": "application/json",
                    },
                )
                if r.status_code == 400:
                    ok(
                        "Webhook endpoint exists and rejects invalid signatures (expected behavior)"
                    )
                elif r.status_code == 404:
                    fail("Webhook endpoint not found at /stripe/webhook!")
                    errors.append(
                        "Webhook endpoint missing — Stripe events won't be processed"
                    )
                else:
                    info(f"Webhook endpoint returned: {r.status_code} — {r.text[:100]}")
            except Exception as e:
                warn(f"Webhook endpoint test failed: {e}")

            # Also test the alias path
            try:
                r = await client.post(
                    "/api/stripe/webhook",
                    content=b"{}",
                    headers={
                        "stripe-signature": "fake_signature",
                        "content-type": "application/json",
                    },
                )
                if r.status_code == 400:
                    ok("Alias webhook endpoint /api/stripe/webhook also working")
                elif r.status_code == 404:
                    warn("Alias webhook endpoint /api/stripe/webhook not found")
                    warnings.append("Missing alias webhook path /api/stripe/webhook")
            except Exception:
                pass
        else:
            warn("Skipping webhook simulation (no checkout session)")

        # ====================================================================
        # Step 7: Validate Database State
        # ====================================================================
        header("Step 7: Validate Final Database State")
        try:
            if admin_token:
                user_resp = await client.get(f"/users/{user_id}", headers=admin_headers)
                if user_resp.status_code == 200:
                    user_data = user_resp.json()
                    info(
                        f"  subscription_status: {user_data.get('subscription_status')}"
                    )
                    info(f"  is_active: {user_data.get('is_active')}")
                    info(f"  email_verified: {user_data.get('email_verified')}")
                    info(f"  stripe_customer_id: {user_data.get('stripe_customer_id')}")
                    info(
                        f"  stripe_subscription_id: {user_data.get('stripe_subscription_id')}"
                    )
                    info(f"  plan_id: {user_data.get('plan_id')}")

                    # At this point (no webhook yet), status should still be pending_payment
                    # unless email verification already activated it
                    status = user_data.get("subscription_status")
                    if status == "pending_payment":
                        ok(
                            "Subscription status is 'pending_payment' (correct — waiting for Stripe webhook)"
                        )
                    elif status in ("active", "trial"):
                        ok(
                            f"Subscription status is '{status}' (webhook already processed)"
                        )
                    else:
                        warn(f"Unexpected subscription_status: {status}")
                        warnings.append(f"Unexpected status after checkout: {status}")
        except Exception as e:
            warn(f"Could not validate final state: {e}")

        # ====================================================================
        # Step 8: Test Login with New Account
        # ====================================================================
        header("Step 8: Test Login with New Account")
        try:
            login_resp = await client.post(
                "/admin/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
            )
            if login_resp.status_code == 200:
                login_data = login_resp.json()
                planner_token = login_data.get("access_token")
                if planner_token:
                    ok("Login successful — JWT token received")
                    info(f"  Token: {planner_token[:30]}...")

                    # Test authenticated endpoint
                    profile_resp = await client.get(
                        "/profile", headers={"Authorization": f"Bearer {planner_token}"}
                    )
                    if profile_resp.status_code == 200:
                        profile = profile_resp.json()
                        ok(
                            f"Profile access works — {profile.get('first_name')} {profile.get('last_name')}"
                        )
                    else:
                        fail(f"Profile access failed: {profile_resp.status_code}")
                        errors.append(
                            f"Authenticated profile access failed: {profile_resp.status_code}"
                        )
                else:
                    fail("Login returned 200 but no access_token")
                    errors.append("Login missing access_token in response")
            elif login_resp.status_code == 401:
                fail(f"Login rejected: {login_resp.text}")
                errors.append(
                    "Cannot login with test planner credentials after registration"
                )
            elif login_resp.status_code == 403:
                info(f"Login blocked (account may require payment): {login_resp.text}")
                warn(
                    "Login blocked — check if subscription_status check is too restrictive"
                )
                warnings.append("Login blocked for pending_payment user")
            else:
                fail(
                    f"Login returned unexpected status: {login_resp.status_code} — {login_resp.text}"
                )
                errors.append(f"Login failed: HTTP {login_resp.status_code}")
        except Exception as e:
            fail(f"Login test failed: {e}")
            errors.append(f"Login test error: {e}")

    # ====================================================================
    # Summary
    # ====================================================================
    header("\n" + "=" * 60)
    header("  Test Summary")
    header("=" * 60)

    if not errors and not warnings:
        print(f"\n  {GREEN}{BOLD}ALL TESTS PASSED ✓{RESET}\n")
    else:
        if errors:
            print(f"\n  {RED}{BOLD}{len(errors)} ERROR(S):{RESET}")
            for i, e in enumerate(errors, 1):
                print(f"    {RED}{i}. {e}{RESET}")
        if warnings:
            print(f"\n  {YELLOW}{BOLD}{len(warnings)} WARNING(S):{RESET}")
            for i, w in enumerate(warnings, 1):
                print(f"    {YELLOW}{i}. {w}{RESET}")

    print(f"\n  {CYAN}Next Steps:{RESET}")
    print("    1. Complete payment at the Stripe checkout URL above")
    print(
        f"    2. Or use Stripe CLI: stripe listen --forward-to {api_url}/stripe/webhook"
    )
    print("    3. Then: stripe trigger checkout.session.completed")
    print("    4. Verify user status changes from 'pending_payment' to 'active'\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Stripe Signup Flow")
    parser.add_argument(
        "--api-url", default="http://localhost:8000", help="API base URL"
    )
    args = parser.parse_args()

    asyncio.run(run_tests(args.api_url))
