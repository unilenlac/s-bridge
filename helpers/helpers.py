from logging import Logger
import os
import re
from typing import AsyncGenerator, Optional
from httpx import AsyncClient, RequestError, HTTPStatusError, Response

from core.exceptions import DtsError

from core.config import Settings


def extract_dts_error_detail(response: Optional[Response]) -> str:
    """
    Extracts detail information from a DTS API error JSON payload.
    Returns a string formatted as ' — type: message: details' if present, or an empty string.
    """
    if response is None:
        return ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            err = payload.get("error", {})
            if isinstance(err, dict):
                parts = [
                    str(p)
                    for p in (err.get("type"), err.get("message"), err.get("details"))
                    if p
                ]
                if parts:
                    return " — " + ": ".join(parts)
    except Exception:
        pass
    return ""


async def ServerId(url: str, logger: Logger, client: AsyncClient) -> str:
    # return server identity based on the URL and the user-agent value
    try:
        response = await client.get(url, timeout=15.0)
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
        detail = extract_dts_error_detail(e.response)
        msg = f"DTS server returned HTTP {e.response.status_code} for {url}{detail}"
        logger.error(msg)
        raise DtsError(msg) from e
    except RequestError as e:
        msg = f"DTS server unreachable at {url}: {e}"
        logger.error(msg)
        raise DtsError(msg) from e


def extract_body_content(data: str) -> str:
    """
    Extracts the inner content of the <body> element from an XML/TEI string.
    This helps isolate the content to be parsed and bypasses any malformed or
    incomplete outer/ancestor elements in DTS XML fragments.
    """
    body_start_match = re.search(r'<([a-zA-Z0-9_-]+:)?body\b[^>]*>', data, re.IGNORECASE)
    if not body_start_match:
        return data

    start_idx = body_start_match.end()

    body_end_match = re.search(r'</([a-zA-Z0-9_-]+:)?body\s*>', data, re.IGNORECASE)
    if body_end_match:
        end_idx = body_end_match.start()
        return data[start_idx:end_idx]

    return data[start_idx:]


def strip_accents(text: str) -> str:
    """
    Normalizes a token/word string to its unaccented, lowercased base form
    matching historical xml2stemmarest normal_form behavior.

    1. Removes punctuation characters (both ASCII and Greek specific like ·, ·, ;).
    2. Decomposes Unicode characters to NFD (Canonical Decomposition).
    3. Strips all combining diacritical marks (Unicode category 'Mn': acute, grave,
       perispomeni/circumflex, rough/smooth breathing, diaeresis, iota subscript, etc.).
    4. Converts to lowercase and strips whitespace.
    """
    import unicodedata
    import string

    if not text:
        return ""

    # Remove standard and Greek-specific punctuation
    extra_punct = "··;’'\"«»—–,.;:!?()[]{}"
    punct_set = set(string.punctuation).union(set(extra_punct))
    cleaned = "".join(c for c in text if c not in punct_set)

    # Decompose to NFD
    nfd_text = unicodedata.normalize("NFD", cleaned)

    # Filter out combining marks
    unaccented = "".join(c for c in nfd_text if unicodedata.category(c) != "Mn")

    return unaccented.lower().strip()


