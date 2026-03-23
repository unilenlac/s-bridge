import logging
from typing import List, Dict, Any, Optional

from core.interfaces import DocumentFetcher, Converter

logger = logging.getLogger(__name__)

class CollatexService:
    def __init__(self, fetcher: DocumentFetcher):
        self.fetcher = fetcher

    async def prepare_collatex(
        self, 
        resources: List[str], 
        converter: Converter, 
        ref: Optional[str] = None
    ) -> Dict[str, Any]:
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
                tokens = converter.run(xml_data)
                
                # 3. Serialize tokens by mapping aliases
                token_dicts = []
                for t in tokens:
                    serialized_token = t.model_dump(by_alias=True, exclude_none=True)
                    token_dicts.append(serialized_token)
                
                # 4. Bind witness sequence into array
                witnesses.append({
                    "id": resource,
                    "tokens": token_dicts
                })
                
            except Exception as e:
                logger.error(f"Failed to process witness '{resource}': {e}")
                raise ValueError(f"Failed to fetch or convert witness '{resource}': {e}")
                
        return {"witnesses": witnesses}
