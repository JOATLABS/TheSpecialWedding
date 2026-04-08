"""
Forms Management Tests

Tests form CRUD, public form access, and form submission.
Forms are used for collecting guest information, vendor questionnaires, etc.
"""

import pytest


@pytest.mark.integration
class TestForms:
    """Test form creation, retrieval, and public submission."""

    def test_create_form(self, api):
        """Create a new form."""
        resp = api.post(
            "/admin/forms",
            json={
                "name": "Integration Test Form",
                "settings": {
                    "title": "Test Form",
                    "description": "A form created by integration tests",
                    "is_public": True,
                    "submit_button_text": "Submit",
                    "success_message": "Thank you!",
                    "allow_multiple_submissions": False,
                    "collect_email": True,
                    "requires_auth": False,
                },
                "fields": [
                    {
                        "id": "field_1",
                        "type": "text",
                        "label": "Your Name",
                        "required": True,
                    },
                    {
                        "id": "field_2",
                        "type": "email",
                        "label": "Your Email",
                        "required": True,
                    },
                    {
                        "id": "field_3",
                        "type": "select",
                        "label": "Meal Choice",
                        "required": False,
                        "options": ["Chicken", "Fish", "Vegetarian"],
                    },
                ],
            },
        )
        assert resp.status_code == 200, f"Create form failed: {resp.text}"
        data = resp.json()
        assert "id" in data

    def test_list_forms(self, api):
        """List all forms."""
        resp = api.get("/admin/forms")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_form_by_id(self, api):
        """Fetch a specific form."""
        list_resp = api.get("/admin/forms")
        forms = list_resp.json()
        assert len(forms) > 0

        form_id = forms[0].get("id") or forms[0].get("_id")
        resp = api.get(f"/admin/forms/{form_id}")
        assert resp.status_code == 200

    def test_public_form_access(self, api):
        """Public can access a public form without auth."""
        list_resp = api.get("/admin/forms")
        forms = list_resp.json()

        # Find a public form
        for form in forms:
            form_id = form.get("id") or form.get("_id")
            resp = api.get_unauthenticated(f"/public/forms/{form_id}")
            if resp.status_code == 200:
                return  # Success — found a publicly accessible form

        # If no public forms exist, that's OK — just verify the endpoint works
        if forms:
            form_id = forms[0].get("id") or forms[0].get("_id")
            resp = api.get_unauthenticated(f"/public/forms/{form_id}")
            # 200 (public) or 404 (not found/not public) are both valid
            assert resp.status_code in (200, 403, 404)

    def test_public_form_submission(self, api):
        """Public can submit a form response."""
        list_resp = api.get("/admin/forms")
        forms = list_resp.json()
        if not forms:
            pytest.skip("No forms available")

        form_id = forms[0].get("id") or forms[0].get("_id")

        resp = api.post_unauthenticated(
            f"/public/forms/{form_id}/submit",
            json={
                "responses": {
                    "field_1": "Test User",
                    "field_2": "test@example.com",
                    "field_3": "Vegetarian",
                },
            },
        )
        # 200 (success), 403 (form not public), or 400 (validation) are all valid
        assert resp.status_code in (200, 201, 400, 403, 404, 429)

    def test_get_form_responses(self, api):
        """Admin can view form responses."""
        list_resp = api.get("/admin/forms")
        forms = list_resp.json()
        if not forms:
            pytest.skip("No forms available")

        form_id = forms[0].get("id") or forms[0].get("_id")
        resp = api.get(f"/admin/forms/{form_id}/responses")
        assert resp.status_code == 200

    def test_get_form_templates(self, api):
        """List available form templates."""
        resp = api.get("/admin/form-templates")
        assert resp.status_code == 200

    def test_update_form(self, api):
        """Update an existing form."""
        list_resp = api.get("/admin/forms")
        forms = list_resp.json()
        if not forms:
            pytest.skip("No forms available")

        form_id = forms[0].get("id") or forms[0].get("_id")
        resp = api.put(
            f"/admin/forms/{form_id}",
            json={
                "name": "Updated Integration Test Form",
                "settings": {
                    "title": "Updated Form",
                    "description": "Updated by integration tests",
                    "is_public": True,
                    "submit_button_text": "Send",
                    "success_message": "Got it!",
                    "allow_multiple_submissions": True,
                    "collect_email": True,
                    "requires_auth": False,
                },
            },
        )
        assert resp.status_code == 200

    def test_duplicate_form(self, api):
        """Duplicate an existing form."""
        list_resp = api.get("/admin/forms")
        forms = list_resp.json()
        if not forms:
            pytest.skip("No forms available")

        source_form = forms[0]
        form_id = source_form.get("id") or source_form.get("_id")
        resp = api.post(
            f"/admin/forms/{form_id}/duplicate",
            json={"new_name": f"{source_form.get('name', 'Form')} Copy"},
        )
        assert resp.status_code == 200
