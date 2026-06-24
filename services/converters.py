from typing import List
import re

from core.interfaces import Processor, Parser
from models.tokenization import Token
from helpers.helpers import extract_body_content


class RawStrategyConverter:
    def __init__(self, proc: Processor):
        self.processor = proc

    def run(
        self, data: str, normalization: str = "text", filter_del: bool = False
    ) -> List[Token]:
        import xml.etree.ElementTree as ET

        body_content = extract_body_content(data)

        try:
            # Attempt to parse as XML to isolate body and avoid header noise
            root = ET.fromstring(body_content)
            data = "".join(root.itertext())
        except Exception:
            # If parsing fails, fall back to regex tag-stripping to strip any XML remains
            clean_text = re.sub(r'<[^>]*>', '', body_content)
            # Strip any trailing unclosed tag at the very end of the string
            data = re.sub(r'<[^>]*$', '', clean_text)

        return self.processor.process(data, normalization=normalization)


class EnrichedStrategyConverter:
    def __init__(self, proc: Processor, parser: Parser):
        self.processor = proc
        self.parser = parser

    def run(
        self, data: str, normalization: str = "lemma", filter_del: bool = True
    ) -> List[Token]:
        # 1. Extract clean text and offset metadata using the TEI Parser
        clean_text, metadata_map = self.parser.parse(data)

        # 2. Process the raw string into tokens using our generic Processor
        raw_tokens: List[Token] = self.processor.process(
            clean_text, normalization=normalization
        )

        # 3. Marry the TEI Metadata with the NLP Tokens based on character offsets
        enriched_tokens = []
        current_char_offset = 0

        for token in raw_tokens:
            if (
                getattr(token, "char_start", None) is not None
                and getattr(token, "char_stop", None) is not None
            ):
                char_start = token.char_start
                char_stop = token.char_stop
                current_char_offset = char_stop + 1
            else:
                char_start = current_char_offset
                char_stop = current_char_offset + len(token.original)
                current_char_offset += len(token.original) + 1

            # Get matching metadata
            editorial_metadata = self.parser.get_metadata_for_token(
                char_start, char_stop, metadata_map
            )

            # Reconstruct the Token dictionary to inject the metadata
            token_dict = token.model_dump(by_alias=False, exclude_none=True)
            token_dict.update(editorial_metadata)

            # Re-instantiate the completely enriched Token

            # THE FILTERING LOGIC
            if filter_del and editorial_metadata.get("del") is True:
                continue  # Skip this token entirely

            enriched_token = Token(**token_dict)
            enriched_tokens.append(enriched_token)

        return enriched_tokens
