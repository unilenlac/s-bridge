import json
import logging
import asyncio
import os
import tempfile
from typing import List, Optional, Union, Dict

from httpx import AsyncClient

from core.interfaces import Converter
from api.dependencies import ProcessingOptions
from models.tokenization import CollatexResponse, CollatexWitness
from core.config import Settings
from helpers.helpers import ServerId, get_xml_from_dts_url
from services.preparators import DtsPreparator

logger = logging.getLogger("s-bridge")


class WitnessService:
    def __init__(self):
        self.preparators = {'dts': DtsPreparator}
    
    async def preprocess_sections(self, url: str, http_client: AsyncClient) -> str | None:
        """
        Placeholder for any preprocessing steps needed before collation.
        For example, this could handle caching, normalization, or other transformations.
        """
        try:
            server_identity = await ServerId(url, logger, http_client)
        except Exception as e:
            logger.warning(f"Could not determine server identity for {url}: {e}")
            server_identity = "unknown"
        prearator = self.preparators.get(server_identity.split()[0].lower())
        if prearator:
            logger.info(f"Using preparator '{prearator.__name__}' for server '{server_identity}'")
            return await prearator.run(url, http_client)
        else:
            logger.info(f"No specific preparator found for server '{server_identity}'. Using URL as-is.")
            return None

    async def _process_single_witness(
        self,
        resource: Dict,
        converter: Converter,
        options: ProcessingOptions,
        ref: Optional[str],
        http_client: AsyncClient
    ) -> Optional[CollatexWitness]:
        """Helper to process a single witness asynchronously and handle its own errors."""
        try:
            # 1. Fetch XML sequence asynchronously
            content = resource.get("content", "")
            # todo: this must be selected based on the server identity, for now we assume it's always a DTS url
            xml_data = await get_xml_from_dts_url(content, http_client, logger)  # This is an async generator that yields XML content

            # 2. Run NLP/TEI conversion in a separate thread (it is heavily CPU-bound)
            tokens = await asyncio.to_thread(
                converter.run,
                xml_data,
                normalization=options.normalization,
                filter_del=options.filter_del
            )

            # 3. Return the populated witness
            return CollatexWitness(id=resource.get("id"), tokens=tokens)

        except Exception as e:
            # Catch all exceptions (404s, parsing errors) to prevent crashing the entire API
            logger.warning(f"Gracefully skipping witness '{resource.get('id')}' for reference '{ref}.")
            return None

    async def process_witnesses(
        self,
        converter: Converter,
        options: ProcessingOptions,
        http_client: AsyncClient,
        path: Optional[str] = None
    ) -> CollatexResponse:
        """
        Fetches the XML for multiple witnesses concurrently, parses them in parallel threads,
        and packages the tokens into a JSON format expected by Collatex.
        """

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Fire off all witness requests at the exact same time
        tasks = [
            self._process_single_witness(witness, converter, options, data.get("ref_id"), http_client)
            for witness in data.get("witnesses", [])
        ]

        # Wait for all network calls and NLP threads to finish
        results = await asyncio.gather(*tasks)

        # Filter out the witnesses that failed (returned None)
        valid_witnesses = [w for w in results if w is not None]

        # If absolutely everything failed, let the client know
        if not valid_witnesses:
             raise ValueError(f"All requested witnesses failed to fetch or parse for ref='{data.get('ref_id')}'. Check your IDs and references.")

        return CollatexResponse(ref_id=data.get("ref_id"), witnesses=valid_witnesses)

    def load_prepared_section(self, filepath: str) -> CollatexResponse:
        """Loads a prepared Collatex JSON file from disk."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Prepared section file not found: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return CollatexResponse.model_validate(data)

    def save_collation_result(
        self, 
        collection_name: str, 
        ref_id: str, 
        result: Union[Dict, str], 
        output_format: str
    ) -> str:
        """
        Saves a collation result to a file and returns the path.
        """
        settings = Settings()
        target_dir = os.path.join(settings.collation_dir, collection_name)
        os.makedirs(target_dir, exist_ok=True)

        # Determine file extension based on format
        format_map = {
            "application/json": ".json",
            "text/plain": ".dot",  # Most common use case for text/plain in Collatex
            "application/tei+xml": ".xml",
            "application/graphml+xml": ".graphml",
            "image/svg+xml": ".svg",
        }
        ext = format_map.get(output_format, ".txt")
        
        filename = f"{ref_id}{ext}"
        filepath = os.path.join(target_dir, filename)

        if isinstance(result, dict):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(result)

        logger.info(f"Saved collation result to: {filepath}")
        return filepath

    async def analyse_section(
        self,
        converter: Converter,
        options: ProcessingOptions,
        http_client: AsyncClient,
        path: Optional[str] = None
    ) -> str:
        """
        Prepares a specific section and saves it to disk by fully regenerating it.
        Returns the path to the prepared file.
        """

        # this def will open the json file, but it's probably an unecessary def
        logger.info(f"Preparing section for collection '{path}' completely...")
        
        # Fetch and process all resources
        section_data = await self.process_witnesses(
            converter=converter,
            options=options,
            http_client=http_client,
            path=path
        )

        self._dump_to_file(section_data, path)
        
        logger.info(f"Successfully prepared and saved section to: {path}")
        return path

    def _dump_to_file(self, data: CollatexResponse, filepath: str):
        """Helper to write a CollatexResponse to disk as JSON."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                data.model_dump(
                    by_alias=True,
                    exclude_none=True,
                    exclude_defaults=True,
                ),
                f,
                indent=2,
                ensure_ascii=False,
            )

