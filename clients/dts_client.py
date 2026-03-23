import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

class DTSClient:
    def __init__(self, base_url: str):
        """
        Initializes the DTS Client.
        :param base_url: The base URL of the DTS API (e.g., "http://ftsr-dev.unil.ch:8000")
        """
        self.base_url = base_url.rstrip("/")

    async def get_document(self, resource: str, ref: Optional[str] = None) -> str:
        """
        Fetches the XML document from the DTS API.
        :param resource: The DTS resource ID (e.g. 'A', 'B', etc)
        :param ref: Optional passage reference
        :return: The raw XML string
        """
        url = f"{self.base_url}/api/dts/v1/document/"
        params = {
            "resource": resource,
            "media_type": "text/xml"
        }
        if ref:
            params["ref"] = ref
            
        logger.info(f"Fetching DTS document for resource: {resource}, ref: {ref}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text
