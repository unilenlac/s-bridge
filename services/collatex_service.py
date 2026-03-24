import logging
from typing import List, Dict, Any, Optional

from core.interfaces import DocumentFetcher, Converter
from api.dependencies import ProcessingOptions
from models.collatex import CollatexResponse, CollatexWitness

logger = logging.getLogger(__name__)

class CollatexService:
    def __init__(self, fetcher: DocumentFetcher):
        self.fetcher = fetcher

    async def prepare_collatex(
        self, 
        resources: List[str], 
        converter: Converter,
        options: ProcessingOptions,
        ref: Optional[str] = None
    ) -> CollatexResponse:
        """
        Fetches the XML for multiple witnesses using the provided DocumentFetcher, 
        passes them through the converter, and packages the tokens into a JSON format expected by Collatex.
        """
        witnesses = []
        
        for resource in resources:
            try:
                # 1. Fetch XML sequence
                xml_data = await self.fetcher.get_document(resource, ref=ref)
                
                # 2. Run NLP/TEI conversion
                tokens = converter.run(
                    xml_data,
                    normalization=options.normalization,
                    filter_del=options.filter_del
                )
                
                # 3. Bind witness sequence into array
                witnesses.append(CollatexWitness(
                    id=resource,
                    tokens=tokens
                ))
                
            except Exception as e:
                logger.error(f"Failed to process witness '{resource}': {e}")
                raise ValueError(f"Failed to fetch or convert witness '{resource}': {e}")
                
        return CollatexResponse(witnesses=witnesses)
