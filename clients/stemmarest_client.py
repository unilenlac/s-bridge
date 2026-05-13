import logging
from httpx import AsyncClient, HTTPStatusError, RequestError

from core.exceptions import StemmarestError

logger = logging.getLogger("s-bridge")

class StemmarestClient:
    def __init__(self, base_url: str, http_client: AsyncClient):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client

    async def get_or_create_tradition(self, name: str, language: str = "grc", direction: str = "LR", is_public: bool = False) -> str:
        """
        Looks up a tradition by name. If it exists, returns its ID.
        Otherwise, creates a new one with the given default metadata.
        """
        
        resp = await self.http_client.get(f"{self.base_url}/traditions")
        if not resp.is_success:
            raise StemmarestError(f"Stemmarest: failed to list traditions — HTTP {resp.status_code}: {resp.text[:200]}")
        traditions = resp.json()
        
        for trad in traditions:
            if trad.get("name") == name:
                logger.info(f"Stemmarest tradition '{name}' already exists with ID: {trad.get('id')}")
                return trad["id"]
                
        logger.info(f"Creating new Stemmarest tradition '{name}'")
        payload = {
            "name": name,
            "language": language,
            "direction": direction,
            "public": str(is_public).lower(),
            "userId": "user",  # Required by stemmarest
            "filetype": "graphml"
        }
        empty_graphml = b'''<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"><graph id="G" edgedefault="directed"></graph></graphml>'''
        
        files = {k: (None, str(v)) for k, v in payload.items()}
        files["file"] = ("empty.xml", empty_graphml, "application/xml")

        resp = await self.http_client.post(f"{self.base_url}/tradition", data={"name":name}, files=files, auth=("user", "userpass"))
        
        if not resp.is_success:
            msg = f"Stemmarest: failed to create tradition '{name}' — HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error(msg)
            raise StemmarestError(msg)
            
        trad_dict = resp.json()
        # If it returns the ID directly as string, or `{ "id": "..." }` or `{ "tradId": "..." }`
        if isinstance(trad_dict, str):
            trad_id = trad_dict
        else:
            trad_id = trad_dict.get("id") or trad_dict.get("tradId")
        
        logger.info(f"Successfully created Stemmarest tradition '{name}' with ID: {trad_id}")
        return trad_id

    async def upload_section(self, trad_id: str, section_name: str, file_path: str, filetype: str = "collatex", logger: logging.Logger = None) -> dict:
        """
        Uploads a collatex JSON file as a new section to an existing tradition.
        """
        logger.info(f"Uploading section '{section_name}' to tradition '{trad_id}' from {file_path}")
        
        with open(file_path, "rb") as f:
            files = {
                "file": (file_path.split("/")[-1], f, "application/json")
            }
            data = {
                "name": section_name,
                "filetype": filetype
            }
            
            resp = await self.http_client.post(
                f"{self.base_url}/tradition/{trad_id}/section",
                data=data,
                files=files,
                auth=("user", "userpass")
            )
            
            if not resp.is_success:
                msg = f"Stemmarest: failed to upload section '{section_name}' to tradition '{trad_id}' — HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error(msg)
                raise StemmarestError(msg)
                
            result = resp.json()
            logger.info(f"Successfully uploaded section '{section_name}', Neo4j node ID: {result}")
            return result
