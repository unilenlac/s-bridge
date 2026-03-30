import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

#Implements a DocumentFetcher Protocol
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

    async def get_navigation(self, resource: str) -> list[dict]:
        """
        Fetches all level-1 CitableUnits for a resource from the Navigation API.
        Handles pagination automatically.
        :param resource: The DTS resource ID
        :return: List of dicts with 'identifier' and 'citeType' keys,
                 e.g. [{"identifier": "107", "citeType": "milestone"}, ...]
        """
        url = f"{self.base_url}/api/dts/v1/navigation/"
        members: list[dict] = []
        page = 1

        logger.info(f"Fetching navigation for resource: {resource}")

        async with httpx.AsyncClient() as client:
            while True:
                params = {
                    "resource": resource,
                    "down": 1,
                    "limit": 100,
                    "page": page,
                }
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                for item in data.get("member", []):
                    members.append({
                        "identifier": item["identifier"],
                        "citeType": item.get("citeType", "section"),
                    })

                # Pagination: stop when next == last (no more pages)
                view = data.get("view", {})
                next_url = view.get("next", "")
                last_url = view.get("last", "")
                if not next_url or next_url == last_url:
                    break
                page += 1

        logger.info(f"Found {len(members)} level-1 refs for resource: {resource}")
        return members
