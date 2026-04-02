import json
import logging
import asyncio
import os
import tempfile
from typing import List, Optional, Union, Dict

from core.interfaces import DocumentFetcher, Converter
from api.dependencies import ProcessingOptions
from models.tokenization import CollatexResponse, CollatexWitness
from core.config import Settings


logger = logging.getLogger(__name__)

class WitnessService:
    def __init__(self, fetcher: DocumentFetcher):
        # example : DTSClient
        self.fetcher = fetcher

    async def _process_single_witness(
        self,
        resource: str,
        converter: Converter,
        options: ProcessingOptions,
        ref: Optional[str]
    ) -> Optional[CollatexWitness]:
        """Helper to process a single witness asynchronously and handle its own errors."""
        try:
            # 1. Fetch XML sequence asynchronously
            xml_data = await self.fetcher.get_document(resource, ref=ref)

            # 2. Run NLP/TEI conversion in a separate thread (it is heavily CPU-bound)
            tokens = await asyncio.to_thread(
                converter.run,
                xml_data,
                normalization=options.normalization,
                filter_del=options.filter_del
            )

            # 3. Return the populated witness
            return CollatexWitness(id=resource, tokens=tokens)

        except Exception as e:
            # Catch all exceptions (404s, parsing errors) to prevent crashing the entire API
            logger.warning(f"Gracefully skipping witness '{resource}': {e}")
            return None

	#Depreciated, used by prepare-collatex/whole
    async def process_witnesses(
        self,
        resources: List[str],
        converter: Converter,
        options: ProcessingOptions,
        ref: Optional[str] = None
    ) -> CollatexResponse:
        """
        Fetches the XML for multiple witnesses concurrently, parses them in parallel threads,
        and packages the tokens into a JSON format expected by Collatex.
        """

        # Fire off all witness requests at the exact same time
        tasks = [
            self._process_single_witness(resource, converter, options, ref)
            for resource in resources
        ]

        # Wait for all network calls and NLP threads to finish
        results = await asyncio.gather(*tasks)

        # Filter out the witnesses that failed (returned None)
        valid_witnesses = [w for w in results if w is not None]

        # If absolutely everything failed, let the client know
        if not valid_witnesses:
             raise ValueError(f"All requested witnesses failed to fetch or parse for ref='{ref}'. Check your IDs and references.")

        return CollatexResponse(witnesses=valid_witnesses)

    def get_section_filepath(self, collection_name: str, ref_id: str) -> str:
        """Standardizes the path for a prepared section file."""
        settings = Settings()
        return os.path.join(settings.output_dir, collection_name, f"{ref_id}.json")

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

    async def prepare_section_if_needed(
        self,
        resources: List[str],
        ref: str,
        converter: Converter,
        options: ProcessingOptions,
        force: bool = False
    ) -> str:
        """
        Ensures a specific section is prepared and saved to disk.
        Returns the path to the prepared file.
        """
        if not resources:
            raise ValueError("At least one resource is required.")

        collection_name = await self.fetcher.get_collection_name(resources[0])

        filepath = self.get_section_filepath(collection_name, ref)

        if not force and os.path.exists(filepath):
            logger.info(f"Using existing prepared file for ref '{ref}': {filepath}")
            return filepath

        logger.info(f"Preparing section '{ref}' for collection '{collection_name}'...")
        
        # Fetch and process
        section_data = await self.process_witnesses(
            resources=resources,
            converter=converter,
            options=options,
            ref=ref
        )

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Write to disk
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                section_data.model_dump(
                    by_alias=True,
                    exclude_none=True,
                    exclude_defaults=True,
                ),
                f,
                indent=2,
                ensure_ascii=False,
            )
        
        logger.info(f"Successfully prepared and saved section to: {filepath}")
        return filepath

