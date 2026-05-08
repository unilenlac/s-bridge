from logging import Logger
import os
from typing import AsyncGenerator
from httpx import AsyncClient, RequestError, HTTPStatusError

from core.config import Settings

async def ServerId(url: str, logger: Logger, client: AsyncClient) -> str:
    # return server identity based on the URL and the user-agent value
    http_client_instance = client
    try:
        response = await http_client_instance.get(url, timeout=5.0)
        response.raise_for_status()
        return response.headers.get("User-Agent", "dts (1.0)")
    except HTTPStatusError as e:
        logger.warning(f"HTTP error determining server identity for {url}: {e.response.status_code}")
        return "Unknown Server"
    except RequestError as e:
        logger.warning(f"Request error determining server identity for {url}: {e}")
        return "Unknown Server"

def get_section_filepath(collection_name: str, ref_id: str, ext: str = "json") -> str:
        """Standardizes the path for a prepared section file."""
        settings = Settings() # this should be passed as dependency not hardcoded here
        return os.path.join(settings.output_dir, collection_name, f"{ref_id}.{ext}")

async def get_xml_from_dts_url(url: str, http_client: AsyncClient, logger: Logger) -> AsyncGenerator[str, None]:
    """Fetches XML content from a given URL using the provided HTTP client."""

    try:
        response = await http_client.get(url=url, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except HTTPStatusError as e:
        logger.error(f"HTTP error fetching XML from {url}: {e.response.status_code}")
        raise
    except RequestError as e:
        logger.error(f"Request error fetching XML from {url}: {e}")
        raise
