"""
Public Vendor Contract API

Endpoints for vendors to access and sign contracts without authentication.
Accessed via secure tokens sent in vendor emails.
"""

from fastapi import APIRouter, Query, Request
from app.services.vendor_service import vendor_service

router = APIRouter()


@router.get("/public/contracts/{contract_id}", tags=["Public Contract Access"])
async def get_contract_for_vendor(
    contract_id: str,
    token: str = Query(..., description="Access token from email")
):
    """
    Get contract for vendor review (no authentication required).
    Vendor accesses this via the link in their email.
    """
    return await vendor_service.get_contract_by_token(contract_id, token)


@router.post("/public/contracts/{contract_id}/sign", tags=["Public Contract Access"])
async def sign_contract_as_vendor(
    contract_id: str,
    token: str = Query(..., description="Access token"),
    signer_name: str = Query(..., description="Name of person signing"),
    signer_email: str = Query(..., description="Email of signer"),
    request: Request = None
):
    """
    Sign a contract as a vendor (no authentication required).
    Records the signature with timestamp and IP address.
    """
    signature_ip = None
    if request:
        signature_ip = request.client.host

    return await vendor_service.sign_contract(
        contract_id=contract_id,
        token=token,
        signer_name=signer_name,
        signer_email=signer_email,
        signature_ip=signature_ip
    )
