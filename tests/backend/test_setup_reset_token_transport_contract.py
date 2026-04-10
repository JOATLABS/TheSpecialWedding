from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_setup_reset_and_team_invite_emails_use_path_tokens() -> None:
    couple_invite_source = _read("app/api/couple_invite.py")
    couple_auth_source = _read("app/api/couple_auth.py")
    user_management_source = _read("app/services/user_management_service.py")
    team_management_source = _read("app/services/team_management_service.py")

    assert (
        'f"{normalized_frontend_url}/couple/setup/{invite_token}"'
        in couple_invite_source
    )
    assert (
        'f"{normalized_frontend_url}/couple/reset-password/{reset_token}"'
        in couple_auth_source
    )
    assert (
        "setup_url = f\"{frontend_url.rstrip('/')}/setup-account/{token}\""
        in user_management_source
    )
    assert (
        "reset_url = f\"{frontend_url.rstrip('/')}/reset-password/{reset_token}\""
        in user_management_source
    )
    assert (
        "accept_url = f\"{base_url.rstrip('/')}/admin/team/accept/{token}\""
        in team_management_source
    )


def test_legacy_pages_redirect_query_tokens_to_canonical_routes() -> None:
    couple_setup_page = _read("app/couple/setup/page.tsx")
    couple_reset_page = _read("app/couple/reset-password/page.tsx")
    setup_account_page = _read("app/setup-account/page.tsx")
    reset_password_page = _read("app/reset-password/page.tsx")
    team_accept_page = _read("app/admin/team/accept/page.tsx")

    assert (
        "redirect(`/couple/setup/${encodeURIComponent(queryToken)}`)"
        in couple_setup_page
    )
    assert (
        "redirect(`/couple/reset-password/${encodeURIComponent(queryToken)}`)"
        in couple_reset_page
    )
    assert (
        "redirect(`/setup-account/${encodeURIComponent(queryToken)}`)"
        in setup_account_page
    )
    assert (
        "redirect(`/reset-password/${encodeURIComponent(queryToken)}`)"
        in reset_password_page
    )
    assert (
        "redirect(`/admin/team/accept/${encodeURIComponent(queryToken)}`)"
        in team_accept_page
    )


def test_canonical_path_pages_pass_route_tokens_into_client_components() -> None:
    canonical_pages = {
        "app/couple/setup/[token]/page.tsx": "CoupleSetupPageClient",
        "app/couple/reset-password/[token]/page.tsx": "CoupleResetPasswordPageClient",
        "app/setup-account/[token]/page.tsx": "SetupAccountPageClient",
        "app/reset-password/[token]/page.tsx": "ResetPasswordPageClient",
        "app/admin/team/accept/[token]/page.tsx": "AcceptInvitePageClient",
    }

    for relative_path, component_name in canonical_pages.items():
        source = _read(relative_path)
        assert f"import {component_name}" in source
        assert "initialToken={token}" in source


def test_client_components_use_initial_token_props_and_existing_safe_backend_contracts() -> (
    None
):
    couple_setup_client = _read("app/couple/setup/CoupleSetupPageClient.tsx")
    couple_reset_client = _read(
        "app/couple/reset-password/CoupleResetPasswordPageClient.tsx"
    )
    setup_account_client = _read("app/setup-account/SetupAccountPageClient.tsx")
    reset_password_client = _read("app/reset-password/ResetPasswordPageClient.tsx")
    team_accept_client = _read("app/admin/team/accept/AcceptInvitePageClient.tsx")

    for source in (
        couple_setup_client,
        couple_reset_client,
        setup_account_client,
        reset_password_client,
        team_accept_client,
    ):
        assert "useSearchParams" not in source
        assert "initialToken: string | null" in source

    assert "body: JSON.stringify({ token, password })" in couple_setup_client
    assert "body: JSON.stringify({ token, password })" in couple_reset_client
    assert "/setup/validate-token/${invitationToken}" in setup_account_client
    assert "token,\n          password: formData.password" in setup_account_client
    assert "/reset-password/validate/${resetToken}" in reset_password_client
    assert "token,\n          password," in reset_password_client
    assert "/admin/team/invite-info/${token}" in team_accept_client
    assert "token,\n          first_name: firstName.trim()" in team_accept_client
