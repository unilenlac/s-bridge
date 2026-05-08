import json
import os

from httpx import AsyncClient
from uritemplate import URITemplate
from urllib.parse import urlparse, parse_qs
from copy import deepcopy

from helpers.helpers import get_section_filepath


class DtsPreparator:
    
    @staticmethod
    async def run(url: str, http_client: AsyncClient) -> tuple[bool, list[str]]:
        """
        Prepares the sections for collation by fetching the necessary data from the DTS API.
        """
        res = await http_client.get(url, follow_redirects=True)
        if res.status_code != 200:
            raise Exception(f"Failed to fetch data from {url}: {res.status_code} {res.text}")
        col = res.json()
        collection_title = col.get("@id") if col.get("title") == "" else col.get("title")
        navigation_urls = [URITemplate(item.get('navigation')) for item in col.get("member", []) if item.get("@type").lower() == "resource"]
        resources = [item.get('@id') for item in col.get("member", []) if item.get("@type").lower() == "resource"]
        document_urls = []
        refs_list = []
        collation_model = {
            "witnesses": []
        }
        paths = []

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
        for ref in refs_list:
            document_url = list(filter(lambda url: f"ref={ref}" in url, document_urls))
            collation = deepcopy(collation_model)
            if len(document_url):
                while len(document_url):
                    doc = document_url.pop()
                    params = parse_qs(urlparse(doc).query)
                    res = await http_client.get(doc, follow_redirects=True)
                    res.raise_for_status()
                    """ todo : this is a bit clumsy. 
                    we could create an iterator that yields the url request, status validation, content extraction, logging etc and add it into the 'content' field
                    the collation could also be saved to a pickle file instead of json to avoid the json dump overhead and the need to load the whole thing in memory at once. 
                    The iterator would be consumed at the analyser level. """
                    witness = {"id": params.get("resource", [None])[0], "content": res.text}
                    collation["witnesses"].append(witness)
            collation["ref_id"] = ref
            filepath = get_section_filepath(collection_name=f"{col.get('@id')}", ref_id=ref)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                json.dump(collation, f)
            # save to tmp and return path
            paths.append(filepath)
        return True, paths, collection_title, resources