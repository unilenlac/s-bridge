from logging import Logger
import os
from typing import AsyncGenerator
from httpx import AsyncClient, RequestError, HTTPStatusError

from core.exceptions import DtsError

from core.config import Settings


async def ServerId(url: str, logger: Logger, client: AsyncClient) -> str:
    # return server identity based on the URL and the user-agent value
    try:
        response = await client.get(url, timeout=5.0)
        return response.headers.get("User-Agent", "dts (1.0)")
    except RequestError as e:
        msg = f"Request error determining server identity for {url}: {e}"
        logger.warning(msg)
        raise DtsError(msg) from e


def get_section_filepath(
    settings: Settings, collection_name: str, ref_id: str, ext: str = "json"
) -> str:
    """Standardizes the path for a prepared section file."""
    return os.path.join(settings.nlp_analysis_dir, collection_name, f"{ref_id}.{ext}")


async def get_xml_from_dts_url(
    url: str, http_client: AsyncClient, logger: Logger
) -> AsyncGenerator[str, None]:
    """Fetches XML content from a given URL using the provided HTTP client."""

    try:
        response = await http_client.get(url=url, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except HTTPStatusError as e:
        msg = f"DTS server returned HTTP {e.response.status_code} for {url}"
        logger.error(msg)
        raise DtsError(msg) from e
    except RequestError as e:
        msg = f"DTS server unreachable at {url}: {e}"
        logger.error(msg)
        raise DtsError(msg) from e
