import json
import logging
import asyncio
import os
from typing import List, Optional

from core.interfaces import DocumentFetcher, Converter
from api.dependencies import ProcessingOptions
from models.tokenization import CollatexResponse, CollatexWitness

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

    async def process_witnesses_by_section(
        self,
        resources: List[str],
        converter: Converter,
        options: ProcessingOptions,
    ) -> List[str]:
        """
        When ref=None: fetches the list of top-level refs from the Navigation API
        (using the first resource as authority), then for each ref fetches all
        witnesses concurrently, and writes one JSON file per section.

        Files are written to: <output_dir>/<collection_name>/<citeType>_<identifier>.json

        :return: List of written file paths.
        """
        if not resources:
            raise ValueError("At least one resource is required.")

        # 1. Get the ordered list of top-level refs from the first resource
        nav_members = await self.fetcher.get_navigation(resources[0])
        if not nav_members:
            raise ValueError(f"No navigation members found for resource '{resources[0]}'.")

        collection_name = await self.fetcher.get_collection_name(resources[0])

        logger.info(
            f"Processing {len(nav_members)} sections across {len(resources)} resources "
            f"for collection '{collection_name}'"
        )

        # 2. Prepare output directory
        target_dir = os.path.join("collections", collection_name)
        os.makedirs(target_dir, exist_ok=True)

        written_files: List[str] = []

        # 3. Process each section: collect all witnesses for this ref, then write
        for member in nav_members:
            ref_id = member["identifier"]
            cite_type = member["citeType"]
            filename = f"{cite_type}_{ref_id}.json"
            filepath = os.path.join(target_dir, filename)

            # Fetch all witnesses for this section concurrently
            tasks = [
                self._process_single_witness(resource, converter, options, ref=ref_id)
                for resource in resources
            ]
            results = await asyncio.gather(*tasks)
            valid_witnesses = [w for w in results if w is not None]

            if not valid_witnesses:
                logger.warning(
                    f"All witnesses failed for section '{ref_id}' — skipping file '{filename}'."
                )
                continue

            section_response = CollatexResponse(witnesses=valid_witnesses)

            # Write to disk
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    section_response.model_dump(
                        by_alias=True,
                        exclude_none=True,
                        exclude_defaults=True,
                    ),
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            written_files.append(filepath)
            logger.info(f"Wrote section file: {filepath}")

        return written_files
