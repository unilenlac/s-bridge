import logging
import httpx
from typing import Optional, Dict, Any, Union

from core.exceptions import CollatexError

logger = logging.getLogger(__name__)


class CollatexClient:
    """
    Client for interacting with the CollateX RESTful Web Service.
    See: https://collatex.net/doc/#cli (section 7)
    """

    # Supported output formats by CollateX
    FORMAT_JSON = "application/json"
    FORMAT_TEI_XML = "application/tei+xml"
    FORMAT_GRAPHML = "application/graphml+xml"
    FORMAT_DOT = "text/plain"
    FORMAT_SVG = "image/svg+xml"

    def __init__(self, base_url: str, http_client: httpx.AsyncClient):
        """
        Initializes the CollateX Client.
        :param base_url: The base URL of the CollateX API (e.g., "http://localhost:7369")
        """
        self.base_url = base_url.rstrip("/")
        # Using a longer timeout as collation of large texts can be slow
        self.timeout = httpx.Timeout(60.0, connect=10.0)
        self.http_client = http_client

    async def collate(
        self, payload: Dict[str, Any], output_format: str = FORMAT_JSON
    ) -> Union[Dict[str, Any], str]:
        """
        Sends a JSON payload to the CollateX service for collation.

        :param payload: A dictionary conforming to the CollateX JSON input format.
                        See: https://collatex.net/doc/#json-input
        :param output_format: The desired output format (via the Accept header).
                              Defaults to 'application/json'.
        :return: If output_format is JSON, returns the parsed Dict.
                 Otherwise, returns the raw string response (XML, DOT, SVG, etc).
        :raises httpx.HTTPError: If the HTTP request fails.
        """
        url = f"{self.base_url}/collate"
        headers = {"Content-Type": "application/json", "Accept": output_format}

        logger.info(f"Sending collation request to {url} (format: {output_format})")

        try:
            response = await self.http_client.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()

            # Parse JSON if requested, otherwise return raw text
            if output_format == self.FORMAT_JSON:
                return response.json()
            else:
                return response.text

        except httpx.HTTPStatusError as e:
            msg = f"CollateX returned HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error(msg)
            raise CollatexError(msg) from e
        except httpx.RequestError as e:
            msg = f"CollateX server unreachable at {url}: {e}"
            logger.error(msg)
            raise CollatexError(msg) from e
