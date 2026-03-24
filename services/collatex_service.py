import logging
import asyncio
from typing import List, Dict, Any, Optional

from core.interfaces import DocumentFetcher, Converter
from api.dependencies import ProcessingOptions
from models.tokenization import CollatexResponse, CollatexWitness

logger = logging.getLogger(__name__)

class CollatexService:
    def __init__(self, fetcher: DocumentFetcher):
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

    async def prepare_collatex(
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
