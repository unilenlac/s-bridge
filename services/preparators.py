import os
import json
import logging

from httpx import AsyncClient
from uritemplate import URITemplate
from urllib.parse import urlparse, parse_qs
from copy import deepcopy
from typing import Optional

from helpers.helpers import get_section_filepath
from core.config import Settings

logger = logging.getLogger("s-bridge")

class DtsPreparator:
    
    @staticmethod
    async def run(url: str, target_ref: Optional[str], job_id: str, http_client: AsyncClient, settings: Settings) -> tuple[bool, list[str], str, list[str]]:
        """
        Prepares the sections for collation by fetching the necessary data from a DTS API.
        """
        document_urls = []
        refs_list = []
        collation_model = {
            "witnesses": []
        }
        paths = []
        
        res = await http_client.get(url, follow_redirects=True)
        if res.status_code != 200:
            raise Exception(f"Failed to fetch data from {url}: {res.status_code} {res.text}")
        col = res.json()
        collection_title = col.get("@id") if col.get("title") == "" else col.get("title")
        navigation_urls = [URITemplate(item.get('navigation')) for item in col.get("member", []) if item.get("@type").lower() == "resource"]
        resources = [item.get('@id') for item in col.get("member", []) if item.get("@type").lower() == "resource"]

        for nav in navigation_urls:
        
            page = 1

            while True:
                params = {
                    "down": 1,
                    "page": page,
                }
                res = await http_client.get(nav.expand(**params), follow_redirects=True)
                res.raise_for_status()
                data = res.json()
                document_url = URITemplate(data.get("resource").get('document'))
                
                for ref in data.get("member", []):
                    refs_list.append(ref.get("identifier"))
                    document_urls.append(document_url.expand(ref=ref.get("identifier")))
                
                view = data.get("view", {})
                next_url = view.get("next", "")
                last_url = view.get("last", "")
                if not next_url or next_url == last_url:
                    break
                page += 1
        
        refs_list = list(dict.fromkeys(refs_list))
        
        #gives the possibility for a specific section/ref in relation to origin ref parameter
        if target_ref:
            if target_ref in refs_list:
                refs_list = [target_ref]
            else:
                logger.warning(f"Target ref '{target_ref}' not found in collection '{url}'")
                return False, [], collection_title, resources

        for ref in refs_list:
            document_url = list(filter(lambda url: f"ref={ref}" in url, document_urls))
            collation = deepcopy(collation_model)
            if len(document_url):
                while len(document_url):
                    doc = document_url.pop()
                    params = parse_qs(urlparse(doc).query)
                    #res = await http_client.get(doc, follow_redirects=True)
                    #res.raise_for_status()
                    """ todo : this is a bit clumsy. 
                    we could create an iterator that yields the url request, status validation, content extraction, logging etc and add it into the 'content' field.
                    The iterator would be consumed at the analyser level. """
                    witness = {
                        "id": params.get("resource", [None])[0], 
                        "content": doc,
                        "type": "dts"
                    }
                    collation["witnesses"].append(witness)
            collation["ref_id"] = ref
            filepath = get_section_filepath(settings, collection_name=f"{col.get('@id')}_{job_id}", ref_id=ref, ext="json")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                json.dump(collation, f)
            # save to tmp and return path
            paths.append(filepath)
        return True, paths, collection_title, resources