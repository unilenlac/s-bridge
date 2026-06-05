import logging
from httpx import AsyncClient, HTTPStatusError, RequestError
from json import JSONDecodeError

from core.exceptions import StemmarestError

logger = logging.getLogger("s-bridge")


class StemmarestClient:
    def __init__(self, base_url: str, http_client: AsyncClient):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> dict | str:
        """Helper to handle HTTP requests, error parsing, and JSON decoding."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = await self.http_client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except HTTPStatusError as e:
            msg = f"Stemmarest HTTP error {e.response.status_code} at {endpoint}"
            logger.error(msg)
            raise StemmarestError(msg) from e
        except RequestError as e:
            msg = f"Stemmarest server unreachable at {endpoint}: {e}"
            logger.error(msg)
            raise StemmarestError(msg) from e
        except JSONDecodeError as e:
            msg = f"Stemmarest returned invalid JSON at {endpoint}: {e}"
            logger.error(msg)
            raise StemmarestError(msg) from e

    async def get_or_create_tradition(
        self,
        name: str,
        language: str = "grc",
        direction: str = "LR",
        is_public: bool = False,
    ) -> str:
        traditions = await self._make_request("GET", "/traditions")

        for trad in traditions:
            if trad.get("name") == name:
                logger.info(
                    f"Stemmarest tradition '{name}' already exists with ID: {trad.get('id')}"
                )
                return trad["id"]

        logger.info(f"Creating new Stemmarest tradition '{name}'")
        payload = {
            "name": name,
            "language": language,
            "direction": direction,
            "public": str(is_public).lower(),
            "userId": "user",
            "filetype": "graphml",
        }
        empty_graphml = b"""<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="[http://graphml.graphdrawing.org/xmlns](http://graphml.graphdrawing.org/xmlns)" xmlns:xsi="http://www.w3.```org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"><graph id="G" edgedefault="directed"></graph></graphml>"""

        files = {k: (None, str(v)) for k, v in payload.items()}
        files["file"] = ("empty.xml", empty_graphml, "application/xml")

        trad_dict = await self._make_request(
            "POST",
            "/tradition",
            data={"name": name},
            files=files,
            auth=("user", "userpass"),
        )

        if isinstance(trad_dict, str):
            trad_id = trad_dict
        else:
            trad_id = trad_dict.get("id") or trad_dict.get("tradId")

        logger.info(
            f"Successfully created Stemmarest tradition '{name}' with ID: {trad_id}"
        )
        return trad_id

    async def upload_section(
        self,
        trad_id: str,
        section_name: str,
        file_path: str,
        filetype: str = "collatex",
    ) -> dict:
        logger.info(
            f"Uploading section '{section_name}' to tradition '{trad_id}' from {file_path}"
        )

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.split("/")[-1], f, "application/json")}
                data = {"name": section_name, "filetype": filetype}

                result = await self._make_request(
                    "POST",
                    f"/tradition/{trad_id}/section",
                    data=data,
                    files=files,
                    auth=("user", "userpass"),
                )

                logger.info(
                    f"Successfully uploaded section '{section_name}', Neo4j node ID: {result}"
                )
                return result

        except OSError as e:
            msg = f"Failed to read file {file_path} for upload: {e}"
            logger.error(msg)
            raise StemmarestError(msg) from e
