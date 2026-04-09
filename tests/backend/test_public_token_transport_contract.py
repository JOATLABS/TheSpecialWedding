from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_vendor_form_public_routes_use_path_tokens() -> None:
    source = _read("app/api/vendor_forms.py")

    assert '/vendor-form/{form_id}/public/{token}' in source
    assert '/vendor-form/{form_id}/submit/{token}' in source
    assert 'f"{normalized_base}/vendor-form/{form_id}/{access_token}"' in source


def test_vendor_contract_public_routes_use_path_tokens_and_body_payloads() -> None:
    api_source = _read("app/api/vendor_contract_public.py")
    service_source = _read("app/services/vendor_service.py")

    assert '/public/contracts/{contract_id}/{token}' in api_source
    assert '/public/contracts/{contract_id}/{token}/sign' in api_source
    assert 'payload: VendorContractSignatureRequest' in api_source
    assert 'f"{normalized_base}/vendor-contract/{contract_id}/{access_token}"' in service_source


def test_public_pages_redirect_query_tokens_to_canonical_routes() -> None:
    vendor_form_page = _read("app/vendor-form/[form_id]/page.tsx")
    vendor_contract_page = _read("app/vendor-contract/[id]/page.tsx")

    assert 'redirect(`/vendor-form/${form_id}/${encodeURIComponent(queryToken)}`)' in vendor_form_page
    assert 'redirect(`/vendor-contract/${id}/${encodeURIComponent(queryToken)}`)' in vendor_contract_page


def test_public_clients_call_path_token_endpoints_and_sign_with_json_body() -> None:
    vendor_form_client = _read("app/vendor-form/[form_id]/VendorFormPageClient.tsx")
    vendor_contract_client = _read("app/vendor-contract/[id]/PublicContractPageClient.tsx")

    assert '/public/${encodeURIComponent(accessToken)}' in vendor_form_client
    assert '/submit/${encodeURIComponent(token!)}' in vendor_form_client
    assert 'submission_data: formData' in vendor_form_client

    assert '/public/contracts/${contractId}/${encodeURIComponent(token)}' in vendor_contract_client
    assert '/public/contracts/${contractId}/${encodeURIComponent(token)}/sign' in vendor_contract_client
    assert "signer_name: signerName" in vendor_contract_client
    assert "signer_email: signerEmail" in vendor_contract_client
