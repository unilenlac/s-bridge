import logging
import httpx
from typing import Dict, Any, Union, Optional

from core.config import Settings
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

    def __init__(
        self,
        base_url: str,
        http_client: httpx.AsyncClient,
        timeout: Optional[float] = None,
    ):
        """
        Initializes the CollateX Client.
        :param base_url: The base URL of the CollateX API (e.g., "http://localhost:7369")
        :param http_client: Shared httpx.AsyncClient instance
        :param timeout: Custom timeout in seconds. Defaults to Settings().collatex_timeout (300s).
        """
        self.base_url = base_url.rstrip("/") if base_url else ""
        if timeout is None:
            timeout = Settings().collatex_timeout
        self.timeout = httpx.Timeout(timeout, connect=10.0)
        self.http_client = http_client

    async def collate(
        self,
        payload: Dict[str, Any],
        output_format: str = FORMAT_JSON,
        algorithm: Optional[str] = None,
        joined: Optional[bool] = None,
        transpositions: Optional[bool] = None,
        token_comparator: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Union[Dict[str, Any], str]:
        """
        Sends a JSON payload to the CollateX service for collation.

        :param payload: A dictionary conforming to the CollateX JSON input format.
                        See: https://collatex.net/doc/#json-input
        :param output_format: The desired output format (via the Accept header).
                              Defaults to 'application/json'.
        :param algorithm: Optional alignment algorithm (e.g. 'dekker', 'needleman-wunsch', 'medite').
        :param joined: Optional flag indicating whether consecutive matches should be joined into single segments.
        :param transpositions: Optional flag indicating whether transpositions should be detected.
        :param token_comparator: Optional token comparator configuration (e.g. {'type': 'equality'} or {'type': 'levenshtein', 'distance': 1}).
        :param timeout: Optional custom timeout in seconds for this request.
        :return: If output_format is JSON, returns the parsed Dict.
                 Otherwise, returns the raw string response (XML, DOT, SVG, etc).
        :raises httpx.HTTPError: If the HTTP request fails.
        """
        url = f"{self.base_url}/collate"
        headers = {"Content-Type": "application/json", "Accept": output_format}

        if algorithm is not None:
            payload["algorithm"] = algorithm
        if joined is not None:
            payload["joined"] = joined
        if transpositions is not None:
            payload["transpositions"] = transpositions
        if token_comparator is not None:
            payload["tokenComparator"] = token_comparator

        request_timeout = (
            httpx.Timeout(timeout, connect=10.0)
            if timeout is not None
            else self.timeout
        )

        logger.info(
            f"Sending collation request to {url} (format: {output_format}, algorithm: {algorithm}, joined: {joined}, transpositions: {transpositions}, token_comparator: {token_comparator}, timeout: {request_timeout.read}s)"
        )

        try:
            response = await self.http_client.post(
                url, json=payload, headers=headers, timeout=request_timeout
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
        except httpx.TimeoutException as e:
            msg = (
                f"CollateX request timed out after {request_timeout.read}s at {url}. "
                f"The server may still be processing a heavy workload: {e}"
            )
            logger.error(msg)
            raise CollatexError(msg) from e
        except httpx.RequestError as e:
            msg = f"CollateX server unreachable at {url}: {e}"
            logger.error(msg)
            raise CollatexError(msg) from e

    async def collate_with_fallback(
        self,
        payload: Dict[str, Any],
        output_format: str = FORMAT_JSON,
        algorithm: Optional[str] = None,
        joined: Optional[bool] = None,
        transpositions: Optional[bool] = None,
        token_comparator: Optional[Dict[str, Any]] = None,
        dekker_timeout: Optional[float] = None,
        ref_id: Optional[str] = None,
    ) -> tuple[Union[Dict[str, Any], str], str, bool]:
        """
        Collates payload with automatic fallback:
        If 'dekker' (default) is requested and takes longer than `dekker_timeout` (default 5.0s),
        it automatically catches the timeout and collates with 'needleman-wunsch'.

        :return: (result, actual_algorithm_used, fell_back_boolean)
        """
        requested_algo = algorithm or "dekker"

        if requested_algo in ["dekker", "auto"]:
            budget = (
                dekker_timeout
                if dekker_timeout is not None
                else Settings().collatex_dekker_timeout
            )
            try:
                result = await self.collate(
                    payload=payload,
                    output_format=output_format,
                    algorithm="dekker",
                    joined=joined,
                    transpositions=transpositions,
                    token_comparator=token_comparator,
                    timeout=budget,
                )
                return result, "dekker", False
            except CollatexError, httpx.TimeoutException:
                ref_info = f" on ref '{ref_id}'" if ref_id else ""
                logger.warning(
                    f"CollateX Dekker algorithm timed out after {budget}s{ref_info}. "
                    f"Falling back immediately to 'needleman-wunsch'..."
                )
                # Retry with needleman-wunsch using full default client timeout
                result = await self.collate(
                    payload=payload,
                    output_format=output_format,
                    algorithm="needleman-wunsch",
                    joined=joined,
                    transpositions=transpositions,
                    token_comparator=token_comparator,
                )
                return result, "needleman-wunsch", True

        # Non-dekker algorithms run directly
        result = await self.collate(
            payload=payload,
            output_format=output_format,
            algorithm=requested_algo,
            joined=joined,
            transpositions=transpositions,
            token_comparator=token_comparator,
        )
        return result, requested_algo, False
