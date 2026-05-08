from logging import Logger
import os
from httpx import AsyncClient

from core.config import Settings

from core.config import Settings

async def ServerId(url: str, logger: Logger, client: AsyncClient) -> str:
    # return server identity based on the URL and the user-agent value
    http_client_instance = client
    try:
        response = await http_client_instance.get(url, timeout=5.0)
        response.raise_for_status()
        return response.headers.get("User-Agent", "dts (1.0)")
    except Exception as e:
        # todo : handle correctly the Exceptions (everywhere in the codebase)
        logger.warning(f"Could not determine server identity for {url}: {e}")
        return "Unknown Server"

def get_section_filepath(collection_name: str, ref_id: str) -> str:
        """Standardizes the path for a prepared section file."""
        settings = Settings() # this should be passed as dependency not hardcoded here
        return os.path.join(settings.output_dir, collection_name, f"{ref_id}.json")
