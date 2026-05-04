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
        self._collection_cache = {}

    async def get_document(self, resource: str, ref: Optional[str] = None) -> str:
        """
        Fetches the XML document from the DTS API.
        :param resource: The DTS resource ID (e.g. 'A', 'B', etc)
        :param ref: Optional passage reference
        :return: The raw XML string
        """
        url = f"{self.base_url}/document/"
        params = {
            "resource": resource,
            "media_type": "text/xml"
        }
        if ref:
            params["ref"] = ref

        logger.info(f"Fetching DTS document for resource: {resource}, ref: {ref}")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text

    async def get_members(self, resource: str) -> list[dict]:
        """
        Fetches all level-1 CitableUnits for a resource from the Navigation API.
        Handles pagination automatically.
        :param resource: The DTS resource ID
        :return: List of dicts with 'identifier' and 'citeType' keys,
                 e.g. [{"identifier": "107", "citeType": "milestone"}, ...]
        """
        url = f"{self.base_url}/navigation/"
        members: list[dict] = []
        page = 1

        logger.info(f"Fetching navigation for resource: {resource}")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            while True:
                params = {
                    "resource": resource,
                    #down : 1 to get section like milestone. down 2 would give subsections
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

    async def get_collection_details(self, collection_id: str) -> tuple[str, list[str]]:
        """
        Fetches the collection name and its document resource IDs.
        Uses a simple dict cache to avoid N+1 queries.
        """
        if collection_id in self._collection_cache:
            return self._collection_cache[collection_id]

        url = f"{self.base_url}/collection/"
        params = {"id": collection_id}
        logger.info(f"Fetching collection details for collection: {collection_id}")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # The Title
            title = data.get("title", collection_id)
            title = title.split(" - ")[0].strip()

            # The Resources
            members = data.get("member", [])
            # Usually SubCollectionResource items are documents (represented by @id).
            resources = [m.get("@id") for m in members if m.get("@type", "Resource") == "Resource" and m.get("@id")]
            
            result = (title, resources)
            self._collection_cache[collection_id] = result
            return result
