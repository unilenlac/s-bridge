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
        url = f"{self.base_url}/api/dts/v1/navigation/"
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

    async def get_collection_name(self, resource: str) -> str:
        """
        Fetches the collection name for a given resource.
        """
        url = f"{self.base_url}/api/dts/v1/collection/"
        params = {"id": resource, "nav": "parents"}
        logger.info(f"Fetching collection parents for resource: {resource}")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Try to get the first parent collection title
            members = data.get("member", [])
            for m in members:
                title = m.get("title")
                if title:
                    return title.split(" - ")[0].strip()

            # Fallback to the resource's own title
            title = data.get("title", resource)
            return title.split(" - ")[0].strip()

    async def get_cite_type(self, resource: str, ref: str) -> str:
        """
        Fetches the citeType for a specific reference from the Navigation API.
        """
        url = f"{self.base_url}/api/dts/v1/navigation/"
        params = {
            "resource": resource,
            "ref": ref,
        }
        logger.info(f"Fetching citeType for resource: {resource}, ref: {ref}")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # citeType is usually in the 'ref' object for a specific ref,
            # but could also be at the top level in some implementations
            cite_type = data.get("citeType") or data.get("ref", {}).get("citeType")
            if not cite_type:
                # Fallback to 'milestone' if not found, consistent with existing logic
                logger.warning(f"citeType not found for ref '{ref}', defaulting to 'milestone'")
                return "milestone"

            return cite_type

    async def get_collection_name_url(self, client_url: str) -> str:
        """
        Fetches the collection name from the basic url.
        """
        # Simple extraction based on the user's rule: id is between 'id=' and the next '&'
        try:
            id_collection = client_url.split("id=")[1].split("&")[0]
        except (IndexError, AttributeError):
            logger.warning(f"Could not extract 'id' from URL: {client_url}")
            return "Unknown"

        url = f"{self.base_url}/api/dts/v1/collection/"
        params = {
            "id": id_collection
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("title", id_collection)