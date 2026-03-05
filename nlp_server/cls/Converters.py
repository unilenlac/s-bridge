import xml.etree.ElementTree as ET
from typing import List

from nlp_server.interface.interfaces import Processor
from nlp_server.model.collatex import Token
from nlp_server.cls.TEIParser import TEIParser

class SimpleConverter:
    def __init__(self, proc: Processor):
        self.processor = proc
    def run(self, data: ET.Element) -> str:  # Example: convert input text to uppercase
        return "".join(data.itertext())

class FullConverter:
    def __init__(self, proc: Processor, parser: Parser):
        self.processor = proc
        self.parser = parser

    def run(self, data: ET.Element) -> List[Token]:
        # 1. Extract clean text and offset metadata using the TEI Parser
        clean_text, metadata_map = self.parser.parse(data)
        
        # 2. Process the raw string into tokens using our generic Processor
        raw_tokens: List[Token] = self.processor.process(clean_text)
        
        # 3. Marry the TEI Metadata with the NLP Tokens based on character offsets
        enriched_tokens = []
        current_char_offset = 0
        
        for token in raw_tokens:
            char_start = current_char_offset
            char_stop = current_char_offset + len(token.original)
            
            # Increment offset for next token + space
            current_char_offset += len(token.original) + 1 
            
            # Get matching metadata
            editorial_metadata = self.parser.get_metadata_for_token(char_start, char_stop, metadata_map)
            
            # Reconstruct the Token dictionary to inject the metadata
            token_dict = token.model_dump(by_alias=True, exclude_none=True)
            token_dict.update(editorial_metadata)
            
            # Re-instantiate the completely enriched Token
            enriched_token = Token(**token_dict)
            enriched_tokens.append(enriched_token)
            
        return enriched_tokens