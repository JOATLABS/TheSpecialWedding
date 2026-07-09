import os
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
# Zone ID for thespecialwedding.com
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID", "04b53289140198a33dd22da4108b7db8")
CLOUDFLARE_API_BASE = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}"

class CloudflareServiceError(Exception):
    pass

class CloudflareService:
    @staticmethod
    def get_headers() -> Dict[str, str]:
        if not CLOUDFLARE_API_TOKEN:
            raise CloudflareServiceError("CLOUDFLARE_API_TOKEN is not set.")
        return {
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json"
        }

    @staticmethod
    async def add_custom_hostname(hostname: str) -> Dict[str, Any]:
        """
        Creates a Custom Hostname (Cloudflare for SaaS) for the given domain.
        Returns the custom_hostname details, including ownership verification records.
        """
        if not CLOUDFLARE_API_TOKEN:
            logger.warning("Cloudflare API token not configured. Returning mock custom hostname data.")
            return {
                "id": "mock_id_" + hostname,
                "hostname": hostname,
                "status": "pending",
                "ownership_verification": {
                    "type": "txt",
                    "name": f"_cf-custom-hostname.{hostname}",
                    "value": "mock_verification_token"
                }
            }

        url = f"{CLOUDFLARE_API_BASE}/custom_hostnames"
        payload = {
            "hostname": hostname,
            "ssl": {
                "method": "http",
                "type": "dv",
                "settings": {
                    "min_tls_version": "1.2"
                }
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=CloudflareService.get_headers(), json=payload, timeout=10.0)
                data = response.json()
                if not response.is_success or not data.get("success"):
                    errors = data.get("errors", [{"message": "Unknown error"}])
                    raise CloudflareServiceError(f"Cloudflare API Error: {errors[0]['message']}")
                
                return data.get("result", {})
            except httpx.RequestError as e:
                raise CloudflareServiceError(f"HTTP Request failed: {str(e)}")

    @staticmethod
    async def get_custom_hostname_status(hostname_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the current status of a custom hostname.
        """
        if not CLOUDFLARE_API_TOKEN or hostname_id.startswith("mock_id_"):
            return {
                "id": hostname_id,
                "status": "pending"
            }

        url = f"{CLOUDFLARE_API_BASE}/custom_hostnames/{hostname_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=CloudflareService.get_headers(), timeout=10.0)
                data = response.json()
                if not response.is_success or not data.get("success"):
                    return None
                
                return data.get("result", {})
            except httpx.RequestError as e:
                raise CloudflareServiceError(f"HTTP Request failed: {str(e)}")

    @staticmethod
    async def delete_custom_hostname(hostname_id: str) -> bool:
        """
        Deletes a Custom Hostname configuration from Cloudflare.
        """
        if not CLOUDFLARE_API_TOKEN or hostname_id.startswith("mock_id_"):
            return True

        url = f"{CLOUDFLARE_API_BASE}/custom_hostnames/{hostname_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, headers=CloudflareService.get_headers(), timeout=10.0)
                return response.is_success
            except httpx.RequestError as e:
                raise CloudflareServiceError(f"HTTP Request failed: {str(e)}")
