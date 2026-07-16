from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.api import subscription_management
from app.dependencies.auth_extended import ExtendedAuthUser, get_current_user_extended
from app.models.subscription import (
    CreateSubscriptionPlanRequest,
    UpdateSubscriptionPlanRequest,
)


@pytest.mark.parametrize(
    "request_model,payload",
    [
        (
            CreateSubscriptionPlanRequest,
            {
                "name": "Invalid domain-only plan",
                "price_monthly": 99,
                "features": {
                    "planner_storefront": False,
                    "custom_domain": True,
                },
            },
        ),
        (
            UpdateSubscriptionPlanRequest,
            {
                "features": {
                    "planner_storefront": False,
                    "custom_domain": True,
                }
            },
        ),
    ],
)
def test_custom_domain_plan_capability_requires_storefront(request_model, payload):
    with pytest.raises(ValidationError, match="requires planner storefront"):
        request_model.model_validate(payload)


def test_non_root_planner_cannot_mutate_storefront_plan_capabilities():
    app = FastAPI()
    app.include_router(subscription_management.router, prefix="/admin")
    app.dependency_overrides[get_current_user_extended] = lambda: ExtendedAuthUser(
        "planner@example.test",
        "wedding_planner",
        {"_id": "planner-1", "role": "wedding_planner"},
    )

    with TestClient(app) as client:
        response = client.put(
            "/admin/subscription-plans/plan_solo",
            json={
                "features": {
                    "planner_storefront": True,
                    "custom_domain": False,
                }
            },
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Root admin access required"}
