"""
Public Vendor Contract API

Endpoints for vendors to access and sign contracts without authentication.
Canonical access now uses path-scoped tokens, with query-token compatibility
left in place temporarily for already-issued links.
"""

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.services.vendor_service import vendor_service

router = APIRouter()


class VendorContractSignatureRequest(BaseModel):
    signer_name: str = Field(..., min_length=1, max_length=200)
    signer_email: str = Field(..., min_length=3, max_length=255)


@router.get("/public/contracts/{contract_id}/{token}", tags=["Public Contract Access"])
async def get_contract_for_vendor(contract_id: str, token: str):
    """Get contract for vendor review using the canonical path-token route."""
    return await vendor_service.get_contract_by_token(contract_id, token)


@router.get("/public/contracts/{contract_id}", tags=["Public Contract Access"], include_in_schema=False)
async def get_contract_for_vendor_legacy(
    contract_id: str,
    token: str = Query(..., description="Access token from email"),
):
    """Backward-compatible query-token access for already-issued links."""
    return await vendor_service.get_contract_by_token(contract_id, token)


@router.post("/public/contracts/{contract_id}/{token}/sign", tags=["Public Contract Access"])
async def sign_contract_as_vendor(
    contract_id: str,
    token: str,
    payload: VendorContractSignatureRequest,
    request: Request,
):
    """
    Sign a contract as a vendor (no authentication required).
    Records the signature with timestamp and IP address.
    """
    signature_ip = request.client.host if request.client else None

    return await vendor_service.sign_contract(
        contract_id=contract_id,
        token=token,
        signer_name=payload.signer_name,
        signer_email=payload.signer_email,
        signature_ip=signature_ip
    )


@router.post("/public/contracts/{contract_id}/sign", tags=["Public Contract Access"], include_in_schema=False)
async def sign_contract_as_vendor_legacy(
    request: Request,
    contract_id: str,
    token: str = Query(..., description="Access token"),
    signer_name: str = Query(..., description="Name of person signing"),
    signer_email: str = Query(..., description="Email of signer"),
):
    """Backward-compatible query-token signing path for already-issued links."""
    payload = VendorContractSignatureRequest(
        signer_name=signer_name,
        signer_email=signer_email,
    )
    return await sign_contract_as_vendor(contract_id, token, payload, request)
