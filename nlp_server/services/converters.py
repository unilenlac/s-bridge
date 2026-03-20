import xml.etree.ElementTree as ET
from typing import List

from nlp_server.core.interfaces import Processor, Parser
from nlp_server.models.collatex import Token

class RawStrategyConverter:
    def __init__(self, proc: Processor):
        self.processor = proc
    #the normalization default parameter *original" is overrun by fatAPI logic. It is currently useless here. Same for default filder_del bool.
    def run(self, data: str, normalization: str = "original", filter_del: bool = False) -> List[Token]: 
        return self.processor.process(data, normalization=normalization)

class EnrichedStrategyConverter:
    def __init__(self, proc: Processor, parser: Parser):
        self.processor = proc
        self.parser = parser

    def run(self, data: str, normalization: str = "lemma+pos", filter_del: bool = True) -> List[Token]:
        # 1. Extract clean text and offset metadata using the TEI Parser
        clean_text, metadata_map = self.parser.parse(data)
        
        # 2. Process the raw string into tokens using our generic Processor
        raw_tokens: List[Token] = self.processor.process(clean_text, normalization=normalization)
        
        # 3. Marry the TEI Metadata with the NLP Tokens based on character offsets
        enriched_tokens = []
        current_char_offset = 0
        
        for token in raw_tokens:
            if getattr(token, 'char_start', None) is not None and getattr(token, 'char_stop', None) is not None:
                char_start = token.char_start
                char_stop = token.char_stop
                current_char_offset = char_stop + 1
            else:
                char_start = current_char_offset
                char_stop = current_char_offset + len(token.original)
                current_char_offset += len(token.original) + 1 
 
            
            # Get matching metadata
            editorial_metadata = self.parser.get_metadata_for_token(char_start, char_stop, metadata_map)
            
            # Reconstruct the Token dictionary to inject the metadata
            token_dict = token.model_dump(by_alias=False, exclude_none=True)
            token_dict.update(editorial_metadata)
            
            # Re-instantiate the completely enriched Token
            
            # THE FILTERING LOGIC
            if filter_del and editorial_metadata.get("del") is True:
                continue # Skip this token entirely

            enriched_token = Token(**token_dict)
            enriched_tokens.append(enriched_token)
            
        return enriched_tokens