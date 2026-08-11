import os
import json
import logging

from httpx import AsyncClient, HTTPStatusError
from uritemplate import URITemplate
from urllib.parse import urlparse, parse_qs, urljoin
from copy import deepcopy
from typing import Optional

from core.exceptions import DtsError
from helpers.helpers import extract_dts_error_detail, get_section_filepath
from core.config import Settings

logger = logging.getLogger("s-bridge")


class DtsPreparator:
    @staticmethod
    async def run(
        url: str,
        target_ref: Optional[str],
        job_id: str,
        http_client: AsyncClient,
        settings: Settings,
    ) -> tuple[bool, list[str], str, list[str]]:
        """
        Prepares the sections for collation by fetching the necessary data from a DTS API.
        """
        document_urls = []
        refs_list = []
        collation_model = {"witnesses": []}
        paths = []

        current_url = url
        visited_urls = set()
        members = []
        collection_title = None
        collection_id = None

        while current_url and current_url not in visited_urls:
            visited_urls.add(current_url)
            res = await http_client.get(current_url, follow_redirects=True)
            if res.status_code != 200:
                detail = extract_dts_error_detail(res)
                raise DtsError(
                    f"DTS collection endpoint returned HTTP {res.status_code} for {current_url}{detail}"
                )
            col = res.json()
            if collection_title is None:
                collection_title = (
                    col.get("@id") if col.get("title") == "" else col.get("title")
                )
            if collection_id is None:
                collection_id = col.get("@id")

            page_members = col.get("member") or []
            members.extend(page_members)

            view = col.get("view") or {}
            view_id = view.get("@id")
            if view_id:
                visited_urls.add(view_id)

            next_url = view.get("next")
            if not next_url:
                break
            next_url = urljoin(str(res.url), next_url)
            if next_url in visited_urls:
                break
            current_url = next_url

        # Select only members of type "resource"
        resource_members = [
            item
            for item in members
            if isinstance(item.get("@type"), str)
            and item.get("@type").lower() == "resource"
        ]

        if not resource_members:
            raise DtsError("Not a single resource found")

        navigation_urls = [
            URITemplate(item.get("navigation")) for item in resource_members
        ]
        resources = [item.get("@id") for item in resource_members]

        for nav in navigation_urls:
            current_url = nav.expand(down=1, page=1)
            visited_urls = set()

            while current_url and current_url not in visited_urls:
                visited_urls.add(current_url)
                try:
                    res = await http_client.get(current_url, follow_redirects=True)
                    res.raise_for_status()
                except HTTPStatusError as e:
                    detail = extract_dts_error_detail(e.response)
                    raise DtsError(
                        f"DTS navigation request failed — HTTP {e.response.status_code} for {current_url}{detail}"
                    ) from e
                data = res.json()
                document_url = URITemplate(data.get("resource", {}).get("document", ""))

                for ref in data.get("member", []):
                    refs_list.append(ref.get("identifier"))
                    document_urls.append(document_url.expand(ref=ref.get("identifier")))

                view = data.get("view") or {}
                view_id = view.get("@id")
                if view_id:
                    visited_urls.add(view_id)

                next_url = view.get("next")
                if not next_url:
                    break
                next_url = urljoin(str(res.url), next_url)
                if next_url in visited_urls:
                    break
                current_url = next_url

        refs_list = list(dict.fromkeys(refs_list))

        # gives the possibility for a specific section/ref in relation to origin ref parameter
        if target_ref:
            if target_ref in refs_list:
                refs_list = [target_ref]
            else:
                logger.warning(
                    f"Target ref '{target_ref}' not found in collection '{url}'"
                )
                return False, [], collection_title, resources

        for ref in refs_list:
            document_url = [
                u
                for u in document_urls
                if parse_qs(urlparse(u).query).get("ref", [None])[0] == str(ref)
            ]
            collation = deepcopy(collation_model)
            for doc in document_url:
                params = parse_qs(urlparse(doc).query)
                witness = {
                    "id": params.get("resource", [None])[0],
                    "content": doc,
                    "type": "dts",
                }
                collation["witnesses"].append(witness)
            collation["ref_id"] = ref
            filepath = get_section_filepath(
                settings,
                collection_name=f"{collection_id}_{job_id}",
                ref_id=ref,
                ext="json",
            )
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                json.dump(collation, f)
            # save to tmp and return path
            paths.append(filepath)
        return True, paths, collection_title, resources
